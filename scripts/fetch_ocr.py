"""给已经下载的书页补拉 Paddle OCR 框。"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from scripts.fetch_book import download
from scripts.paths import BOOKS


def main() -> None:
    for book_json in BOOKS.rglob("book.json"):
        meta = json.loads(book_json.read_text(encoding="utf-8"))
        base = meta.get("cdn_pages") or ""
        pages_dir = book_json.parent / "pages"
        if not base:
            continue
        print(f"[ocr] {meta.get('slug')} {meta.get('page_count')} pages", flush=True)

        def one(n: int) -> None:
            download(f"{base}/{n}_paddle.json", pages_dir / f"{n:03d}_paddle.json")

        with ThreadPoolExecutor(max_workers=8) as pool:
            futs = [pool.submit(one, p["page"]) for p in meta.get("pages") or []]
            for fut in as_completed(futs):
                fut.result()


if __name__ == "__main__":
    main()
