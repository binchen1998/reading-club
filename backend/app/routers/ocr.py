from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from ..assets import ensure_ocr, lookup_ocr
from ..config import BOOKS

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
    if body.check:
        found = lookup_ocr(body.series_id, body.book_slug, body.page, body.text)
        return found or {"words": [], "exists": False, "created": False, "source": ""}
    return ensure_ocr(body.series_id, body.book_slug, body.page, body.text, body.purpose)
