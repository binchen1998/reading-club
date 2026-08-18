"""从每套书正文里挑一张封面，上传到七牛，并写出 covers.json。"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.config import BOOKS, CATALOG
from backend.app.qiniu_upload import (
    cdn_url,
    covers_json_key,
    qiniu_enabled,
    qiniu_put_bytes,
    series_cover_key,
)
from backend.app.remote_book import book_slug_of, catalog_series, page_image_bytes

# 每套书在正文里挑到的封面页（系列代表作 + 真正的封面页码）
COVER_PAGES = [
    {"id": "FlyGuy", "slug": "01-hi-fly-guy", "page": 0},
    {"id": "FrogAndToad", "slug": "frog-and-toad-are-friends", "page": 1},
    {"id": "FancyNancy", "slug": "fancy-nancy-and-the-boy-from-paris", "page": 1},
    {"id": "WinnieAndWilbur", "slug": "around-the-world", "page": 1},
    {"id": "MagicTreeHouse", "slug": "dinosaurs-before-dark", "page": 1},
    {"id": "CuriousGeorge", "slug": "curious-george", "page": 0},
    {"id": "NateTheGreat", "slug": "san-francisco-detective", "page": 1},
    {"id": "AToZ", "slug": "the-kidnapped-king", "page": 1},
    {"id": "CatAndMouse", "slug": "cat-and-mouse-in-a-haunted-house", "page": 1},
    {"id": "DragonMasters", "slug": "rise-of-the-earth-dragon", "page": 1},
]


def _local_cover(series_id: str, slug: str, page: int) -> bytes | None:
    path = BOOKS / series_id / slug / "pages" / f"{page:03d}.jpg"
    if path.exists():
        data = path.read_bytes()
        return data if data else None
    return None


def _cover_bytes(series_id: str, slug: str, page: int) -> bytes:
    data = _local_cover(series_id, slug, page) or page_image_bytes(series_id, slug, page)
    if not data:
        raise RuntimeError(f"找不到封面 {series_id}/{slug} p{page}")
    return data


def main() -> None:
    if not qiniu_enabled():
        raise SystemExit("七牛未配置，无法上传封面")
    catalog = {row["id"]: row for row in json.loads(CATALOG.read_text(encoding="utf-8")).get("series") or []}
    items = []
    for pick in COVER_PAGES:
        series_id = pick["id"]
        slug = pick["slug"]
        page = int(pick["page"])
        row = catalog.get(series_id) or catalog_series(series_id) or {}
        if row.get("books") and not any(
            book_slug_of(book.get("title") or "", book.get("name") or "") == slug for book in row["books"]
        ):
            raise RuntimeError(f"书目里没有 {series_id}/{slug}")
        print(f"[cover] {series_id} {slug} p{page}", flush=True)
        image = _cover_bytes(series_id, slug, page)
        key = series_cover_key(series_id)
        qiniu_put_bytes(key, image, mime_type="image/jpeg")
        cover_url = cdn_url(key)
        items.append(
            {
                "id": series_id,
                "title": row.get("title") or series_id,
                "cover": cover_url,
                "bookSlug": slug,
                "page": page,
            }
        )
        print(f"  -> {cover_url}", flush=True)
    payload = {
        "updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "series": items,
    }
    json_key = covers_json_key()
    qiniu_put_bytes(
        json_key,
        json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        mime_type="application/json",
    )
    print(f"[covers.json] {cdn_url(json_key)}", flush=True)


if __name__ == "__main__":
    main()
