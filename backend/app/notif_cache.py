"""未读消息数 Redis 缓存（无 TTL；创建/已读时维护）。"""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .cache_keys import NOTIF_UNREAD
from .models import Notification
from .redis_client import get_redis

logger = logging.getLogger("notif_cache")


def _key(username: str) -> str:
    return NOTIF_UNREAD.format(username=username)


def get_unread_count(db: Session, username: str) -> int:
    redis = get_redis()
    if redis is not None:
        try:
            raw = redis.get(_key(username))
            if raw is not None:
                return max(0, int(raw))
        except Exception:
            logger.warning("unread cache get failed", exc_info=True)

    count = int(
        db.execute(
            select(func.count()).select_from(Notification).where(
                Notification.username == username,
                Notification.is_read.is_(False),
            )
        ).scalar()
        or 0
    )
    set_unread_count(username, count)
    return count


def set_unread_count(username: str, count: int) -> None:
    redis = get_redis()
    if redis is None:
        return
    try:
        redis.set(_key(username), str(max(0, int(count))))
    except Exception:
        logger.warning("unread cache set failed", exc_info=True)


def invalidate_unread_count(username: str) -> None:
    redis = get_redis()
    if redis is None:
        return
    try:
        redis.delete(_key(username))
    except Exception:
        logger.warning("unread cache delete failed", exc_info=True)
