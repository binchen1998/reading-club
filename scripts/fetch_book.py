"""下载书的基本页资源（页图 + 页 JSON + book.json）到本地。

不生成讲解、OCR、TTS；那些等用户打开阅读页后再由 worker 按需生成。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.client import IncompleteRead
from pathlib import Path

from scripts.paths import BOOKS, CATALOG, SERIES, book_slug, pages_base


def download(url: str, dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 200:
        return True
    parts = urllib.parse.urlsplit(url)
    encoded = urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, urllib.parse.quote(parts.path, safe="/"), parts.query, parts.fragment)
    )
    req = urllib.request.Request(encoded, headers={"User-Agent": "reading-club/1.0"})
    last_err: Exception | None = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=40) as resp:
                dest.write_bytes(resp.read())
            return True
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return False
            last_err = exc
        except (urllib.error.URLError, TimeoutError, ConnectionError, IncompleteRead) as exc:
            last_err = exc
        if dest.exists() and dest.stat().st_size < 200:
            dest.unlink()
    if last_err:
        raise last_err
    return False


def find_series(series_id: str) -> dict:
    return next(s for s in SERIES if s["id"] == series_id)


def find_book(series_id: str, title_or_name: str) -> dict:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    series = next(s for s in catalog["series"] if s["id"] == series_id)
    key = title_or_name.lower().strip()
    for book in series["books"]:
        if key in (book.get("title") or "").lower() or key == (book.get("name") or "").lower():
            return book
    raise KeyError(title_or_name)


def fetch_book(series_id: str, title_or_name: str, max_pages: int = 200) -> Path:
    series = find_series(series_id)
    book = find_book(series_id, title_or_name)
    slug = book_slug(book["title"], book["name"])
    dest = BOOKS / series_id / slug
    dest.mkdir(parents=True, exist_ok=True)
    pages_dir = dest / "pages"
    base = pages_base(series, book["name"])
    def one(n: int) -> tuple[int, bool, dict]:
        jpg = pages_dir / f"{n:03d}.jpg"
        js = pages_dir / f"{n:03d}.json"
        ok = download(f"{base}/{n}.jpg", jpg)
        if not ok:
            return n, False, {}
        download(f"{base}/{n}.json", js)
        download(f"{base}/{n}_paddle.json", pages_dir / f"{n:03d}_paddle.json")
        payload = {}
        if js.exists():
            try:
                payload = json.loads(js.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                payload = {}
        english = (payload.get("学习内容") or "").strip()
        rec = {
            "page": n,
            "image": f"pages/{n:03d}.jpg",
            "json": f"pages/{n:03d}.json" if js.exists() else "",
            "guide": (payload.get("导读") or "").strip(),
            "english": english,
            "translate": (payload.get("翻译") or "").strip(),
            "has_text": bool(english),
        }
        return n, True, rec

    found: dict[int, dict] = {}
    stop_at = max_pages
    with ThreadPoolExecutor(max_workers=8) as pool:
        # first probe in batches so we stop after first missing page
        n = 0
        while n < max_pages:
            batch = list(range(n, min(n + 8, max_pages)))
            futures = [pool.submit(one, i) for i in batch]
            missing = False
            for fut in as_completed(futures):
                idx, ok, rec = fut.result()
                if ok:
                    found[idx] = rec
                    preview = rec["english"][:48].encode("gbk", "replace").decode("gbk")
                    print(f"  p{idx:03d} text={int(rec['has_text'])} {preview}", flush=True)
                else:
                    missing = True
                    stop_at = min(stop_at, idx)
            if missing:
                break
            n += 8
    pages = [found[i] for i in sorted(found) if i < stop_at]
    meta = {
        "series_id": series_id,
        "slug": slug,
        "title": book["title"],
        "name": book["name"],
        "cdn_pages": base,
        "page_count": len(pages),
        "pages": pages,
    }
    (dest / "book.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return dest


def _catalog_series(series_id: str) -> dict:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    row = next((s for s in catalog["series"] if s["id"] == series_id), None)
    if not row:
        raise KeyError(series_id)
    return row


def fetch_series(series_id: str, skip_existing: bool = True) -> list[Path]:
    row = _catalog_series(series_id)
    books = row.get("books") or []
    print(f"== {series_id}  {row.get('title')}  ({len(books)} 本)", flush=True)
    done: list[Path] = []
    for book in books:
        title = book.get("title") or book.get("name") or ""
        slug = book_slug(book.get("title") or "", book.get("name") or "")
        dest = BOOKS / series_id / slug / "book.json"
        if skip_existing and dest.exists():
            print(f"  skip {slug}（已有 book.json）", flush=True)
            done.append(dest.parent)
            continue
        print(f"  fetch {title}", flush=True)
        try:
            done.append(fetch_book(series_id, title))
        except Exception as exc:
            print(f"  FAIL {title}: {exc}", flush=True)
    return done


def fetch_all(skip_existing: bool = True) -> list[Path]:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    done: list[Path] = []
    for row in catalog.get("series") or []:
        done.extend(fetch_series(row["id"], skip_existing=skip_existing))
    return done


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="只下载页图 / 页 JSON / book.json，不跑讲解、OCR、TTS。"
    )
    parser.add_argument("--series", default="", help="系列 id，如 FancyNancy。省略 --book 时下载整套")
    parser.add_argument("--book", default="", help="书名或 CDN name。省略则下载该系列全部书")
    parser.add_argument("--all", action="store_true", help="下载 catalog 里全部系列")
    parser.add_argument(
        "--force",
        action="store_true",
        help="已有 book.json 也重新下载",
    )
    args = parser.parse_args()
    skip = not args.force

    if args.all:
        paths = fetch_all(skip_existing=skip)
        print(f"done {len(paths)} books")
    elif args.series and args.book:
        print(fetch_book(args.series, args.book))
    elif args.series:
        paths = fetch_series(args.series, skip_existing=skip)
        print(f"done {len(paths)} books in {args.series}")
    else:
        parser.print_help()
        sys.exit(2)
