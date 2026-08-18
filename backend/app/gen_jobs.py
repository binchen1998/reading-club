"""生成任务登记：FastAPI 只入队，worker 做完后通过 SSE 推结果。"""

from __future__ import annotations

import json
import queue
import threading
import time
import uuid
from dataclasses import dataclass, field

JOB_TTL_SEC = 30 * 60


@dataclass
class Job:
    id: str
    kind: str
    key: str
    payload: dict
    priority: int = 0
    status: str = "queued"
    result: dict | None = None
    error: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


_guard = threading.Lock()
_jobs: dict[str, Job] = {}
_by_key: dict[str, str] = {}
_subs: dict[str, list[queue.Queue]] = {}
_interactive: queue.PriorityQueue[tuple[int, int, str]] = queue.PriorityQueue()
_seq = 0


def _prune_locked() -> None:
    now = time.time()
    stale = [job_id for job_id, job in _jobs.items() if job.status in ("done", "error") and now - job.updated_at > JOB_TTL_SEC]
    for job_id in stale:
        job = _jobs.pop(job_id, None)
        if job and _by_key.get(job.key) == job_id:
            _by_key.pop(job.key, None)
        _subs.pop(job_id, None)


def snapshot(job_id: str) -> dict | None:
    with _guard:
        job = _jobs.get(job_id)
        if not job:
            return None
        return {
            "job_id": job.id,
            "kind": job.kind,
            "status": job.status,
            "result": job.result,
            "error": job.error,
        }


def get_job(job_id: str) -> Job | None:
    with _guard:
        return _jobs.get(job_id)


def _job_preview(job: Job) -> str:
    payload = job.payload or {}
    if job.kind == "lesson":
        chapter = int(payload.get("chapter") or 0)
        return f"{payload.get('series_id')}/{payload.get('book_slug')}/ch{chapter:02d}"
    if job.kind == "tts":
        return (payload.get("text") or "")[:80]
    if job.kind == "ocr":
        text = (payload.get("text") or "")[:50]
        return f"{payload.get('series_id')}/{payload.get('book_slug')} p{payload.get('page')} {text}"
    if job.kind == "chat":
        return (payload.get("student_text") or payload.get("book_title") or "")[:80]
    return job.key


def list_open_jobs() -> list[dict]:
    with _guard:
        jobs = [job for job in _jobs.values() if job.status in ("queued", "running")]
    jobs.sort(key=lambda job: (0 if job.status == "running" else 1, job.updated_at))
    return [
        {
            "job_id": job.id,
            "kind": job.kind,
            "key": job.key,
            "status": job.status,
            "preview": _job_preview(job),
        }
        for job in jobs
    ]


def subscribe(job_id: str) -> queue.Queue:
    q: queue.Queue = queue.Queue()
    with _guard:
        _subs.setdefault(job_id, []).append(q)
    return q


def unsubscribe(job_id: str, q: queue.Queue) -> None:
    with _guard:
        items = _subs.get(job_id) or []
        if q in items:
            items.remove(q)
        if not items:
            _subs.pop(job_id, None)


def _publish_locked(job: Job) -> None:
    event = {
        "job_id": job.id,
        "kind": job.kind,
        "status": job.status,
        "result": job.result,
        "error": job.error,
    }
    for q in list(_subs.get(job.id) or []):
        q.put(event)


def mark_running(job_id: str) -> None:
    with _guard:
        job = _jobs.get(job_id)
        if not job:
            return
        job.status = "running"
        job.updated_at = time.time()
        _publish_locked(job)


def mark_done(job_id: str, result: dict | None = None) -> None:
    with _guard:
        job = _jobs.get(job_id)
        if not job:
            return
        job.status = "done"
        job.result = result or {}
        job.error = ""
        job.updated_at = time.time()
        _publish_locked(job)


def mark_error(job_id: str, error: str) -> None:
    with _guard:
        job = _jobs.get(job_id)
        if not job:
            return
        job.status = "error"
        job.error = error
        job.updated_at = time.time()
        _publish_locked(job)


def submit_job(kind: str, key: str, payload: dict, priority: int = 0) -> Job:
    global _seq
    with _guard:
        _prune_locked()
        existing_id = _by_key.get(key)
        if existing_id:
            job = _jobs.get(existing_id)
            if job and job.status in ("queued", "running"):
                return job
        _seq += 1
        job = Job(id=uuid.uuid4().hex, kind=kind, key=key, payload=payload, priority=priority)
        _jobs[job.id] = job
        _by_key[key] = job.id
        _interactive.put((priority, _seq, job.id))
        _publish_locked(job)
        return job


def next_interactive_job() -> Job | None:
    _prio, _seq_n, job_id = _interactive.get()
    with _guard:
        return _jobs.get(job_id)


def job_payload(job: Job) -> dict:
    return {
        "job_id": job.id,
        "exists": job.status == "done",
        "status": job.status,
        "result": job.result,
        "error": job.error,
    }


def iter_job_sse(job_id: str):
    q = subscribe(job_id)
    try:
        snap = snapshot(job_id)
        if not snap:
            yield _sse({"job_id": job_id, "status": "error", "error": "任务不存在"})
            return
        yield _sse(snap)
        if snap["status"] in ("done", "error"):
            return
        while True:
            try:
                event = q.get(timeout=15)
            except queue.Empty:
                yield ": keepalive\n\n"
                continue
            yield _sse(event)
            if event.get("status") in ("done", "error"):
                return
    finally:
        unsubscribe(job_id, q)


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
