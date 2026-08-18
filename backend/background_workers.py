import logging
import os
import signal
import threading
from pathlib import Path

from app.square_snapshot_worker import run_square_snapshot_loop

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent
WORKER_LOCK_PATH = BASE_DIR / ".background-workers.lock"


class BackgroundWorkerLock:
    def __init__(self, path: Path):
        self.path = path
        self.handle = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = open(self.path, "a+b")
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.handle.seek(0)
            self.handle.truncate()
            self.handle.write(str(os.getpid()).encode("ascii"))
            self.handle.flush()
            return True
        except OSError:
            self.release()
            return False

    def release(self) -> None:
        if not self.handle:
            return
        try:
            if os.name == "nt":
                import msvcrt

                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        self.handle.close()
        self.handle = None


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    lock = BackgroundWorkerLock(WORKER_LOCK_PATH)
    if not lock.acquire():
        logger.warning("background workers already running")
        return
    stop = threading.Event()

    def handle_stop(*_args):
        stop.set()

    signal.signal(signal.SIGINT, handle_stop)
    signal.signal(signal.SIGTERM, handle_stop)
    try:
        run_square_snapshot_loop(stop)
    finally:
        lock.release()


if __name__ == "__main__":
    main()
