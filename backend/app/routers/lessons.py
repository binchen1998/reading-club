import json
import logging
import re

from fastapi import APIRouter, HTTPException, Query

from ..book_pages import split_chapters
from ..config import LESSONS
from ..gen_jobs import job_payload
from ..lesson_gen import page_lesson_exists, page_lesson_file
from ..lesson_worker import enqueue_lesson_job, is_generating
from ..remote_book import book_exists, load_book, load_one_page, page_image_url

router = APIRouter(prefix="/api")
logger = logging.getLogger("lesson_worker")
WORD_RE = re.compile(r"[A-Za-z']+")
CHAPTER_ID_RE = re.compile(r"^ch(\d+)$", re.I)
SENTENCE_END_RE = re.compile(r'(?:[.!?。！？…]|\.\.\.)["\'”’)]*$')


def _ends_with_sentence_punct(text: str) -> bool:
    return bool(SENTENCE_END_RE.search((text or "").rstrip()))


def merge_short_segments(segments: list, min_words: int = 3) -> list[str]:
    out: list[str] = []
    i = 0
    items = [str(s).strip() for s in segments or [] if str(s).strip()]
    while i < len(items):
        cur = items[i]
        while i + 1 < len(items):
            if _ends_with_sentence_punct(cur) and len(WORD_RE.findall(cur)) >= min_words:
                break
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
    if not book_exists(series_id, book_slug):
        raise HTTPException(404, "没有这本书")
    book = load_book(series_id, book_slug)
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
    for info in split_chapters(book.get("pages") or [], book.get("title") or ""):
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


def _read_page_lesson(series_id: str, book_slug: str, page: int) -> dict | None:
    path = page_lesson_file(series_id, book_slug, page)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _assemble_lesson(series_id: str, book_slug: str, book: dict) -> dict:
    word_bank: list[dict] = []
    phrase_bank: list[dict] = []
    beats = []
    for rec in book.get("pages") or []:
        page_no = int(rec.get("page") or 0)
        saved = _read_page_lesson(series_id, book_slug, page_no)
        beat = {
            "page": page_no,
            "explain": "",
            "words": [],
            "phrases": [],
            "segments": [],
            "generated": False,
        }
        if saved:
            picked = next(
                (row for row in (saved.get("beats") or []) if int(row.get("page") or 0) == page_no),
                None,
            )
            if picked is None and saved.get("beats"):
                picked = saved["beats"][0]
            if picked:
                beat.update(
                    {
                        "explain": picked.get("explain") or "",
                        "words": picked.get("words") or [],
                        "phrases": picked.get("phrases") or [],
                        "segments": picked.get("segments") or [],
                        "ocr": picked.get("ocr") or [],
                        "generated": True,
                    }
                )
            word_bank.extend(saved.get("word_bank") or [])
            phrase_bank.extend(saved.get("phrase_bank") or [])
        beats.append(beat)
    word_map = {str(item.get("en") or ""): item for item in word_bank if item.get("en")}
    phrase_map = {str(item.get("en") or ""): item for item in phrase_bank if item.get("en")}
    out = []
    for beat, rec in zip(beats, book.get("pages") or []):
        page_no = int(beat["page"])
        out.append(
            {
                **beat,
                "image": page_image_url(series_id, book_slug, page_no),
                "english": rec.get("english") or "",
                "translate": rec.get("translate") or "",
                "ocr": beat.get("ocr") or [],
                "word_items": [word_map[key] for key in beat.get("words") or [] if key in word_map],
                "phrase_items": [phrase_map[key] for key in beat.get("phrases") or [] if key in phrase_map],
                "segments": merge_short_segments(beat.get("segments") or []),
            }
        )
    return {
        "chapter": 1,
        "title": book.get("title") or book_slug,
        "title_zh": "",
        "beats": out,
        "word_bank": list(word_map.values()),
        "phrase_bank": list(phrase_map.values()),
    }


@router.get("/lessons/{series_id}/{book_slug}/{chapter_id}")
def lesson_detail(
    series_id: str,
    book_slug: str,
    chapter_id: str,
    check: bool = Query(False),
    page: int | None = Query(None),
):
    _chapter_num(chapter_id)
    if not book_exists(series_id, book_slug):
        raise HTTPException(404, "没有这本书")
    if check:
        if page is None:
            return {"exists": False}
        return {"exists": page_lesson_exists(series_id, book_slug, page), "page": page}
    book = load_book(series_id, book_slug)
    return {"lesson": _assemble_lesson(series_id, book_slug, book)}


@router.post("/lessons/{series_id}/{book_slug}/{chapter_id}/generate")
def lesson_generate(
    series_id: str,
    book_slug: str,
    chapter_id: str,
    page: int = Query(..., ge=0),
):
    chapter = _chapter_num(chapter_id)
    if not book_exists(series_id, book_slug):
        raise HTTPException(404, "没有这本书")
    if load_one_page(series_id, book_slug, page) is None:
        raise HTTPException(404, "没有这一页")
    if page_lesson_exists(series_id, book_slug, page):
        logger.info("单页讲解已存在 %s/%s p%s", series_id, book_slug, page)
        return {"exists": True, "job_id": "", "status": "done", "page": page}
    logger.info("收到生成单页讲解 %s/%s p%s", series_id, book_slug, page)
    job = enqueue_lesson_job(series_id, book_slug, chapter, page=page)
    return {**job_payload(job), "page": page}
