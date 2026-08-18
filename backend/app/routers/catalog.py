import json

from fastapi import APIRouter, HTTPException

from ..config import BOOKS, CATALOG
from ..lesson_worker import enqueue_book

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
def series_detail(series_id: str):
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    row = next((s for s in data["series"] if s["id"] == series_id), None)
    if not row:
        raise HTTPException(404, "没有这个系列")
    books = []
    for book in row.get("books") or []:
        slug = book_slug_of(book.get("title") or "", book.get("name") or "")
        local = BOOKS / series_id / slug / "book.json"
        ready = local.exists()
        if ready:
            enqueue_book(series_id, slug)
        books.append(
            {
                "title": book.get("title"),
                "name": book.get("name"),
                "number": book.get("number"),
                "slug": slug,
                "ready": ready,
                "readable": ready,
                "cover": f"/media/books/{series_id}/{slug}/pages/001.jpg" if ready else "",
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


def book_slug_of(title: str, name: str) -> str:
    raw = (title or name or "book").lower()
    out = [ch if ch.isalnum() else "-" for ch in raw]
    slug = "".join(out).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or name.lower()
