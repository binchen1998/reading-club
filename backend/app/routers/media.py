from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse, Response

from ..assets import lookup_tts
from ..remote_book import book_exists, page_image_bytes
from ..tts import audio_path

router = APIRouter(prefix="/api/media")
cdn_router = APIRouter(prefix="/media/cdn")


@router.get("/tts")
def tts(text: str = Query(..., min_length=1), purpose: str = Query("讲解音频")):
    del purpose
    result = lookup_tts(text.strip())
    url = (result or {}).get("url") or ""
    if not url:
        raise HTTPException(409, "音频尚未生成")
    if url.startswith("http"):
        return RedirectResponse(url)
    path = audio_path(text.strip())
    if not path.exists():
        raise HTTPException(409, "音频尚未生成")
    return FileResponse(path, media_type="audio/mpeg")


@cdn_router.get("/{series_id}/{book_slug}/{page_name}")
def cdn_page_image(series_id: str, book_slug: str, page_name: str):
    if not book_exists(series_id, book_slug):
        raise HTTPException(404, "没有这本书")
    name = (page_name or "").lower()
    if not name.endswith(".jpg"):
        raise HTTPException(404, "没有这一页")
    try:
        page = int(name[:-4])
    except ValueError as exc:
        raise HTTPException(404, "没有这一页") from exc
    data = page_image_bytes(series_id, book_slug, page)
    if not data:
        raise HTTPException(404, "没有这一页")
    return Response(content=data, media_type="image/jpeg")
