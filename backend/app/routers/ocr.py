from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from ..assets import lookup_ocr
from ..config import BOOKS
from ..gen_jobs import job_payload
from ..lesson_worker import enqueue_ocr_job

router = APIRouter(prefix="/api")


class WordOcrBody(BaseModel):
    series_id: str
    book_slug: str
    page: int = Field(..., ge=0)
    text: str = Field(..., min_length=1)
    purpose: str = "这一句的词框"
    check: bool = False


@router.post("/ocr/words")
def ocr_words(body: WordOcrBody):
    pages_dir = BOOKS / body.series_id / body.book_slug / "pages"
    if not pages_dir.exists():
        raise HTTPException(404, "书页不存在")
    found = lookup_ocr(body.series_id, body.book_slug, body.page, body.text)
    if found:
        return found
    if body.check:
        return {"words": [], "exists": False, "created": False, "source": ""}
    job = enqueue_ocr_job(body.series_id, body.book_slug, body.page, body.text, body.purpose)
    return {"words": [], "exists": False, "created": False, "source": "", **job_payload(job)}


@router.post("/ocr/words/generate")
def ocr_words_generate(body: WordOcrBody):
    pages_dir = BOOKS / body.series_id / body.book_slug / "pages"
    if not pages_dir.exists():
        raise HTTPException(404, "书页不存在")
    found = lookup_ocr(body.series_id, body.book_slug, body.page, body.text)
    if found:
        return {"exists": True, "job_id": "", "status": "done", "result": found, **found}
    job = enqueue_ocr_job(body.series_id, body.book_slug, body.page, body.text, body.purpose)
    return job_payload(job)
