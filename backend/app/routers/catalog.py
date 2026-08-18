import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..book_pages import split_chapters
from ..config import BOOKS, CATALOG
from ..db import get_db
from ..lesson_worker import enqueue_book
from ..models import User
from ..routers.progress import book_cursors_for_series, serialize_cursor

router = APIRouter(prefix="/api")


@router.get("/catalog")
def catalog():
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    series = []
    for row in data.get("series") or []:
        series.append(
            {
                "id": row["id"],
                "title": row["title"],
                "readable": True,
                "book_count": row.get("book_count") or len(row.get("books") or []),
                "cover": _series_cover(row["id"]),
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
        local = BOOKS / series_id / slug / "book.json"
        ready = local.exists()
        if ready:
            enqueue_book(series_id, slug)
        cursor = cursors.get(slug)
        last_page = book_last_page(series_id, slug) if ready else 0
        cursor_info = serialize_cursor(cursor, last_page) if cursor else {}
        books.append(
            {
                "title": book.get("title"),
                "name": book.get("name"),
                "number": book.get("number"),
                "slug": slug,
                "ready": ready,
                "readable": ready,
                "cover": f"/media/books/{series_id}/{slug}/pages/001.jpg" if ready else "",
                "lastPage": cursor_info.get("page") or 0,
                "lastChapterId": cursor_info.get("chapterId") or "",
                "finished": bool(cursor_info.get("finished")),
            }
        )
    return {"series": {"id": row["id"], "title": row["title"], "readable": True}, "books": books}


def _series_cover(series_id: str) -> str:
    fallback = {
        "NateTheGreat": "/media/books/NateTheGreat/hungry-book-club/pages/001.jpg",
        "FlyGuy": "/media/books/FlyGuy/01-hi-fly-guy/pages/001.jpg",
    }
    root = BOOKS / series_id
    if root.exists():
        for book_path in sorted(root.glob("*/book.json")):
            cover = f"/media/books/{series_id}/{book_path.parent.name}/pages/001.jpg"
            if (book_path.parent / "pages" / "001.jpg").exists():
                return cover
    return fallback.get(series_id, "")


def book_last_page(series_id: str, book_slug: str) -> int:
    path = BOOKS / series_id / book_slug / "book.json"
    if not path.exists():
        return 0
    try:
        book = json.loads(path.read_text(encoding="utf-8"))
        pages = [
            int(page.get("page") or 0)
            for chapter in split_chapters(book.get("pages") or [])
            for page in chapter.get("pages") or []
        ]
    except Exception:
        return 0
    return max(pages) if pages else 0


def book_slug_of(title: str, name: str) -> str:
    raw = (title or name or "book").lower()
    out = [ch if ch.isalnum() else "-" for ch in raw]
    slug = "".join(out).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or name.lower()
