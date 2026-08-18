"""七牛直传：token insertOnly=0，key 必须归属当前用户。"""

from __future__ import annotations

import time
import uuid
from datetime import datetime

from .config import (
    QINIU_ACCESS_KEY,
    QINIU_ASSET_PREFIX,
    QINIU_BUCKET,
    QINIU_CDN_DOMAIN,
    QINIU_PRACTICE_PREFIX,
    QINIU_SECRET_KEY,
    QINIU_UPLOAD_HOST,
    QINIU_ZONE,
)

_UPLOAD_HOST_BY_ZONE = {
    "z0": "https://up-z0.qiniup.com",
    "z1": "https://up-z1.qiniup.com",
    "z2": "https://up-z2.qiniup.com",
    "na0": "https://up-na0.qiniup.com",
    "as0": "https://up-as0.qiniup.com",
}
DEFAULT_UPLOAD_HOST = "https://up-z0.qiniup.com"


def qiniu_enabled() -> bool:
    return bool(QINIU_ACCESS_KEY and QINIU_SECRET_KEY and QINIU_BUCKET and QINIU_CDN_DOMAIN)


def upload_host() -> str:
    if QINIU_UPLOAD_HOST:
        host = QINIU_UPLOAD_HOST.rstrip("/")
        return host if host.startswith("http") else f"https://{host}"
    return _UPLOAD_HOST_BY_ZONE.get(QINIU_ZONE, DEFAULT_UPLOAD_HOST)


def safe_username(username: str) -> str:
    return "".join(c if c.isalnum() or c in "-_@" else "_" for c in username)


def practice_key_prefix(username: str, practice_id: int) -> str:
    return f"{QINIU_PRACTICE_PREFIX}/{safe_username(username)}/{practice_id}-"


def resolve_video_ext(video_ext: str = "", mime_type: str = "") -> str:
    ext = (video_ext or "").lower().lstrip(".")
    if not ext:
        mime = (mime_type or "").lower()
        if "mp4" in mime or "m4v" in mime:
            ext = "mp4"
        elif "webm" in mime:
            ext = "webm"
        else:
            ext = "mp4"
    if ext == "m4v":
        ext = "mp4"
    if ext not in ("webm", "mp4", "mov"):
        ext = "mp4"
    return ext


def build_practice_key(username: str, practice_id: int, ext: str = "mp4") -> str:
    safe_ext = resolve_video_ext(ext)
    return f"{practice_key_prefix(username, practice_id)}{uuid.uuid4().hex}.{safe_ext}"


def build_thumb_key(username: str, practice_id: int, ext: str = "jpg") -> str:
    safe_ext = ext.lower().lstrip(".")
    if safe_ext not in ("jpg", "jpeg", "png", "webp"):
        safe_ext = "jpg"
    return f"{practice_key_prefix(username, practice_id)}thumb-{uuid.uuid4().hex}.{safe_ext}"


def practice_key_belongs_to_user(key: str, username: str, practice_id: int) -> bool:
    prefix = practice_key_prefix(username, practice_id)
    return bool(key) and key.startswith(prefix)


def cdn_url(key: str) -> str:
    if not key or not QINIU_CDN_DOMAIN:
        return ""
    domain = QINIU_CDN_DOMAIN.rstrip("/")
    if domain.startswith("http"):
        return f"{domain}/{key}"
    return f"https://{domain}/{key}"


def create_upload_token(key: str, expires: int = 3600) -> dict:
    if not qiniu_enabled():
        raise RuntimeError("七牛未配置，无法上传")
    from qiniu import Auth

    auth = Auth(QINIU_ACCESS_KEY, QINIU_SECRET_KEY)
    token = auth.upload_token(QINIU_BUCKET, key, expires, {"insertOnly": 0})
    return {
        "token": token,
        "key": key,
        "cdn_domain": QINIU_CDN_DOMAIN,
        "expires_at": int(time.time()) + expires,
    }


def tts_key(digest: str) -> str:
    return f"{QINIU_ASSET_PREFIX}/tts/{digest}.mp3"


def ocr_key(series_id: str, book_slug: str, page: int, digest: str) -> str:
    return f"{QINIU_ASSET_PREFIX}/ocr/{series_id}/{book_slug}/{page:03d}-{digest}.json"


def qiniu_exists(key: str) -> bool:
    if not qiniu_enabled() or not key:
        return False
    from qiniu import Auth, BucketManager

    auth = Auth(QINIU_ACCESS_KEY, QINIU_SECRET_KEY)
    _ret, info = BucketManager(auth).stat(QINIU_BUCKET, key)
    return getattr(info, "status_code", 0) == 200


def qiniu_put_bytes(key: str, data: bytes) -> None:
    from qiniu import put_data

    token = create_upload_token(key)["token"]
    _ret, info = put_data(token, key, data)
    if getattr(info, "status_code", 0) not in (200, 614):
        raise RuntimeError(f"七牛上传失败: {getattr(info, 'text_body', info)}")


def qiniu_get_bytes(key: str) -> bytes | None:
    url = cdn_url(key)
    if not url:
        return None
    import requests

    try:
        res = requests.get(url, timeout=30)
        if res.status_code == 200 and res.content:
            return res.content
    except Exception:
        return None
    return None


def local_media_name(username: str, practice_id: int, ext: str = "mp4") -> str:
    ts = int(datetime.utcnow().timestamp())
    return f"{safe_username(username)}-{practice_id}-{ts}.{resolve_video_ext(ext)}"
