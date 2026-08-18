"""Worker 生成日志：内存环缓 + SSE，给 admin 实时看。"""

from __future__ import annotations

import json
import logging
import queue
import threading
import time
from collections import deque

from .timeutil import server_now_iso

MAX_LINES = 400
LOGGERS = (
    "lesson_worker",
    "lesson_gen",
    "prebuild_content",
    "content_reset",
)

_guard = threading.Lock()
_lines: deque[dict] = deque(maxlen=MAX_LINES)
_subs: list[queue.Queue] = []
_attached = False
_seq = 0


def _line(level: str, logger_name: str, message: str) -> dict:
    global _seq
    _seq += 1
    return {
        "id": _seq,
        "ts": time.time(),
        "iso": server_now_iso(),
        "level": (level or "INFO").upper(),
        "logger": logger_name or "worker",
        "message": (message or "").strip() or "(空)",
    }


def emit(level: str, logger_name: str, message: str) -> dict:
    row = _line(level, logger_name, message)
    with _guard:
        _lines.append(row)
        targets = list(_subs)
    for q in targets:
        try:
            q.put_nowait(row)
        except Exception:
            pass
    return row


def recent(limit: int = 200) -> list[dict]:
    size = max(1, min(int(limit or 200), MAX_LINES))
    with _guard:
        return list(_lines)[-size:]


def subscribe() -> queue.Queue:
    q: queue.Queue = queue.Queue(maxsize=500)
    with _guard:
        _subs.append(q)
    return q


def unsubscribe(q: queue.Queue) -> None:
    with _guard:
        if q in _subs:
            _subs.remove(q)


class WorkerLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
            if record.exc_info and record.exc_info[1]:
                msg = f"{msg}: {record.exc_info[1]}"
            emit(record.levelname, record.name, msg)
        except Exception:
            self.handleError(record)


def attach_worker_logging() -> None:
    global _attached
    if _attached:
        return
    _attached = True
    handler = WorkerLogHandler()
    handler.setLevel(logging.INFO)
    for name in LOGGERS:
        log = logging.getLogger(name)
        log.addHandler(handler)
        if log.level == logging.NOTSET or log.level > logging.INFO:
            log.setLevel(logging.INFO)


def worker_status() -> dict:
    from .gen_jobs import list_open_jobs
    from .lesson_worker import background_status

    return {
        "background": background_status(),
        "interactive": list_open_jobs(),
    }


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def iter_admin_worker_sse():
    attach_worker_logging()
    q = subscribe()
    last_status = ""
    last_keepalive = time.time()
    try:
        status = worker_status()
        last_status = json.dumps(status, ensure_ascii=False, sort_keys=True)
        yield _sse({"type": "hello", "status": status, "logs": recent(200)})
        while True:
            try:
                row = q.get(timeout=1)
                yield _sse({"type": "log", "line": row})
            except queue.Empty:
                pass
            status = worker_status()
            packed = json.dumps(status, ensure_ascii=False, sort_keys=True)
            if packed != last_status:
                last_status = packed
                yield _sse({"type": "status", "status": status})
            now = time.time()
            if now - last_keepalive >= 15:
                last_keepalive = now
                yield ": keepalive\n\n"
    finally:
        unsubscribe(q)
