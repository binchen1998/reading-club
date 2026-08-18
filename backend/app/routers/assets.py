from fastapi import APIRouter, HTTPException, Query

from ..assets import ensure_ocr, ensure_tts, lookup_ocr, lookup_tts

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.get("/tts")
def tts_asset(
    text: str = Query(..., min_length=1),
    purpose: str = Query("讲解音频"),
    check: int = Query(0),
):
    value = text.strip()
    if not value:
        raise HTTPException(400, "文本不能为空")
    if check:
        found = lookup_tts(value)
        return found or {"url": "", "exists": False, "created": False, "source": ""}
    return ensure_tts(value, purpose)


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
    if body.get("check"):
        found = lookup_ocr(series_id, book_slug, page, text)
        return found or {"words": [], "exists": False, "created": False, "source": ""}
    return ensure_ocr(series_id, book_slug, page, text, purpose)
