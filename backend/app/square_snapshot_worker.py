import logging
import time

from .config import SQUARE_SNAPSHOT_REFRESH_INTERVAL_SECONDS
from .square_snapshot import refresh_square_snapshot

logger = logging.getLogger(__name__)


def run_square_snapshot_loop(stop):
    while not stop.is_set():
        try:
            refresh_square_snapshot()
        except Exception:
            logger.exception("square snapshot refresh failed")
        stop.wait(SQUARE_SNAPSHOT_REFRESH_INTERVAL_SECONDS)
