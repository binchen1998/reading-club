"""读本地 book.json，切章节，并标出跨页未写完的句子。"""

from __future__ import annotations

import json
import re
from pathlib import Path

from scripts.paths import BOOKS, CATALOG, book_slug

CHAPTER_HEAD = re.compile(
    r"^\s*Chapter\s+"
    r"(One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|"
    r"Eleven|Twelve|Thirteen|Fourteen|Fifteen|"
    r"\d+)\b",
    re.I,
)
ORDINALS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
}
SENT_END = re.compile(r'[.!?…]["”\'»」』]?\s*$')
SKIP_HINT = re.compile(
    r"copyright|isbn|all rights reserved|manufactured in|remembering\n|yearling book",
    re.I,
)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\n", " ")).strip()


def sentence_complete(text: str) -> bool:
    value = _norm(text)
    if not value:
        return True
    return bool(SENT_END.search(value))


def page_tail(text: str, words: int = 28) -> str:
    value = _norm(text)
    parts = value.split()
    return " ".join(parts[-words:])


def page_head(text: str, words: int = 28) -> str:
    value = _norm(text)
    parts = value.split()
    return " ".join(parts[:words])


def is_story_page(page: dict) -> bool:
    english = (page.get("english") or "").strip()
    if not english:
        return False
    if CHAPTER_HEAD.search(english):
        return True
    if SKIP_HINT.search(english) and len(english) > 400:
        return False
    if page.get("has_text") is False:
        return False
    return len(_norm(english).split()) >= 8


def chapter_number(english: str) -> int | None:
    match = CHAPTER_HEAD.search(english or "")
    if not match:
        return None
    raw = match.group(1).lower()
    if raw.isdigit():
        return int(raw)
    return ORDINALS.get(raw)


def load_book(series_id: str, slug: str) -> dict:
    path = BOOKS / series_id / slug / "book.json"
    if not path.exists():
        raise FileNotFoundError(f"书不在本地：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def annotate_pages(pages: list[dict]) -> list[dict]:
    rows: list[dict] = []
    story = [p for p in pages if is_story_page(p)]
    for i, page in enumerate(story):
        prev_en = (story[i - 1].get("english") or "") if i else ""
        next_en = (story[i + 1].get("english") or "") if i + 1 < len(story) else ""
        english = page.get("english") or ""
        rows.append(
            {
                "page": int(page["page"]),
                "english": english,
                "translate": page.get("translate") or "",
                "carry_from_prev": not sentence_complete(prev_en),
                "continues_on_next": not sentence_complete(english),
                "prev_page_tail": page_tail(prev_en) if prev_en and not sentence_complete(prev_en) else "",
                "next_page_head": page_head(next_en) if next_en and not sentence_complete(english) else "",
            }
        )
    return rows


def split_chapters(pages: list[dict]) -> list[dict]:
    annotated = annotate_pages(pages)
    chapters: list[dict] = []
    current: dict | None = None
    for row in annotated:
        num = chapter_number(row["english"])
        if num is not None:
            if current:
                chapters.append(current)
            title_line = _norm(row["english"]).split(".")[0][:80]
            current = {"chapter": num, "title": title_line, "pages": [row]}
            continue
        if current is None:
            continue
        current["pages"].append(row)
    if current:
        chapters.append(current)
    return chapters


def load_catalog() -> dict:
    return json.loads(Path(CATALOG).read_text(encoding="utf-8"))


def list_local_books(series: str | None = None, book: str | None = None) -> list[tuple[str, str, dict]]:
    catalog = load_catalog()
    wanted_series = (series or "").strip()
    wanted_book = (book or "").strip().lower()
    found: list[tuple[str, str, dict]] = []
    for item in catalog.get("series") or []:
        series_id = item.get("id") or ""
        if wanted_series and series_id.lower() != wanted_series.lower():
            continue
        for raw in item.get("books") or []:
            slug = book_slug(raw.get("title") or "", raw.get("name") or "")
            title = (raw.get("title") or "").strip()
            name = (raw.get("name") or "").strip()
            if wanted_book and wanted_book not in {slug.lower(), title.lower(), name.lower()}:
                continue
            book_path = BOOKS / series_id / slug / "book.json"
            if not book_path.exists():
                continue
            payload = json.loads(book_path.read_text(encoding="utf-8"))
            found.append((series_id, slug, payload))
    if wanted_series or wanted_book:
        if not found:
            raise SystemExit(f"没有匹配的本地书：series={series!r} book={book!r}")
    return found


def clip_segment_to_page(segment: str, page_english: str) -> str:
    """丢掉误带上的上一页/下一页单词，保证朗读段落在本页。"""
    text = _norm(segment)
    page = _norm(page_english)
    if not text or not page:
        return segment.strip()
    if text.lower() in page.lower():
        return text
    words = text.split()
    for i in range(len(words)):
        cand = " ".join(words[i:])
        if len(cand) >= 8 and cand.lower() in page.lower():
            return cand
    for i in range(len(words), 0, -1):
        cand = " ".join(words[:i])
        if len(cand) >= 8 and cand.lower() in page.lower():
            return cand
    return text
