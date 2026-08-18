import logging

from .config import REDIS_ON, REDIS_URL

logger = logging.getLogger("redis")
_redis = None


def get_redis():
    global _redis
    if not REDIS_ON or not REDIS_URL:
        return None
    if _redis is None:
        try:
            import redis

            client = redis.Redis.from_url(
                REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            client.ping()
            _redis = client
            logger.info("Redis 已连接")
        except Exception as exc:
            logger.warning("Redis 连接失败: %s", exc)
            _redis = None
    return _redis
