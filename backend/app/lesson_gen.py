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


def lesson_exists(series_id: str, book_slug: str, chapter: int) -> bool:
    return lesson_file(series_id, book_slug, chapter).exists()


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
