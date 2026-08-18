from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse

from ..assets import lookup_tts
from ..tts import audio_path

router = APIRouter(prefix="/api/media")


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
