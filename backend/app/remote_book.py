"""直接复用原站 CDN 的页图 / 页 JSON，不把书文件下到本地。"""

from __future__ import annotations

import json
import logging
import threading
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache

from .config import CATALOG, STORAGE

logger = logging.getLogger("remote_book")

CDN_UA = "reading-club/1.0"
MAX_PAGES = 200
META_DIR = STORAGE / "book-meta"
_guard = threading.Lock()
_books: dict[str, dict] = {}


def book_slug_of(title: str, name: str) -> str:
    raw = (title or name or "book").lower()
    out = [ch if ch.isalnum() else "-" for ch in raw]
    slug = "".join(out).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or (name or "book").lower()


def _encode(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, urllib.parse.quote(parts.path, safe="/"), parts.query, parts.fragment)
    )


def fetch_bytes(url: str) -> bytes | None:
    req = urllib.request.Request(_encode(url), headers={"User-Agent": CDN_UA})
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            data = resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return None
    return data if data and len(data) > 20 else None


def fetch_json(url: str) -> dict | None:
    raw = fetch_bytes(url)
    if not raw:
        return None
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


@lru_cache(maxsize=1)
def load_catalog() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def catalog_series(series_id: str) -> dict | None:
    return next((row for row in (load_catalog().get("series") or []) if row.get("id") == series_id), None)


def catalog_book(series_id: str, book_slug: str) -> dict | None:
    row = catalog_series(series_id)
    if not row:
        return None
    for book in row.get("books") or []:
        if book_slug_of(book.get("title") or "", book.get("name") or "") == book_slug:
            return book
    return None


def book_exists(series_id: str, book_slug: str) -> bool:
    return catalog_book(series_id, book_slug) is not None


def pages_base_url(series_id: str, book_name: str) -> str:
    from scripts.paths import pages_base

    row = catalog_series(series_id) or {}
    return pages_base(row, book_name)


def page_urls(series_id: str, book_slug: str, page: int) -> dict[str, str]:
    book = catalog_book(series_id, book_slug) or {}
    base = pages_base_url(series_id, book.get("name") or "")
    return {
        "image": f"{base}/{page}.jpg",
        "json": f"{base}/{page}.json",
        "paddle": f"{base}/{page}_paddle.json",
    }


def page_image_url(series_id: str, book_slug: str, page: int) -> str:
    return f"/media/cdn/{series_id}/{book_slug}/{int(page)}.jpg"


def page_image_bytes(series_id: str, book_slug: str, page: int) -> bytes | None:
    return fetch_bytes(page_urls(series_id, book_slug, page)["image"])


def page_paddle(series_id: str, book_slug: str, page: int):
    return fetch_json(page_urls(series_id, book_slug, page)["paddle"])


def load_one_page(series_id: str, book_slug: str, page: int) -> dict | None:
    if not book_exists(series_id, book_slug):
        return None
    n = int(page)
    payload = fetch_json(page_urls(series_id, book_slug, n)["json"])
    if payload is None:
        return None
    english = (payload.get("学习内容") or "").strip()
    return {
        "page": n,
        "image": page_urls(series_id, book_slug, n)["image"],
        "json": page_urls(series_id, book_slug, n)["json"],
        "guide": (payload.get("导读") or "").strip(),
        "english": english,
        "translate": (payload.get("翻译") or "").strip(),
        "has_text": bool(english),
    }


def _cache_path(series_id: str, book_slug: str):
    return META_DIR / series_id / f"{book_slug}.json"


def peek_book(series_id: str, book_slug: str) -> dict | None:
    key = f"{series_id}/{book_slug}"
    with _guard:
        cached = _books.get(key)
    if cached:
        return cached
    path = _cache_path(series_id, book_slug)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict) and data.get("pages"):
        with _guard:
            _books[key] = data
        return data
    return None


def _one_page(base: str, n: int) -> tuple[int, dict | None]:
    payload = fetch_json(f"{base}/{n}.json")
    if payload is None:
        return n, None
    english = (payload.get("学习内容") or "").strip()
    rec = {
        "page": n,
        "image": f"{base}/{n}.jpg",
        "json": f"{base}/{n}.json",
        "guide": (payload.get("导读") or "").strip(),
        "english": english,
        "translate": (payload.get("翻译") or "").strip(),
        "has_text": bool(english),
    }
    return n, rec


def _fetch_book(series_id: str, book_slug: str) -> dict:
    book = catalog_book(series_id, book_slug)
    if not book:
        raise FileNotFoundError(f"书目里没有 {series_id}/{book_slug}")
    base = pages_base_url(series_id, book.get("name") or "")
    logger.info("开始拉原站书页 %s/%s %s", series_id, book_slug, base)
    found: dict[int, dict] = {}
    stop_at = MAX_PAGES
    with ThreadPoolExecutor(max_workers=8) as pool:
        n = 0
        while n < MAX_PAGES:
            batch = list(range(n, min(n + 8, MAX_PAGES)))
            missing = False
            for fut in as_completed([pool.submit(_one_page, base, i) for i in batch]):
                idx, rec = fut.result()
                if rec:
                    found[idx] = rec
                else:
                    missing = True
                    stop_at = min(stop_at, idx)
            logger.info("原站书页 %s/%s 已取 %s 页", series_id, book_slug, len(found))
            if missing:
                if n == 0 and stop_at == 0:
                    stop_at = MAX_PAGES
                    n = 1
                    continue
                break
            n += 8
    pages = [found[i] for i in sorted(found) if i < stop_at]
    logger.info("原站书页完成 %s/%s pages=%s", series_id, book_slug, len(pages))
    return {
        "series_id": series_id,
        "slug": book_slug,
        "title": book.get("title") or book_slug,
        "name": book.get("name") or "",
        "cdn_pages": base,
        "page_count": len(pages),
        "pages": pages,
    }


def load_book(series_id: str, book_slug: str) -> dict:
    cached = peek_book(series_id, book_slug)
    if cached:
        logger.info("使用缓存书页 %s/%s pages=%s", series_id, book_slug, len(cached.get("pages") or []))
        return cached
    data = _fetch_book(series_id, book_slug)
    key = f"{series_id}/{book_slug}"
    path = _cache_path(series_id, book_slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    with _guard:
        _books[key] = data
    return data
