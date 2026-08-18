from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..assets import lookup_ocr, lookup_tts
from ..gen_jobs import job_payload
from ..lesson_worker import enqueue_ocr_job, enqueue_tts_job

router = APIRouter(prefix="/api/assets", tags=["assets"])


class TtsGenerateIn(BaseModel):
    text: str = Field(..., min_length=1)
    purpose: str = "讲解音频"


class OcrGenerateIn(BaseModel):
    series_id: str
    book_slug: str
    page: int = 0
    text: str = Field(..., min_length=1)
    purpose: str = "这一句的词框"


@router.get("/tts")
def tts_asset(
    text: str = Query(..., min_length=1),
    purpose: str = Query("讲解音频"),
    check: int = Query(0),
):
    value = text.strip()
    if not value:
        raise HTTPException(400, "文本不能为空")
    found = lookup_tts(value)
    if found:
        return found
    if check:
        return {"url": "", "exists": False, "created": False, "source": ""}
    job = enqueue_tts_job(value, purpose)
    return {"url": "", "exists": False, "created": False, "source": "", **job_payload(job)}


@router.post("/tts/generate")
def tts_generate(body: TtsGenerateIn):
    value = body.text.strip()
    found = lookup_tts(value)
    if found:
        return {"exists": True, "job_id": "", "status": "done", "result": found, **found}
    job = enqueue_tts_job(value, body.purpose)
    return job_payload(job)


@router.post("/ocr")
def ocr_asset(body: dict):
    series_id = str(body.get("series_id") or "").strip()
    book_slug = str(body.get("book_slug") or "").strip()
    text = str(body.get("text") or "").strip()
    purpose = str(body.get("purpose") or "这一句的词框")
    try:
        page = int(body.get("page") or 0)
    except (TypeError, ValueError):
        page = 0
    if not series_id or not book_slug or not text:
        raise HTTPException(400, "缺少书页或文本")
    found = lookup_ocr(series_id, book_slug, page, text)
    if found:
        return found
    if body.get("check"):
        return {"words": [], "exists": False, "created": False, "source": ""}
    job = enqueue_ocr_job(series_id, book_slug, page, text, purpose)
    return {"words": [], "exists": False, "created": False, "source": "", **job_payload(job)}


@router.post("/ocr/generate")
def ocr_generate(body: OcrGenerateIn):
    found = lookup_ocr(body.series_id, body.book_slug, body.page, body.text)
    if found:
        return {"exists": True, "job_id": "", "status": "done", "result": found, **found}
    job = enqueue_ocr_job(body.series_id, body.book_slug, body.page, body.text, body.purpose)
    return job_payload(job)
