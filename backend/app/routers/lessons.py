import json
import re

from fastapi import APIRouter, HTTPException, Query

from ..book_pages import split_chapters
from ..config import BOOKS, LESSONS
from ..gen_jobs import job_payload
from ..lesson_gen import lesson_exists
from ..lesson_worker import enqueue_book, enqueue_lesson_job, is_generating
from ..ocr import load_page_ocr

router = APIRouter(prefix="/api")
WORD_RE = re.compile(r"[A-Za-z']+")
CHAPTER_ID_RE = re.compile(r"^ch(\d+)$", re.I)


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


def _chapter_num(chapter_id: str) -> int:
    match = CHAPTER_ID_RE.fullmatch((chapter_id or "").strip())
    if not match:
        raise HTTPException(404, "这一章还没开放")
    return int(match.group(1))


@router.get("/books/{series_id}/{book_slug}")
def book_detail(series_id: str, book_slug: str):
    path = BOOKS / series_id / book_slug / "book.json"
    if not path.exists():
        raise HTTPException(404, "书还没下载到本地")
    book = json.loads(path.read_text(encoding="utf-8"))
    lesson_dir = LESSONS / series_id / book_slug
    by_id: dict[str, dict] = {}
    if lesson_dir.exists():
        for file in sorted(lesson_dir.glob("ch*.json")):
            lesson = json.loads(file.read_text(encoding="utf-8"))
            by_id[file.stem] = {
                "id": file.stem,
                "chapter": lesson.get("chapter"),
                "title": lesson.get("title"),
                "title_zh": lesson.get("title_zh"),
                "open": True,
                "generated": True,
                "generating": False,
            }
    for info in split_chapters(book.get("pages") or []):
        num = int(info.get("chapter") or 0)
        if not num:
            continue
        cid = f"ch{num:02d}"
        if cid in by_id:
            continue
        by_id[cid] = {
            "id": cid,
            "chapter": num,
            "title": info.get("title") or f"Chapter {num}",
            "title_zh": "",
            "open": True,
            "generated": False,
            "generating": is_generating(series_id, book_slug, num),
        }
    chapters = sorted(by_id.values(), key=lambda row: int(row.get("chapter") or 0))
    return {"book": book, "chapters": chapters}


@router.get("/lessons/{series_id}/{book_slug}/{chapter_id}")
def lesson_detail(
    series_id: str,
    book_slug: str,
    chapter_id: str,
    check: bool = Query(False),
):
    chapter = _chapter_num(chapter_id)
    if check:
        return {"exists": lesson_exists(series_id, book_slug, chapter)}
    if not lesson_exists(series_id, book_slug, chapter):
        raise HTTPException(409, "课稿尚未生成")
    lesson = json.loads((LESSONS / series_id / book_slug / f"ch{chapter:02d}.json").read_text(encoding="utf-8"))
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


@router.post("/lessons/{series_id}/{book_slug}/{chapter_id}/generate")
def lesson_generate(series_id: str, book_slug: str, chapter_id: str):
    chapter = _chapter_num(chapter_id)
    book_path = BOOKS / series_id / book_slug / "book.json"
    if not book_path.exists():
        raise HTTPException(404, "书还没下载到本地")
    if lesson_exists(series_id, book_slug, chapter):
        return {"exists": True, "job_id": "", "status": "done"}
    job = enqueue_lesson_job(series_id, book_slug, chapter)
    enqueue_book(series_id, book_slug)
    return job_payload(job)
