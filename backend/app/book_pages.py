"""从 book.json 切章节，供 API 与预生成脚本共用。"""

from __future__ import annotations

import re

CHAPTER_HEAD = re.compile(
    r"^\s*Chapter\s+"
    r"(One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|"
    r"Eleven|Twelve|Thirteen|Fourteen|Fifteen|"
    r"\d+)\b",
    re.I,
)
ORDINALS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
}
SENT_END = re.compile(r'[.!?…]["”\'»」』]?\s*$')
SKIP_HINT = re.compile(
    r"copyright|isbn|all rights reserved|manufactured in|remembering\n|yearling book|"
    r"have read this book|scholastic inc|honor book|look for",
    re.I,
)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\n", " ")).strip()


def sentence_complete(text: str) -> bool:
    value = _norm(text)
    if not value:
        return True
    return bool(SENT_END.search(value))


def page_tail(text: str, words: int = 28) -> str:
    value = _norm(text)
    parts = value.split()
    return " ".join(parts[-words:])


def page_head(text: str, words: int = 28) -> str:
    value = _norm(text)
    parts = value.split()
    return " ".join(parts[:words])


def is_story_page(page: dict) -> bool:
    english = (page.get("english") or "").strip()
    if not english:
        return False
    if CHAPTER_HEAD.search(english):
        return True
    if SKIP_HINT.search(english):
        return False
    if page.get("has_text") is False:
        return False
    return len(_norm(english).split()) >= 2


def chapter_number(english: str) -> int | None:
    match = CHAPTER_HEAD.search(english or "")
    if not match:
        return None
    raw = match.group(1).lower()
    if raw.isdigit():
        return int(raw)
    return ORDINALS.get(raw)


def annotate_pages(pages: list[dict]) -> list[dict]:
    rows: list[dict] = []
    story = [p for p in pages if is_story_page(p)]
    for i, page in enumerate(story):
        prev_en = (story[i - 1].get("english") or "") if i else ""
        next_en = (story[i + 1].get("english") or "") if i + 1 < len(story) else ""
        english = page.get("english") or ""
        rows.append(
            {
                "page": int(page["page"]),
                "english": english,
                "translate": page.get("translate") or "",
                "carry_from_prev": not sentence_complete(prev_en),
                "continues_on_next": not sentence_complete(english),
                "prev_page_tail": page_tail(prev_en) if prev_en and not sentence_complete(prev_en) else "",
                "next_page_head": page_head(next_en) if next_en and not sentence_complete(english) else "",
            }
        )
    return rows


def split_chapters(pages: list[dict], title: str = "") -> list[dict]:
    annotated = annotate_pages(pages)
    if not annotated:
        for page in pages or []:
            english = (page.get("english") or "").strip()
            if not english:
                continue
            annotated.append(
                {
                    "page": int(page.get("page") or 0),
                    "english": english,
                    "translate": page.get("translate") or "",
                    "carry_from_prev": False,
                    "continues_on_next": False,
                    "prev_page_tail": "",
                    "next_page_head": "",
                }
            )
    if not annotated:
        return []
    return [
        {
            "chapter": 1,
            "title": (title or "").strip() or "全书",
            "pages": annotated,
        }
    ]


def clip_segment_to_page(segment: str, page_english: str) -> str:
    """丢掉误带上的上一页/下一页单词，保证朗读段落在本页。"""
    text = _norm(segment)
    page = _norm(page_english)
    if not text or not page:
        return segment.strip()
    if text.lower() in page.lower():
        return text
    words = text.split()
    for i in range(len(words)):
        cand = " ".join(words[i:])
        if len(cand) >= 8 and cand.lower() in page.lower():
            return cand
    for i in range(len(words), 0, -1):
        cand = " ".join(words[:i])
        if len(cand) >= 8 and cand.lower() in page.lower():
            return cand
    return text
