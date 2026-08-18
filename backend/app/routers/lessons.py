import json
import re

from fastapi import APIRouter, HTTPException

from ..config import BOOKS, LESSONS
from ..ocr import load_page_ocr

router = APIRouter(prefix="/api")
WORD_RE = re.compile(r"[A-Za-z']+")


def merge_short_segments(segments: list, min_words: int = 3) -> list[str]:
    out: list[str] = []
    i = 0
    items = [str(s).strip() for s in segments or [] if str(s).strip()]
    while i < len(items):
        cur = items[i]
        while len(WORD_RE.findall(cur)) < min_words and i + 1 < len(items):
            i += 1
            cur = f"{cur} {items[i]}".strip()
        out.append(cur)
        i += 1
    return out


@router.get("/books/{series_id}/{book_slug}")
def book_detail(series_id: str, book_slug: str):
    path = BOOKS / series_id / book_slug / "book.json"
    if not path.exists():
        raise HTTPException(404, "书还没下载到本地")
    book = json.loads(path.read_text(encoding="utf-8"))
    lesson_dir = LESSONS / series_id / book_slug
    chapters = []
    if lesson_dir.exists():
        for file in sorted(lesson_dir.glob("ch*.json")):
            lesson = json.loads(file.read_text(encoding="utf-8"))
            chapters.append(
                {
                    "id": file.stem,
                    "chapter": lesson.get("chapter"),
                    "title": lesson.get("title"),
                    "title_zh": lesson.get("title_zh"),
                    "open": True,
                }
            )
    return {"book": book, "chapters": chapters}


@router.get("/lessons/{series_id}/{book_slug}/{chapter_id}")
def lesson_detail(series_id: str, book_slug: str, chapter_id: str):
    path = LESSONS / series_id / book_slug / f"{chapter_id}.json"
    if not path.exists():
        raise HTTPException(404, "这一章还没开放")
    lesson = json.loads(path.read_text(encoding="utf-8"))
    book = json.loads((BOOKS / series_id / book_slug / "book.json").read_text(encoding="utf-8"))
    pages = {p["page"]: p for p in book.get("pages") or []}
    word_map = {w["en"]: w for w in lesson.get("word_bank") or []}
    phrase_map = {p["en"]: p for p in lesson.get("phrase_bank") or []}
    beats = []
    for beat in lesson.get("beats") or []:
        page = pages.get(beat["page"]) or {}
        page_no = int(beat["page"])
        beats.append(
            {
                **beat,
                "image": f"/media/books/{series_id}/{book_slug}/{page.get('image')}",
                "english": page.get("english") or "",
                "translate": page.get("translate") or "",
                "ocr": load_page_ocr(BOOKS / series_id / book_slug / "pages", page_no),
                "word_items": [word_map[k] for k in beat.get("words") or [] if k in word_map],
                "phrase_items": [phrase_map[k] for k in beat.get("phrases") or [] if k in phrase_map],
                "segments": merge_short_segments(beat.get("segments") or []),
            }
        )
    return {
        "lesson": {
            **lesson,
            "beats": beats,
            "word_bank": lesson.get("word_bank") or [],
            "phrase_bank": lesson.get("phrase_bank") or [],
        }
    }
