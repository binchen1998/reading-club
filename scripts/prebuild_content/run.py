"""预生成课稿、讲解 TTS、朗读词框。

用法（仓库根目录）:
  $env:PYTHONPATH = "D:\\git\\reading-club"
  python -m scripts.prebuild_content --all
  python -m scripts.prebuild_content --series NateTheGreat
  python -m scripts.prebuild_content --series NateTheGreat --book hungry-book-club
  python -m scripts.prebuild_content --series NateTheGreat --book "Hungry Book Club" --chapter 1
  python -m scripts.prebuild_content --series NateTheGreat --book hungry-book-club --only tts
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.paths import LESSONS
from scripts.prebuild_content.assets_gen import generate_ocr, generate_tts
from scripts.prebuild_content.lesson_llm import generate_chapter_lesson_full
from scripts.prebuild_content.pages import list_local_books, load_book, split_chapters

logger = logging.getLogger("prebuild_content")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="预生成课稿 / TTS / OCR")
    parser.add_argument("--all", action="store_true", help="处理所有已下载到本地的书")
    parser.add_argument("--series", default="", help="系列 id，如 NateTheGreat")
    parser.add_argument("--book", default="", help="书 slug / 书名 / CDN name")
    parser.add_argument("--chapter", type=int, default=0, help="只生成某一章，如 1")
    parser.add_argument(
        "--only",
        choices=["all", "lesson", "tts", "ocr"],
        default="all",
        help="只跑其中一类；默认课稿+TTS+OCR",
    )
    parser.add_argument("--force", action="store_true", help="已有课稿也重新生成")
    return parser.parse_args()


def lesson_path(series_id: str, slug: str, chapter: int) -> Path:
    return LESSONS / series_id / slug / f"ch{chapter:02d}.json"


def write_lesson(path: Path, lesson: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(lesson, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def process_book(
    series_id: str,
    slug: str,
    book: dict,
    *,
    chapter: int,
    only: str,
    force: bool,
) -> None:
    chapters = split_chapters(book.get("pages") or [], book.get("title") or "")
    if chapter:
        chapters = [c for c in chapters if int(c.get("chapter") or 0) == chapter]
        if not chapters:
            print(f"[skip] {series_id}/{slug} 没有第 {chapter} 章", flush=True)
            return
    if not chapters:
        print(f"[skip] {series_id}/{slug} 没有可读页", flush=True)
        return

    for info in chapters:
        num = int(info["chapter"])
        dest = lesson_path(series_id, slug, num)
        label = f"{series_id}/{slug}/ch{num:02d}"
        lesson = None
        need_lesson = only in ("all", "lesson")
        if dest.exists() and not force:
            lesson = json.loads(dest.read_text(encoding="utf-8"))
            print(f"[lesson] {label} 已存在，跳过生成（--force 可重做）", flush=True)
        elif need_lesson:
            pages = info.get("pages") or []
            print(f"[lesson] {label} 正在用 AI 生成，页数={len(pages)}", flush=True)
            lesson = generate_chapter_lesson_full(info)
            write_lesson(dest, lesson)
            print(f"[lesson] {label} 已写入 {dest}", flush=True)
        elif dest.exists():
            lesson = json.loads(dest.read_text(encoding="utf-8"))
        else:
            print(f"[skip] {label} 还没有课稿，先跑 --only lesson 或 --only all", flush=True)
            continue

        if only in ("all", "tts"):
            generate_tts(lesson, label)
        if only in ("all", "ocr"):
            generate_ocr(series_id, slug, lesson, label)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()
    if not args.all and not args.series and not args.book:
        raise SystemExit("请指定 --all，或 --series，或 --series + --book")
    series = args.series if not args.all else ""
    book = args.book if not args.all else ""
    targets = list_local_books(series or None, book or None)
    print(f"[prebuild] {len(targets)} 本书 only={args.only}", flush=True)
    for series_id, slug, payload in targets:
        print(f"==> {series_id}/{slug}", flush=True)
        process_book(
            series_id,
            slug,
            payload if payload.get("pages") else load_book(series_id, slug),
            chapter=args.chapter,
            only=args.only,
            force=args.force,
        )
    print("[prebuild] done", flush=True)


if __name__ == "__main__":
    main()
