import logging
import os
import signal
import threading
from pathlib import Path

from app.backup_database import backup_storage_enabled, log_backup_storage_status
from app.database_backup_worker import run_database_backup_loop
from app.leaderboard_cache_worker import run_leaderboard_cache_loop
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
    log_backup_storage_status(logger.info)
    if backup_storage_enabled():
        logger.info("database backup worker enabled")
    else:
        logger.info("database backup worker will idle (qiniu backup storage not ready)")
    backup_thread = threading.Thread(
        target=run_database_backup_loop,
        args=(stop,),
        name="db-backup-worker",
        daemon=True,
    )
    backup_thread.start()
    leaderboard_thread = threading.Thread(
        target=run_leaderboard_cache_loop,
        args=(stop,),
        name="leaderboard-worker",
        daemon=True,
    )
    leaderboard_thread.start()
    logger.info("started workers: backup, square-snapshot, leaderboard")
    try:
        run_square_snapshot_loop(stop)
    finally:
        stop.set()
        backup_thread.join(timeout=8)
        leaderboard_thread.join(timeout=8)
        lock.release()


if __name__ == "__main__":
    main()
