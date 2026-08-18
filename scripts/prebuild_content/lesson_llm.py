from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from scripts.prebuild_content.pages import clip_segment_to_page

logger = logging.getLogger("prebuild_content")
PROMPT_PATH = Path(__file__).resolve().parent / "prompt.md"
WORD_RE = re.compile(r"[A-Za-z']+")


def page_item_quota(english: str) -> int:
    """本页单词/短句数量：按英文篇幅落在 2–5。"""
    n = len(WORD_RE.findall(english or ""))
    if n <= 40:
        return 2
    if n <= 70:
        return 3
    if n <= 110:
        return 4
    return 5


def _uniq(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.lower()
        if not item or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _client():
    from backend.app.openai_llm import get_openai_client, openai_base_url

    openai_base_url()
    client = get_openai_client()
    if client is None:
        raise RuntimeError("未配置 OPENAI_API_KEY，无法生成课稿")
    return client


def _model_name() -> str:
    from backend.app.openai_llm import teaching_model

    return teaching_model()


def _strip_fence(raw: str) -> str:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def extract_json(raw: str) -> dict[str, Any]:
    text = _strip_fence(raw)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        data = json.loads(text[start : end + 1])
        if isinstance(data, dict):
            return data
    raise ValueError("模型未返回合法 JSON")


def _complete(client, messages):
    from backend.app.openai_llm import complete

    return complete(client, messages, model=_model_name())


def generate_chapter_lesson(chapter: dict) -> dict[str, Any]:
    pages = chapter.get("pages") or []
    payload = {
        "chapter": chapter.get("chapter"),
        "hint_title": chapter.get("title") or "",
        "pages": [
            {
                "page": row["page"],
                "english": row["english"],
                "translate": row["translate"],
                "carry_from_prev": row["carry_from_prev"],
                "continues_on_next": row["continues_on_next"],
                "prev_page_tail": row["prev_page_tail"],
                "next_page_head": row["next_page_head"],
            }
            for row in pages
        ],
    }
    client = _client()
    messages = [
        {"role": "system", "content": load_prompt()},
        {
            "role": "user",
            "content": (
                "请为下面这一章生成课稿 JSON。务必处理跨页截断句子。\n\n"
                + json.dumps(payload, ensure_ascii=False, indent=2)
            ),
        },
    ]
    last_err: Exception | None = None
    for attempt in range(1, 4):
        resp = _complete(client, messages)
        raw = (resp.choices[0].message.content or "").strip()
        try:
            lesson = extract_json(raw)
            return sanitize_lesson(lesson, chapter)
        except Exception as exc:
            last_err = exc
            logger.warning("课稿第 %s 次无效: %s | %s", attempt, exc, raw[:180].replace("\n", " "))
    raise RuntimeError(f"课稿生成失败: {last_err}")


def sanitize_lesson(lesson: dict, chapter: dict) -> dict:
    page_map = {int(row["page"]): row for row in chapter.get("pages") or []}
    beats = []
    for beat in lesson.get("beats") or []:
        try:
            page_no = int(beat.get("page"))
        except (TypeError, ValueError):
            continue
        page = page_map.get(page_no)
        if page is None:
            continue
        english = page.get("english") or ""
        segments = [
            clip_segment_to_page(str(seg), english)
            for seg in (beat.get("segments") or [])
            if str(seg).strip()
        ]
        quota = page_item_quota(english)
        words = _uniq(str(w).strip() for w in (beat.get("words") or []))[:quota]
        phrases = _uniq(str(p).strip() for p in (beat.get("phrases") or []))[:quota]
        beats.append(
            {
                "page": page_no,
                "explain": str(beat.get("explain") or "").strip(),
                "words": words,
                "phrases": phrases,
                "segments": segments,
            }
        )
    lesson["chapter"] = int(chapter.get("chapter") or lesson.get("chapter") or 1)
    lesson["title"] = str(lesson.get("title") or chapter.get("title") or f"Chapter {lesson['chapter']}")
    lesson["title_zh"] = str(lesson.get("title_zh") or "")
    lesson["word_bank"] = [
        {"en": str(item.get("en") or "").strip(), "zh": str(item.get("zh") or "").strip()}
        for item in (lesson.get("word_bank") or [])
        if str(item.get("en") or "").strip()
    ]
    lesson["phrase_bank"] = [
        {"en": str(item.get("en") or "").strip(), "zh": str(item.get("zh") or "").strip()}
        for item in (lesson.get("phrase_bank") or [])
        if str(item.get("en") or "").strip()
    ]
    lesson["beats"] = beats
    if not beats:
        raise ValueError("生成结果没有有效 beat")
    return lesson


def generate_chapter_lesson_full(chapter: dict) -> dict[str, Any]:
    """一章完整课稿；页数多时分段并行，供预生成与在线讲解共用。"""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    pages = chapter.get("pages") or []
    num = int(chapter.get("chapter") or 1)
    if len(pages) <= 12:
        return generate_chapter_lesson(chapter)
    lesson = {
        "chapter": num,
        "title": chapter.get("title") or "",
        "title_zh": "",
        "word_bank": [],
        "phrase_bank": [],
        "beats": [],
    }
    seen_w: set[str] = set()
    seen_p: set[str] = set()
    chunks = [
        {**chapter, "pages": pages[start : start + 10]}
        for start in range(0, len(pages), 10)
    ]
    parts: list[dict] = [{}] * len(chunks)
    with ThreadPoolExecutor(max_workers=min(4, len(chunks))) as pool:
        futs = {pool.submit(generate_chapter_lesson, chunk): i for i, chunk in enumerate(chunks)}
        for fut in as_completed(futs):
            parts[futs[fut]] = fut.result()
    for part in parts:
        lesson["title"] = part.get("title") or lesson["title"]
        lesson["title_zh"] = part.get("title_zh") or lesson["title_zh"]
        for item in part.get("word_bank") or []:
            key = str(item.get("en") or "").lower()
            if not key or key in seen_w:
                continue
            seen_w.add(key)
            lesson["word_bank"].append(item)
        for item in part.get("phrase_bank") or []:
            key = str(item.get("en") or "").lower()
            if not key or key in seen_p:
                continue
            seen_p.add(key)
            lesson["phrase_bank"].append(item)
        lesson["beats"].extend(part.get("beats") or [])
    if not lesson["beats"]:
        raise ValueError("生成结果没有有效 beat")
    return lesson
