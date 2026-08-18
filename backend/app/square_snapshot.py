"""广场快照：仅 worker 定时刷新；上传完成禁止 invalidate。"""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import desc, select

from .cache_keys import SQUARE_SNAPSHOT
from .config import DATA_DIR
from .db import SessionLocal
from .models import Recording, User
from .redis_client import get_redis
from .timeutil import shanghai_today

logger = logging.getLogger("square_snapshot")
SNAPSHOT_PATH = Path(DATA_DIR) / "snapshots" / "square_public_snapshot.json"
SORT_KEYS = ("latest", "likes")
FIRST_PAGE_SIZE = 12
_memory: dict[str, Any] | None = None


def _empty_snapshot() -> dict[str, Any]:
    return {
        "generated_at": None,
        "stats": {"publicCount": 0, "todayCount": 0, "public_count": 0, "today_count": 0},
        "items_by_sort": {key: [] for key in SORT_KEYS},
        "items": [],
        "first_page_size": FIRST_PAGE_SIZE,
    }


def snapshot_is_ready(payload: dict[str, Any] | None) -> bool:
    return bool(payload and payload.get("generated_at"))


def normalize_sort(sort: str | None) -> str:
    return sort if sort in SORT_KEYS else "latest"


def get_sort_items(snapshot: dict[str, Any], sort: str) -> list[dict[str, Any]]:
    key = normalize_sort(sort)
    by_sort = snapshot.get("items_by_sort")
    if isinstance(by_sort, dict) and key in by_sort:
        return [dict(raw) for raw in (by_sort.get(key) or [])]
    if key == "latest":
        return [dict(raw) for raw in (snapshot.get("items") or [])]
    return []


def _serialize(row: Recording, nickname: str) -> dict[str, Any]:
    return {
        "id": row.id,
        "username": row.username,
        "nickname": nickname or row.username,
        "bookTitle": row.book_title,
        "page": row.page,
        "lessonDate": row.lesson_date.isoformat() if row.lesson_date else None,
        "durationSec": row.duration_sec,
        "overallScore": row.overall_score,
        "videoUrl": row.video_url,
        "thumbUrl": row.thumb_url,
        "likeCount": row.like_count,
    }


def load_snapshot() -> dict[str, Any]:
    global _memory
    if _memory and snapshot_is_ready(_memory):
        return deepcopy(_memory)
    redis = get_redis()
    if redis is not None:
        try:
            raw = redis.get(SQUARE_SNAPSHOT)
            if raw:
                payload = json.loads(raw)
                if snapshot_is_ready(payload):
                    _memory = payload
                    return deepcopy(payload)
        except Exception:
            logger.warning("read redis snapshot failed", exc_info=True)
    if SNAPSHOT_PATH.exists():
        try:
            payload = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
            if snapshot_is_ready(payload):
                _memory = payload
                return deepcopy(payload)
        except Exception:
            logger.warning("read file snapshot failed", exc_info=True)
    return _empty_snapshot()


def refresh_square_snapshot() -> dict[str, Any]:
    global _memory
    db = SessionLocal()
    try:
        rows = (
            db.execute(
                select(Recording)
                .where(Recording.status == "completed", Recording.is_public.is_(True))
                .order_by(desc(Recording.completed_at))
            )
            .scalars()
            .all()
        )
        names = {
            u.username: u.nickname or u.username
            for u in db.execute(select(User)).scalars().all()
        }
        today = shanghai_today()
        latest = [_serialize(row, names.get(row.username, "")) for row in rows]
        likes = sorted(latest, key=lambda item: (-int(item.get("likeCount") or 0), -(item.get("id") or 0)))
        today_count = sum(1 for row in rows if row.lesson_date == today)
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "stats": {
                "publicCount": len(latest),
                "todayCount": today_count,
                "public_count": len(latest),
                "today_count": today_count,
                "date": today.isoformat(),
            },
            "items_by_sort": {"latest": latest[:FIRST_PAGE_SIZE], "likes": likes[:FIRST_PAGE_SIZE]},
            "items": latest[:FIRST_PAGE_SIZE],
            "first_page_size": FIRST_PAGE_SIZE,
        }
        SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT_PATH.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        redis = get_redis()
        if redis is not None:
            redis.set(SQUARE_SNAPSHOT, json.dumps(payload, ensure_ascii=False))
        _memory = payload
        logger.info("square snapshot refreshed count=%s", len(latest))
        return payload
    finally:
        db.close()
