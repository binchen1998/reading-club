"""读本地 book.json，切章节，并标出跨页未写完的句子。"""

from __future__ import annotations

import json
from pathlib import Path

from backend.app.book_pages import (  # noqa: F401
    annotate_pages,
    chapter_number,
    clip_segment_to_page,
    is_story_page,
    page_head,
    page_tail,
    sentence_complete,
    split_chapters,
)
from scripts.paths import BOOKS, CATALOG, book_slug


def load_book(series_id: str, slug: str) -> dict:
    path = BOOKS / series_id / slug / "book.json"
    if not path.exists():
        raise FileNotFoundError(f"书不在本地：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_catalog() -> dict:
    return json.loads(Path(CATALOG).read_text(encoding="utf-8"))


def list_local_books(series: str | None = None, book: str | None = None) -> list[tuple[str, str, dict]]:
    catalog = load_catalog()
    wanted_series = (series or "").strip()
    wanted_book = (book or "").strip().lower()
    found: list[tuple[str, str, dict]] = []
    for item in catalog.get("series") or []:
        series_id = item.get("id") or ""
        if wanted_series and series_id.lower() != wanted_series.lower():
            continue
        for raw in item.get("books") or []:
            slug = book_slug(raw.get("title") or "", raw.get("name") or "")
            title = (raw.get("title") or "").strip()
            name = (raw.get("name") or "").strip()
            if wanted_book and wanted_book not in {slug.lower(), title.lower(), name.lower()}:
                continue
            book_path = BOOKS / series_id / slug / "book.json"
            if not book_path.exists():
                continue
            payload = json.loads(book_path.read_text(encoding="utf-8"))
            found.append((series_id, slug, payload))
    if wanted_series or wanted_book:
        if not found:
            raise SystemExit(f"没有匹配的本地书：series={series!r} book={book!r}")
    return found
