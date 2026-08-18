"""下载全部章节书系列书目（只存元数据，不下载全书图片）。"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

from scripts.paths import CATALOG, CONTENT, SERIES, catalog_url


def get_json(url: str):
    parts = urllib.parse.urlsplit(url)
    path = urllib.parse.quote(parts.path, safe="/")
    encoded = urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))
    req = urllib.request.Request(encoded, headers={"User-Agent": "reading-club/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    CONTENT.mkdir(parents=True, exist_ok=True)
    catalog = {"series": []}
    for series in SERIES:
        url = catalog_url(series)
        print(f"[catalog] {series['id']} {url}", flush=True)
        try:
            books = get_json(url)
        except Exception as exc:  # noqa: BLE001
            print(f"  fail: {exc}", flush=True)
            books = []
        catalog["series"].append(
            {
                **series,
                "catalog_url": url,
                "book_count": len(books) if isinstance(books, list) else 0,
                "books": books if isinstance(books, list) else [],
            }
        )
        print(f"  books={len(books) if isinstance(books, list) else 0}", flush=True)
    CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {CATALOG}")


if __name__ == "__main__":
    main()
