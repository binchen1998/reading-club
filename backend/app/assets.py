"""按需查本地/七牛，没有再生成并回传。用到哪一项只处理哪一项。"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from .config import AUDIO, BOOKS, STORAGE
from .db import SessionLocal
from .models import GeneratedAsset
from .ocr import ocr_cache_digest, word_boxes_for_text
from .qiniu_upload import (
    cdn_url,
    ocr_key,
    qiniu_enabled,
    qiniu_exists,
    qiniu_get_bytes,
    qiniu_put_bytes,
    tts_key,
)
from .tts import audio_id, audio_path, synthesize

_locks: dict[str, threading.Lock] = {}
_guard = threading.Lock()


def _lock_for(name: str) -> threading.Lock:
    with _guard:
        lock = _locks.get(name)
        if lock is None:
            lock = threading.Lock()
            _locks[name] = lock
        return lock


def _record_asset(kind: str, asset_key: str, label: str, source: str, preview: str = "") -> None:
    db = SessionLocal()
    try:
        exists = (
            db.query(GeneratedAsset)
            .filter(GeneratedAsset.kind == kind, GeneratedAsset.asset_key == asset_key)
            .first()
        )
        if exists:
            return
        db.add(
            GeneratedAsset(
                kind=kind,
                asset_key=asset_key,
                label=(label or "")[:80],
                preview=(preview or "")[:200],
                source=source,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _maybe_upload(key: str, data: bytes) -> str:
    if not qiniu_enabled():
        return ""
    if not qiniu_exists(key):
        qiniu_put_bytes(key, data)
    return cdn_url(key)


def lookup_tts(text: str) -> dict | None:
    value = (text or "").strip()
    if not value:
        return None
    digest = audio_id(value)
    path = audio_path(value)
    key = tts_key(digest)
    if path.exists() and path.stat().st_size > 200:
        url = f"/media/audio/{digest}.mp3"
        try:
            uploaded = _maybe_upload(key, path.read_bytes())
            if uploaded:
                url = uploaded
        except Exception:
            pass
        return {"url": url, "exists": True, "created": False, "source": "local"}
    if qiniu_exists(key):
        data = qiniu_get_bytes(key)
        if data:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return {"url": cdn_url(key), "exists": True, "created": False, "source": "qiniu"}
    return None


def ensure_tts(text: str, purpose: str = "讲解音频") -> dict:
    value = (text or "").strip()
    if not value:
        return {"url": "", "exists": False, "created": False, "source": ""}
    found = lookup_tts(value)
    if found:
        return found
    digest = audio_id(value)
    path = audio_path(value)
    key = tts_key(digest)
    with _lock_for(f"tts:{digest}"):
        found = lookup_tts(value)
        if found:
            return found
        AUDIO.mkdir(parents=True, exist_ok=True)
        synthesize(value, path)
        source = "generated"
        url = f"/media/audio/{digest}.mp3"
        try:
            uploaded = _maybe_upload(key, path.read_bytes())
            if uploaded:
                url = uploaded
                source = "qiniu"
        except Exception:
            pass
        _record_asset("tts", key if qiniu_enabled() else digest, purpose, source, value)
        return {"url": url, "exists": True, "created": True, "source": source}


def _ocr_paths(series_id: str, book_slug: str, page: int, text: str) -> tuple[Path, Path, str, str]:
    digest = ocr_cache_digest(text)
    pages_dir = BOOKS / series_id / book_slug / "pages"
    cache_dir = STORAGE / "ocr" / series_id / book_slug
    local = cache_dir / f"{page:03d}-{digest}.json"
    key = ocr_key(series_id, book_slug, page, digest)
    return pages_dir, local, key, digest


def lookup_ocr(series_id: str, book_slug: str, page: int, text: str) -> dict | None:
    value = (text or "").strip()
    if not value:
        return None
    _pages_dir, local, key, _digest = _ocr_paths(series_id, book_slug, page, value)
    if local.exists():
        try:
            words = json.loads(local.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            words = None
        if isinstance(words, list):
            try:
                _maybe_upload(key, local.read_bytes())
            except Exception:
                pass
            return {"words": words, "exists": True, "created": False, "source": "local"}
    if qiniu_exists(key):
        data = qiniu_get_bytes(key)
        if data:
            try:
                words = json.loads(data.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                words = None
            if isinstance(words, list):
                local.parent.mkdir(parents=True, exist_ok=True)
                local.write_bytes(data)
                return {"words": words, "exists": True, "created": False, "source": "qiniu"}
    return None


def ensure_ocr(series_id: str, book_slug: str, page: int, text: str, purpose: str = "这一句的词框") -> dict:
    value = (text or "").strip()
    if not value:
        return {"words": [], "exists": False, "created": False, "source": ""}
    found = lookup_ocr(series_id, book_slug, page, value)
    if found:
        return found
    from io import BytesIO

    from PIL import Image

    from .ocr import word_boxes_from_image
    from .remote_book import page_image_bytes, page_paddle

    pages_dir, local, key, digest = _ocr_paths(series_id, book_slug, page, value)
    with _lock_for(f"ocr:{series_id}:{book_slug}:{page}:{digest}"):
        found = lookup_ocr(series_id, book_slug, page, value)
        if found:
            return found
        words = word_boxes_for_text(pages_dir, page, value, cache_dir=local.parent) if pages_dir.exists() else []
        if not words:
            data = page_image_bytes(series_id, book_slug, page)
            if not data:
                return {"words": [], "exists": False, "created": False, "source": ""}
            image = Image.open(BytesIO(data)).convert("RGB")
            words = word_boxes_from_image(
                image,
                page_paddle(series_id, book_slug, page),
                value,
                cache_dir=local.parent,
                page_no=page,
            )
        source = "generated"
        try:
            payload = json.dumps(words, ensure_ascii=False).encode("utf-8")
            uploaded = _maybe_upload(key, payload)
            if uploaded:
                source = "qiniu"
        except Exception:
            pass
        _record_asset(
            "ocr",
            key if qiniu_enabled() else f"{series_id}/{book_slug}/{page:03d}-{digest}",
            purpose,
            source,
            value,
        )
        return {"words": words, "exists": True, "created": True, "source": source}
