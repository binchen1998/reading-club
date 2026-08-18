import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / "backend" / ".env")
CONTENT = ROOT / "content"
CATALOG = CONTENT / "catalog.json"
BOOKS = CONTENT / "books"
LESSONS = CONTENT / "lessons"
STORAGE = ROOT / "storage"
AUDIO = STORAGE / "audio"
RECORDINGS = STORAGE / "recordings"
DATA_DIR = STORAGE
FISH_AUDIO_URL = "https://fish-audio.coding61.com"
FISH_TEACHER = "Magic"

REDIS_URL = (os.getenv("REDIS_URL") or "").strip()
REDIS_ENABLED = (os.getenv("REDIS_ENABLED") or "").strip().lower()
if REDIS_ENABLED in ("1", "true", "yes"):
    REDIS_ON = True
elif REDIS_ENABLED in ("0", "false", "no"):
    REDIS_ON = False
else:
    REDIS_ON = bool(REDIS_URL)

SQUARE_SNAPSHOT_REFRESH_INTERVAL_SECONDS = int(
    os.getenv("SQUARE_SNAPSHOT_REFRESH_INTERVAL_SECONDS") or "60"
)
QINIU_ACCESS_KEY = (os.getenv("QINIU_ACCESS_KEY") or "").strip()
QINIU_SECRET_KEY = (os.getenv("QINIU_SECRET_KEY") or "").strip()
QINIU_BUCKET = (os.getenv("QINIU_BUCKET") or "").strip()
QINIU_CDN_DOMAIN = (os.getenv("QINIU_CDN_DOMAIN") or "").strip()
QINIU_ZONE = (os.getenv("QINIU_ZONE") or os.getenv("QINIU_REGION") or "").strip().lower()
QINIU_UPLOAD_HOST = (os.getenv("QINIU_UPLOAD_HOST") or "").strip()
QINIU_PRACTICE_PREFIX = os.getenv("QINIU_PRACTICE_PREFIX") or "reading-club/practices"
QINIU_ASSET_PREFIX = os.getenv("QINIU_ASSET_PREFIX") or "reading-club/assets"
QINIU_FRONTEND_PREFIX = (os.getenv("QINIU_FRONTEND_PREFIX") or os.getenv("QINIU_DEPLOY_PREFIX") or "reading-club").strip().strip("/")
HOST = os.getenv("HOST") or "0.0.0.0"
PORT = int(os.getenv("PORT") or "8001")
JWT_SECRET = os.getenv("JWT_SECRET") or "reading_club_jwt_secret_2026"
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME") or "admin"
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD") or "coding61"
