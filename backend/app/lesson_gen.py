"""按需生成课稿（在线讲解，OpenAI luna）。"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

from .config import LESSONS
from .openai_llm import get_openai_client

logger = logging.getLogger("lesson_gen")
_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def lesson_file(series_id: str, book_slug: str, chapter: int) -> Path:
    return LESSONS / series_id / book_slug / f"ch{chapter:02d}.json"


def page_lesson_file(series_id: str, book_slug: str, page: int) -> Path:
    return LESSONS / series_id / book_slug / f"p{int(page):03d}.json"


def lesson_exists(series_id: str, book_slug: str, chapter: int) -> bool:
    return lesson_file(series_id, book_slug, chapter).exists()


def page_lesson_exists(series_id: str, book_slug: str, page: int) -> bool:
    return page_lesson_file(series_id, book_slug, page).exists()


def _lock_for(key: str) -> threading.Lock:
    with _locks_guard:
        lock = _locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _locks[key] = lock
        return lock


def _write_lesson(path: Path, lesson: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(lesson, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def generate_lesson(series_id: str, book_slug: str, chapter: int) -> dict:
    path = lesson_file(series_id, book_slug, chapter)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    if get_openai_client() is None:
        raise RuntimeError("未配置 OPENAI_API_KEY，无法生成讲解")
    from .openai_llm import openai_base_url

    openai_base_url()
    key = f"{series_id}/{book_slug}/ch{chapter:02d}"
    lock = _lock_for(key)
    with lock:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        from scripts.prebuild_content.lesson_llm import generate_chapter_lesson_full

        from .book_pages import split_chapters
        from .remote_book import load_book

        logger.info("开始生成课稿 %s，先读原站书页", key)
        try:
            book = load_book(series_id, book_slug)
        except FileNotFoundError as exc:
            raise RuntimeError("书目里没有这本书") from exc
        chapters = split_chapters(book.get("pages") or [], book.get("title") or "")
        info = next((row for row in chapters if int(row.get("chapter") or 0) == chapter), None)
        if info is None:
            raise RuntimeError("这一章还没开放")
        logger.info("online lesson generate %s pages=%s", key, len(info.get("pages") or []))
        try:
            lesson = generate_chapter_lesson_full(info)
        except Exception as exc:
            logger.exception("online lesson generate failed %s", key)
            raise RuntimeError(f"讲解生成失败：{exc}") from exc
        _write_lesson(path, lesson)
        return lesson


def ensure_lesson(series_id: str, book_slug: str, chapter: int) -> dict:
    return generate_lesson(series_id, book_slug, chapter)


def _page_row(series_id: str, book_slug: str, page: int) -> dict:
    from .book_pages import annotate_pages
    from .remote_book import load_one_page, peek_book

    book = peek_book(series_id, book_slug)
    if book:
        annotated = annotate_pages(book.get("pages") or [])
        rec = next((item for item in (book.get("pages") or []) if int(item.get("page") or 0) == page), None)
        row = next((item for item in annotated if int(item.get("page") or 0) == page), None)
        if row:
            return {**row, "guide": (rec or {}).get("guide") or ""}
        if rec:
            return {
                "page": page,
                "english": rec.get("english") or "",
                "translate": rec.get("translate") or "",
                "guide": rec.get("guide") or "",
                "carry_from_prev": False,
                "continues_on_next": False,
                "prev_page_tail": "",
                "next_page_head": "",
            }
    rows = []
    for num in range(max(0, page - 1), page + 2):
        rec = load_one_page(series_id, book_slug, num)
        if rec:
            rows.append(rec)
    annotated = annotate_pages(rows)
    row = next((item for item in annotated if int(item.get("page") or 0) == page), None)
    rec = next((item for item in rows if int(item.get("page") or 0) == page), None)
    if row:
        return {**row, "guide": (rec or {}).get("guide") or ""}
    rec = rec or load_one_page(series_id, book_slug, page)
    if not rec:
        raise RuntimeError("没有这一页")
    return {
        "page": page,
        "english": rec.get("english") or "",
        "translate": rec.get("translate") or "",
        "guide": rec.get("guide") or "",
        "carry_from_prev": False,
        "continues_on_next": False,
        "prev_page_tail": "",
        "next_page_head": "",
    }


def generate_page_lesson(series_id: str, book_slug: str, page: int) -> dict:
    page = int(page)
    path = page_lesson_file(series_id, book_slug, page)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    if get_openai_client() is None:
        raise RuntimeError("未配置 OPENAI_API_KEY，无法生成讲解")
    from .openai_llm import openai_base_url

    openai_base_url()
    key = f"{series_id}/{book_slug}/p{page:03d}"
    lock = _lock_for(key)
    with lock:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        from scripts.prebuild_content.lesson_llm import fallback_page_beat, generate_chapter_lesson

        from .remote_book import catalog_book, peek_book

        logger.info("开始生成单页课稿 %s", key)
        row = _page_row(series_id, book_slug, page)
        book = peek_book(series_id, book_slug) or {}
        catalog = catalog_book(series_id, book_slug) or {}
        title = book.get("title") or catalog.get("title") or book_slug
        if not (row.get("english") or "").strip():
            lesson = {
                "chapter": 1,
                "title": title,
                "title_zh": "",
                "word_bank": [],
                "phrase_bank": [],
                "beats": [
                    {
                        "page": page,
                        "explain": "",
                        "words": [],
                        "phrases": [],
                        "segments": [],
                    }
                ],
            }
            _write_lesson(path, lesson)
            logger.info("单页无正文，跳过模型 %s", key)
            return lesson
        info = {"chapter": 1, "title": title, "pages": [row]}
        try:
            lesson = generate_chapter_lesson(info)
        except Exception:
            logger.exception("单页课稿失败，回退本页导读 %s", key)
            lesson = {
                "chapter": 1,
                "title": title,
                "title_zh": "",
                "word_bank": [],
                "phrase_bank": [],
                "beats": [fallback_page_beat(row)],
            }
        if not lesson.get("beats"):
            lesson["beats"] = [fallback_page_beat(row)]
        _write_lesson(path, lesson)
        logger.info("单页课稿完成 %s", key)
        return lesson
