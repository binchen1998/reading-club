from pathlib import Path

from scripts.cdn import SERIES, catalog_url as _catalog_url
from scripts.cdn import pages_base as _pages_base

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
CATALOG = CONTENT / "catalog.json"
BOOKS = CONTENT / "books"
LESSONS = CONTENT / "lessons"


def catalog_url(series: dict | str) -> str:
    if isinstance(series, dict):
        return _catalog_url(series["level_name"])
    return _catalog_url(series)


def pages_base(series: dict | str, book_name: str = "") -> str:
    if isinstance(series, dict):
        return _pages_base(series["level_name"], book_name)
    return _pages_base(series, book_name)


def book_slug(title: str, name: str) -> str:
    raw = (title or name or "book").lower()
    out = [ch if ch.isalnum() else "-" for ch in raw]
    slug = "".join(out).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or name.lower()
