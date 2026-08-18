from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import AUDIO, BOOKS, RECORDINGS, ROOT
from .db import init_db
from .routers import (
    admin,
    assets,
    catalog,
    dict as dict_router,
    lessons,
    media,
    ocr,
    practice,
    profile,
    progress,
    reports,
    share,
    square,
    users,
    wrongbook,
)
from .routers.share import share_page

DIST = ROOT / "frontend" / "dist"

app = FastAPI(title="Reading Club")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

AUDIO.mkdir(parents=True, exist_ok=True)
RECORDINGS.mkdir(parents=True, exist_ok=True)
init_db()

app.include_router(catalog.router)
app.include_router(lessons.router)
app.include_router(media.router)
app.include_router(assets.router)
app.include_router(ocr.router)
app.include_router(admin.router)
app.include_router(dict_router.router)
app.include_router(share.router)
app.include_router(users.router)
app.include_router(reports.router)
app.include_router(progress.router)
app.include_router(practice.router)
app.include_router(wrongbook.router)
app.include_router(square.router)
app.include_router(profile.router)
app.get("/share/{rec_id}")(share_page)
app.mount("/media/books", StaticFiles(directory=BOOKS), name="books")
app.mount("/media/audio", StaticFiles(directory=AUDIO), name="audio")
app.mount("/media/recordings", StaticFiles(directory=RECORDINGS), name="recordings")
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


@app.get("/{full_path:path}")
async def spa(full_path: str):
    if DIST.exists():
        file = DIST / full_path
        if full_path and file.exists() and file.is_file():
            return FileResponse(file)
        return FileResponse(DIST / "index.html")
    return {"ok": True, "hint": "frontend not built"}

