"""cache-aside，无 TTL；写路径主动 invalidate。禁止 SCAN。"""

from __future__ import annotations

import json
import logging
from typing import Any, Sequence

from .redis_client import get_redis

logger = logging.getLogger("page_cache")
_DELETE_CHUNK = 500


def cache_get(key: str) -> Any | None:
    redis = get_redis()
    if redis is None:
        return None
    try:
        raw = redis.get(key)
        if not raw:
            return None
        return json.loads(raw)
    except Exception:
        logger.warning("cache get failed key=%s", key, exc_info=True)
        return None


def cache_set(key: str, payload: Any, *, indexes: Sequence[str] | None = None) -> None:
    redis = get_redis()
    if redis is None:
        return
    try:
        redis.set(key, json.dumps(payload, ensure_ascii=False, default=str))
        if indexes:
            for index in indexes:
                if index:
                    redis.sadd(index, key)
    except Exception:
        logger.warning("cache set failed key=%s", key, exc_info=True)


def cache_delete(*keys: str) -> None:
    if not keys:
        return
    redis = get_redis()
    if redis is None:
        return
    try:
        for i in range(0, len(keys), _DELETE_CHUNK):
            redis.delete(*keys[i : i + _DELETE_CHUNK])
    except Exception:
        logger.warning("cache delete failed", exc_info=True)


def cache_delete_indexed(*indexes: str) -> None:
    cleaned = [i for i in indexes if i]
    if not cleaned:
        return
    redis = get_redis()
    if redis is None:
        return
    try:
        keys: list[str] = []
        for index in cleaned:
            members = redis.smembers(index) or set()
            keys.extend(str(item) for item in members)
            keys.append(index)
        if keys:
            for i in range(0, len(keys), _DELETE_CHUNK):
                redis.delete(*keys[i : i + _DELETE_CHUNK])
    except Exception:
        logger.warning("cache delete indexed failed", exc_info=True)
