import json
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from ..config import RECORDINGS

router = APIRouter(prefix="/api")


@router.post("/recordings")
async def save_recording(
    series_id: str = Form(...),
    book_slug: str = Form(...),
    chapter: str = Form(...),
    page: int = Form(...),
    text: str = Form(""),
    file: UploadFile = File(...),
):
    rec_id = uuid.uuid4().hex[:12]
    dest = RECORDINGS / rec_id
    dest.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "clip.webm").suffix or ".webm"
    audio_path = dest / f"clip{suffix}"
    audio_path.write_bytes(await file.read())
    meta = {
        "id": rec_id,
        "series_id": series_id,
        "book_slug": book_slug,
        "chapter": chapter,
        "page": page,
        "text": text,
        "file": audio_path.name,
        "created_at": int(time.time()),
    }
    (dest / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"id": rec_id, "share_url": f"/share/{rec_id}", "audio_url": f"/media/recordings/{rec_id}/{audio_path.name}"}


@router.get("/recordings/{rec_id}")
def recording_meta(rec_id: str):
    meta = RECORDINGS / rec_id / "meta.json"
    if not meta.exists():
        raise HTTPException(404, "录音不存在")
    data = json.loads(meta.read_text(encoding="utf-8"))
    data["audio_url"] = f"/media/recordings/{rec_id}/{data['file']}"
    return data


@router.get("/share/{rec_id}", response_class=HTMLResponse)
def share_page(rec_id: str):
    meta_path = RECORDINGS / rec_id / "meta.json"
    if not meta_path.exists():
        raise HTTPException(404, "分享不存在")
    data = json.loads(meta_path.read_text(encoding="utf-8"))
    audio = f"/media/recordings/{rec_id}/{data['file']}"
    text = (data.get("text") or "").replace("<", "")
    return f"""<!doctype html>
<html lang="zh">
<head>
  <meta charset="utf-8" />
  <title>朗读分享</title>
  <style>
    body {{ margin:0; font-family: system-ui, sans-serif; min-height:100vh; background: linear-gradient(to bottom right, #ffedd9, rgba(255,201,51,.25), rgba(255,77,148,.2)); color:#d04f0a; padding:24px; }}
    .card {{ max-width:720px; margin:auto; background:rgba(255,255,255,.95); border-radius:24px; padding:24px; box-shadow: 0 10px 28px -8px rgba(240,101,21,.38); }}
    h1 {{ margin:0 0 12px; }}
    p {{ line-height:1.8; font-weight:700; }}
    audio {{ width:100%; margin-top:16px; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>第 {data.get("page")} 页朗读</h1>
    <p>{text}</p>
    <audio controls src="{audio}"></audio>
  </div>
</body>
</html>"""
