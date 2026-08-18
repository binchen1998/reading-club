from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse

from ..assets import ensure_tts
from ..tts import audio_path

router = APIRouter(prefix="/api/media")


@router.get("/tts")
def tts(text: str = Query(..., min_length=1), purpose: str = Query("讲解音频")):
    result = ensure_tts(text.strip(), purpose)
    url = result.get("url") or ""
    if not url:
        raise HTTPException(404, "音频生成失败")
    if url.startswith("http"):
        return RedirectResponse(url)
    path = audio_path(text.strip())
    if not path.exists():
        raise HTTPException(404, "音频生成失败")
    return FileResponse(path, media_type="audio/mpeg")
