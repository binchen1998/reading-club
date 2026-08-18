from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, UploadFile

ROOT = Path(__file__).resolve().parents[3]
RECORDS = ROOT / "storage" / "records"

router = APIRouter(prefix="/api/records")


@router.post("")
async def save_record(
    file: UploadFile = File(...),
    book_name: str = Form(""),
    page: int = Form(0),
    segment: int = Form(0),
):
    RECORDS.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename or "clip.webm").suffix or ".webm"
    name = f"{book_name or 'book'}-p{page:03d}-s{segment:02d}-{uuid4().hex[:8]}{ext}"
    dest = RECORDS / name
    dest.write_bytes(await file.read())
    return {"ok": True, "url": f"/media/records/{name}", "name": name}
