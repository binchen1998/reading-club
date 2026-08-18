import json

from fastapi import APIRouter, HTTPException

from ..config import BOOKS, CATALOG

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
                "readable": bool(row.get("readable")),
                "book_count": row.get("book_count") or len(row.get("books") or []),
                "cover": f"/media/books/NateTheGreat/hungry-book-club/pages/001.jpg"
                if row["id"] == "NateTheGreat"
                else "",
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
        slug = _slug(book.get("title") or "", book.get("name") or "")
        local = BOOKS / series_id / slug / "book.json"
        ready = local.exists()
        books.append(
            {
                "title": book.get("title"),
                "name": book.get("name"),
                "number": book.get("number"),
                "slug": slug,
                "ready": ready,
                "readable": bool(row.get("readable")) and ready,
                "cover": f"/media/books/{series_id}/{slug}/pages/001.jpg" if ready else "",
            }
        )
    return {"series": {"id": row["id"], "title": row["title"], "readable": row.get("readable")}, "books": books}


def _slug(title: str, name: str) -> str:
    raw = (title or name or "book").lower()
    out = [ch if ch.isalnum() else "-" for ch in raw]
    slug = "".join(out).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or name.lower()
