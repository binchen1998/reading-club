import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..book_pages import split_chapters
from ..config import CATALOG
from ..db import get_db
from ..models import User
from ..qiniu_upload import covers_json_key, qiniu_get_bytes, with_cdn_timestamp
from ..remote_book import book_slug_of, page_image_url, peek_book
from ..routers.progress import book_cursors_for_series, serialize_cursor

router = APIRouter(prefix="/api")


@router.get("/catalog")
def catalog():
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    covers = _qiniu_covers()
    series = []
    for row in data.get("series") or []:
        series.append(
            {
                "id": row["id"],
                "title": row["title"],
                "readable": True,
                "book_count": row.get("book_count") or len(row.get("books") or []),
                "cover": covers.get(row["id"]) or "",
            }
        )
    return {"series": series}


@router.get("/series/{series_id}")
def series_detail(
    series_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    row = next((s for s in data["series"] if s["id"] == series_id), None)
    if not row:
        raise HTTPException(404, "没有这个系列")
    cursors = book_cursors_for_series(db, user.username, series_id)
    books = []
    for book in row.get("books") or []:
        slug = book_slug_of(book.get("title") or "", book.get("name") or "")
        cursor = cursors.get(slug)
        last_page = book_last_page(series_id, slug)
        cursor_info = serialize_cursor(cursor, last_page) if cursor else {}
        books.append(
            {
                "title": book.get("title"),
                "name": book.get("name"),
                "number": book.get("number"),
                "slug": slug,
                "ready": True,
                "readable": True,
                "cover": page_image_url(series_id, slug, 1),
                "lastPage": cursor_info.get("page") or 0,
                "lastChapterId": cursor_info.get("chapterId") or "",
                "finished": bool(cursor_info.get("finished")),
            }
        )
    return {"series": {"id": row["id"], "title": row["title"], "readable": True}, "books": books}


def _qiniu_covers() -> dict[str, str]:
    raw = qiniu_get_bytes(covers_json_key(), cache_bust=True)
    if not raw:
        return {}
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    covers: dict[str, str] = {}
    for item in payload.get("series") or []:
        series_id = str(item.get("id") or "").strip()
        cover = str(item.get("cover") or "").strip()
        if series_id and cover:
            covers[series_id] = with_cdn_timestamp(cover)
    return covers


def book_last_page(series_id: str, book_slug: str) -> int:
    book = peek_book(series_id, book_slug)
    if not book:
        return 0
    try:
        pages = [
            int(page.get("page") or 0)
            for chapter in split_chapters(book.get("pages") or [], book.get("title") or "")
            for page in chapter.get("pages") or []
        ]
    except Exception:
        return 0
    return max(pages) if pages else 0
