import logging

from .config import LEADERBOARD_CACHE_REFRESH_INTERVAL_SECONDS
from .leaderboard_worker import refresh_leaderboard_cache

logger = logging.getLogger(__name__)


def run_leaderboard_cache_loop(stop):
    while not stop.is_set():
        try:
            refresh_leaderboard_cache()
        except Exception:
            logger.exception("leaderboard cache refresh failed")
        stop.wait(LEADERBOARD_CACHE_REFRESH_INTERVAL_SECONDS)
