"""清除已生成课稿和词框，便于后台重新生成。"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from sqlalchemy.orm import Session

from .book_pages import split_chapters
from .config import BOOKS, CATALOG, LESSONS, STORAGE
from .remote_book import book_slug_of, load_book, peek_book
from .lesson_gen import lesson_exists, lesson_file
from .lesson_worker import enqueue_chapter, forget_chapter, is_generating
from .models import GeneratedAsset
from .qiniu_upload import ocr_key, qiniu_delete, qiniu_enabled


logger = logging.getLogger("content_reset")
OCR_NAME = re.compile(r"^(\d{3})-([a-f0-9]+)\.json$", re.I)


def _load_catalog() -> list[dict]:
    if not CATALOG.exists():
        return []
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    return list(data.get("series") or [])


def _book_chapters(series_id: str, book_slug: str, fetch: bool = False) -> list[dict]:
    book = peek_book(series_id, book_slug)
    if not book and fetch:
        try:
            book = load_book(series_id, book_slug)
        except Exception:
            book = None
    if not book:
        return []
    try:
        chapters = split_chapters(book.get("pages") or [], book.get("title") or "")
    except Exception:
        logger.exception("read book failed %s/%s", series_id, book_slug)
        return []
    rows = []
    for info in chapters:
        num = int(info.get("chapter") or 0)
        if not num:
            continue
        pages = [int(p.get("page") or 0) for p in info.get("pages") or [] if p.get("page")]
        rows.append(
            {
                "chapter": num,
                "id": f"ch{num:02d}",
                "title": info.get("title") or f"Chapter {num}",
                "pages": pages,
            }
        )
    return rows


def _delete_ocr(series_id: str, book_slug: str, pages: set[int] | None) -> int:
    ocr_dir = STORAGE / "ocr" / series_id / book_slug
    if not ocr_dir.exists():
        return 0
    count = 0
    for file in list(ocr_dir.glob("*.json")):
        match = OCR_NAME.match(file.name)
        if not match:
            continue
        page = int(match.group(1))
        digest = match.group(2)
        if pages is not None and page not in pages:
            continue
        file.unlink(missing_ok=True)
        count += 1
        if qiniu_enabled():
            try:
                qiniu_delete(ocr_key(series_id, book_slug, page, digest))
            except Exception:
                logger.exception("delete qiniu ocr failed %s", file.name)
    return count


def _delete_asset_rows(
    db: Session,
    series_id: str,
    book_slug: str | None,
    pages: set[int] | None,
) -> int:
    needle = f"{series_id}/{book_slug}" if book_slug else f"{series_id}/"
    rows = list(db.query(GeneratedAsset).filter(GeneratedAsset.kind == "ocr").all())
    removed = 0
    for row in rows:
        key = row.asset_key or ""
        if needle not in key:
            continue
        if pages is not None:
            if not pages or not any(f"{page:03d}-" in key for page in pages):
                continue
        db.delete(row)
        removed += 1
    return removed


def content_tree() -> list[dict]:
    catalog = _load_catalog()
    tree = []
    for row in catalog:
        series_id = row["id"]
        books = []
        seen: set[str] = set()
        for book in row.get("books") or []:
            slug = book_slug_of(book.get("title") or "", book.get("name") or "")
            seen.add(slug)
            ready = True
            chapters = []
            generated = 0
            if ready:
                for ch in _book_chapters(series_id, slug):
                    exists = lesson_exists(series_id, slug, ch["chapter"])
                    if exists:
                        generated += 1
                    chapters.append(
                        {
                            **ch,
                            "generated": exists,
                            "generating": is_generating(series_id, slug, ch["chapter"]),
                        }
                    )
            books.append(
                {
                    "slug": slug,
                    "title": book.get("title") or slug,
                    "number": book.get("number"),
                    "ready": ready,
                    "generated": generated,
                    "chapterCount": len(chapters),
                    "chapters": chapters,
                }
            )
        extra_dir = BOOKS / series_id
        if extra_dir.exists():
            for path in sorted(extra_dir.glob("*/book.json")):
                slug = path.parent.name
                if slug in seen:
                    continue
                chapters = []
                generated = 0
                for ch in _book_chapters(series_id, slug):
                    exists = lesson_exists(series_id, slug, ch["chapter"])
                    if exists:
                        generated += 1
                    chapters.append(
                        {
                            **ch,
                            "generated": exists,
                            "generating": is_generating(series_id, slug, ch["chapter"]),
                        }
                    )
                books.append(
                    {
                        "slug": slug,
                        "title": slug,
                        "number": None,
                        "ready": True,
                        "generated": generated,
                        "chapterCount": len(chapters),
                        "chapters": chapters,
                    }
                )
        tree.append({"id": series_id, "title": row.get("title") or series_id, "books": books})
    return tree


def _targets(series_id: str, book_slug: str | None, chapter: int | None) -> list[tuple[str, str, int, set[int]]]:
    series_ids = [series_id] if series_id else [row["id"] for row in _load_catalog()]
    out: list[tuple[str, str, int, set[int]]] = []
    for sid in series_ids:
        slugs: list[str] = []
        if book_slug:
            slugs = [book_slug]
        else:
            catalog = next((row for row in _load_catalog() if row["id"] == sid), None)
            if catalog:
                slugs = [book_slug_of(book.get("title") or "", book.get("name") or "") for book in catalog.get("books") or []]
            extra = BOOKS / sid
            if extra.exists():
                for path in extra.glob("*/book.json"):
                    if path.parent.name not in slugs:
                        slugs.append(path.parent.name)
        for slug in slugs:
            chapters = _book_chapters(sid, slug, fetch=True)
            if not chapters:
                lesson_dir = LESSONS / sid / slug
                if lesson_dir.exists():
                    for file in sorted(lesson_dir.glob("ch*.json")):
                        try:
                            num = int(file.stem[2:])
                        except ValueError:
                            continue
                        chapters.append({"chapter": num, "pages": []})
            for info in chapters:
                num = int(info.get("chapter") or 0)
                if not num:
                    continue
                if chapter and num != chapter:
                    continue
                pages = {int(p) for p in (info.get("pages") or []) if p}
                out.append((sid, slug, num, pages))
    return out


def clear_generated(
    db: Session,
    series_id: str,
    book_slug: str | None = None,
    chapter: int | None = None,
) -> dict:
    series_id = (series_id or "").strip()
    book_slug = (book_slug or "").strip() or None
    if not series_id:
        raise ValueError("缺少系列")
    if chapter and not book_slug:
        raise ValueError("清除某一章时需要指定书")
    targets = _targets(series_id, book_slug, chapter)
    if not targets:
        raise ValueError("没有可清除的课稿范围")

    lessons = 0
    ocr_files = 0
    asset_rows = 0
    queued = 0
    grouped: dict[tuple[str, str], set[int]] = {}
    for sid, slug, num, pages in targets:
        path = lesson_file(sid, slug, num)
        if path.exists():
            extra_pages = set(_pages_from_lesson(path))
            pages = pages | extra_pages
            path.unlink()
            lessons += 1
        page_dir = LESSONS / sid / slug
        if page_dir.exists():
            for file in page_dir.glob("p*.json"):
                try:
                    page_no = int(file.stem[1:])
                except ValueError:
                    continue
                if pages and page_no not in pages:
                    continue
                file.unlink(missing_ok=True)
                lessons += 1
        forget_chapter(sid, slug, num)
        ocr_files += _delete_ocr(sid, slug, pages if chapter else None)
        grouped.setdefault((sid, slug), set()).update(pages)
        enqueue_chapter(sid, slug, num, force=True)
        queued += 1

    if book_slug and not chapter:
        ocr_files += _delete_ocr(series_id, book_slug, None)
        asset_rows += _delete_asset_rows(db, series_id, book_slug, None)
    elif chapter:
        pages = set()
        for sid, slug, num, ch_pages in targets:
            pages.update(ch_pages)
        asset_rows += _delete_asset_rows(db, series_id, book_slug, pages)
    else:
        asset_rows += _delete_asset_rows(db, series_id, None, None)
        for (sid, slug), _pages in grouped.items():
            ocr_files += _delete_ocr(sid, slug, None)

    db.commit()
    return {
        "lessons": lessons,
        "ocrFiles": ocr_files,
        "assetRows": asset_rows,
        "queued": queued,
    }


def _pages_from_lesson(path: Path) -> list[int]:
    try:
        lesson = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    pages = []
    for beat in lesson.get("beats") or []:
        try:
            page = int(beat.get("page") or 0)
        except (TypeError, ValueError):
            continue
        if page:
            pages.append(page)
    return pages
