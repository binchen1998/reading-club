from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .config import AUDIO, BOOKS, HOST, PORT, RECORDINGS, ROOT
from .lesson_worker import start_lesson_worker
from .routers import (
    admin,
    assets,
    catalog,
    dict as dict_router,
    jobs,
    leaderboard,
    lessons,
    media,
    ocr,
    practice,
    profile,
    progress,
    reports,
    share,
    square,
    teaching,
    users,
    wrongbook,
)
from .routers.share import share_page
from .timeutil import server_now_iso, shanghai_today

DIST = ROOT / "frontend" / "dist"
NO_CACHE = {"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    start_lesson_worker()
    yield


app = FastAPI(title="袋鼠英语-阅读俱乐部", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

AUDIO.mkdir(parents=True, exist_ok=True)
RECORDINGS.mkdir(parents=True, exist_ok=True)

app.include_router(catalog.router)
app.include_router(lessons.router)
app.include_router(jobs.router)
app.include_router(media.router)
app.include_router(media.cdn_router)
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
app.include_router(leaderboard.router)
app.include_router(profile.router)
app.include_router(teaching.router)
app.get("/share/{rec_id}")(share_page)
app.mount("/media/books", StaticFiles(directory=BOOKS), name="books")
app.mount("/media/audio", StaticFiles(directory=AUDIO), name="audio")
app.mount("/media/recordings", StaticFiles(directory=RECORDINGS), name="recordings")

_assets = DIST / "assets"
if _assets.exists():
    app.mount("/assets", StaticFiles(directory=str(_assets)), name="assets")


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "service": "reading-club",
        "server_now": server_now_iso(),
        "today": shanghai_today().isoformat(),
        "timezone": "Asia/Shanghai",
    }


def _serve_index():
    index = DIST / "index.html"
    if not index.exists():
        return HTMLResponse(
            "<h1>前端尚未构建</h1><p>开发请运行 <code>cd frontend && npm run dev</code>，"
            "生产请在服务器执行 <code>npm run deploy</code>。</p>",
            status_code=200,
        )
    return FileResponse(str(index), headers=NO_CACHE)


@app.get("/")
async def index():
    return _serve_index()


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    if full_path.startswith(("api/", "assets/", "media/", "share/")):
        raise HTTPException(status_code=404)
    candidate = DIST / full_path
    if candidate.is_file():
        return FileResponse(str(candidate))
    return _serve_index()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)
