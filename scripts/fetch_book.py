"""下载书的基本页资源（页图 + 页 JSON + book.json）到本地。

不生成讲解、OCR、TTS；那些等用户打开阅读页后再由 worker 按需生成。
默认 8 路并行，已下完的书跳过，没下完的从缺页续传。
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.client import IncompleteRead
from pathlib import Path

from scripts.paths import BOOKS, CATALOG, SERIES, book_slug, pages_base

DEFAULT_WORKERS = 8
_print_lock = threading.Lock()
_download_gate = threading.Semaphore(DEFAULT_WORKERS)


def log(msg: str) -> None:
    with _print_lock:
        print(msg, flush=True)


def set_download_limit(workers: int) -> None:
    global _download_gate
    _download_gate = threading.Semaphore(max(1, workers))


def download(url: str, dest: Path, force: bool = False) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not force and dest.exists() and dest.stat().st_size > 200:
        return True
    parts = urllib.parse.urlsplit(url)
    encoded = urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, urllib.parse.quote(parts.path, safe="/"), parts.query, parts.fragment)
    )
    req = urllib.request.Request(encoded, headers={"User-Agent": "reading-club/1.0"})
    last_err: Exception | None = None
    with _download_gate:
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


def book_dest(series_id: str, book: dict) -> Path:
    return BOOKS / series_id / book_slug(book.get("title") or "", book.get("name") or "")


def is_book_complete(series_id: str, book: dict) -> bool:
    dest = book_dest(series_id, book)
    meta_path = dest / "book.json"
    if not meta_path.exists():
        return False
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    pages = meta.get("pages") or []
    if not pages:
        return False
    expected = int(book.get("num_pages") or 0)
    if not meta.get("complete") and (not expected or len(pages) < expected):
        return False
    if expected and len(pages) < expected:
        return False
    for rec in pages:
        image = dest / (rec.get("image") or "")
        if not image.exists() or image.stat().st_size < 200:
            return False
    return True


def _write_book_json(
    dest: Path,
    series_id: str,
    slug: str,
    book: dict,
    base: str,
    pages: list[dict],
    complete: bool = False,
) -> None:
    meta = {
        "series_id": series_id,
        "slug": slug,
        "title": book["title"],
        "name": book["name"],
        "cdn_pages": base,
        "page_count": len(pages),
        "complete": complete,
        "pages": pages,
    }
    tmp = dest / "book.json.tmp"
    tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(dest / "book.json")


def fetch_book(series_id: str, title_or_name: str, max_pages: int = 200, force: bool = False) -> Path:
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
        ok = download(f"{base}/{n}.jpg", jpg, force=force)
        if not ok:
            return n, False, {}
        download(f"{base}/{n}.json", js, force=force)
        download(f"{base}/{n}_paddle.json", pages_dir / f"{n:03d}_paddle.json", force=force)
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
    with ThreadPoolExecutor(max_workers=DEFAULT_WORKERS) as pool:
        n = 0
        while n < max_pages:
            batch = list(range(n, min(n + DEFAULT_WORKERS, max_pages)))
            futures = [pool.submit(one, i) for i in batch]
            missing = False
            for fut in as_completed(futures):
                idx, ok, rec = fut.result()
                if ok:
                    found[idx] = rec
                else:
                    missing = True
                    stop_at = min(stop_at, idx)
            pages = [found[i] for i in sorted(found) if i < stop_at]
            _write_book_json(dest, series_id, slug, book, base, pages, complete=False)
            if missing:
                break
            n += DEFAULT_WORKERS
    pages = [found[i] for i in sorted(found) if i < stop_at]
    _write_book_json(dest, series_id, slug, book, base, pages, complete=True)
    return dest


def _catalog_jobs(series_id: str = "") -> list[tuple[str, dict]]:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    jobs: list[tuple[str, dict]] = []
    for row in catalog.get("series") or []:
        if series_id and row["id"] != series_id:
            continue
        for book in row.get("books") or []:
            jobs.append((row["id"], book))
    return jobs


def _run_one(series_id: str, book: dict, skip_existing: bool, force: bool, index: int, total: int) -> Path:
    title = book.get("title") or book.get("name") or ""
    slug = book_slug(book.get("title") or "", book.get("name") or "")
    dest = book_dest(series_id, book)
    prefix = f"[{index}/{total}] {series_id}/{slug}"
    if skip_existing and not force and is_book_complete(series_id, book):
        log(f"{prefix} skip")
        return dest
    log(f"{prefix} fetch {title}")
    try:
        path = fetch_book(series_id, title, force=force)
        pages = 0
        meta = dest / "book.json"
        if meta.exists():
            try:
                pages = int(json.loads(meta.read_text(encoding="utf-8")).get("page_count") or 0)
            except json.JSONDecodeError:
                pages = 0
        log(f"{prefix} ok pages={pages}")
        return path
    except Exception as exc:
        log(f"{prefix} FAIL {exc}")
        return dest


def fetch_many(
    series_id: str = "",
    skip_existing: bool = True,
    force: bool = False,
    workers: int = DEFAULT_WORKERS,
) -> list[Path]:
    jobs = _catalog_jobs(series_id)
    workers = max(1, int(workers or DEFAULT_WORKERS))
    set_download_limit(workers)
    scope = series_id or "all"
    log(f"== {scope}  {len(jobs)} 本  workers={workers}  断点续传")
    done: list[Path] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [
            pool.submit(_run_one, sid, book, skip_existing, force, i, len(jobs))
            for i, (sid, book) in enumerate(jobs, start=1)
        ]
        for fut in as_completed(futs):
            done.append(fut.result())
    return done


def fetch_series(series_id: str, skip_existing: bool = True, force: bool = False, workers: int = DEFAULT_WORKERS) -> list[Path]:
    return fetch_many(series_id, skip_existing=skip_existing, force=force, workers=workers)


def fetch_all(skip_existing: bool = True, force: bool = False, workers: int = DEFAULT_WORKERS) -> list[Path]:
    return fetch_many("", skip_existing=skip_existing, force=force, workers=workers)


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="只下载页图 / 页 JSON / book.json，不跑讲解、OCR、TTS。默认 8 路并行，可断点续传。"
    )
    parser.add_argument("--series", default="", help="系列 id，如 FancyNancy。省略 --book 时下载整套")
    parser.add_argument("--book", default="", help="书名或 CDN name。省略则下载该系列全部书")
    parser.add_argument("--all", action="store_true", help="下载 catalog 里全部系列")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="并行路数，默认 8")
    parser.add_argument(
        "--force",
        action="store_true",
        help="已下完的书也重新下载",
    )
    args = parser.parse_args()
    skip = not args.force
    workers = max(1, args.workers)
    set_download_limit(workers)

    if args.all:
        paths = fetch_all(skip_existing=skip, force=args.force, workers=workers)
        print(f"done {len(paths)} books")
    elif args.series and args.book:
        print(fetch_book(args.series, args.book, force=args.force))
    elif args.series:
        paths = fetch_series(args.series, skip_existing=skip, force=args.force, workers=workers)
        print(f"done {len(paths)} books in {args.series}")
    else:
        parser.print_help()
        sys.exit(2)
