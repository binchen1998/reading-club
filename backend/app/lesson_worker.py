"""按用户正在读的书生成课稿、讲解 TTS、朗读词框。

启动和浏览书目时不预生成。只有阅读页发起生成后，才排队这本书。
"""

from __future__ import annotations

import json
import logging
import queue
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from .book_pages import split_chapters
from .config import BOOKS, LESSONS
from .gen_jobs import mark_done, mark_error, mark_running, next_interactive_job
from .lesson_gen import generate_lesson, lesson_exists
from .ocr import ocr_cache_digest
from .tts import audio_id
from .worker_log import attach_worker_logging

logger = logging.getLogger("lesson_worker")
WORD_RE = re.compile(r"[A-Za-z']+")
TTS_WORKERS = 6
INTERACTIVE_WORKERS = 4
RETRY_AFTER_SEC = 90

_queue: queue.Queue[tuple[str, str, int, str]] = queue.Queue()
_guard = threading.Lock()
_queued: set[str] = set()
_active: set[str] = set()
_done: set[str] = set()
_failed_at: dict[str, float] = {}
_started = False


def _key(series_id: str, book_slug: str, chapter: int) -> str:
    return f"{series_id}/{book_slug}/ch{chapter:02d}"


def is_generating(series_id: str, book_slug: str, chapter: int) -> bool:
    key = _key(series_id, book_slug, chapter)
    with _guard:
        return key in _queued or key in _active


def start_lesson_worker() -> None:
    global _started
    with _guard:
        if _started:
            return
        _started = True
    attach_worker_logging()
    threading.Thread(target=_loop, daemon=True, name="lesson-worker").start()
    for i in range(INTERACTIVE_WORKERS):
        threading.Thread(target=_interactive_loop, daemon=True, name=f"gen-worker-{i}").start()


def enqueue_book(series_id: str, book_slug: str) -> None:
    start_lesson_worker()
    from .remote_book import book_exists, load_book

    if not book_exists(series_id, book_slug):
        return
    try:
        book = load_book(series_id, book_slug)
        chapters = split_chapters(book.get("pages") or [])
    except Exception:
        logger.exception("enqueue book failed %s/%s", series_id, book_slug)
        return
    for info in chapters:
        num = int(info.get("chapter") or 0)
        if num:
            _put(series_id, book_slug, num)


def enqueue_all_local() -> None:
    start_lesson_worker()
    if not BOOKS.exists():
        return
    for book_path in sorted(BOOKS.glob("*/*/book.json")):
        enqueue_book(book_path.parents[1].name, book_path.parent.name)


def forget_chapter(series_id: str, book_slug: str, chapter: int) -> None:
    key = _key(series_id, book_slug, chapter)
    with _guard:
        _done.discard(key)
        _failed_at.pop(key, None)


def enqueue_chapter(series_id: str, book_slug: str, chapter: int, force: bool = False) -> None:
    start_lesson_worker()
    if force:
        forget_chapter(series_id, book_slug, chapter)
    _put(series_id, book_slug, chapter, force=force)


def _put(series_id: str, book_slug: str, chapter: int, force: bool = False) -> None:
    key = _key(series_id, book_slug, chapter)
    now = time.time()
    with _guard:
        if key in _queued or key in _active:
            return
        if not force and key in _done:
            return
        last_fail = _failed_at.get(key) or 0
        if not force and last_fail and now - last_fail < RETRY_AFTER_SEC:
            return
        _queued.add(key)
    _queue.put((series_id, book_slug, chapter, key))
    logger.info("排队章节 %s", key)


def background_status() -> dict:
    with _guard:
        return {
            "queued": sorted(_queued),
            "active": sorted(_active),
            "queued_count": len(_queued),
            "active_count": len(_active),
        }


def _loop() -> None:
    logger.info("lesson worker started")
    while True:
        series_id, book_slug, chapter, key = _queue.get()
        with _guard:
            _queued.discard(key)
            _active.add(key)
        logger.info("开始后台生成 %s", key)
        try:
            _generate_one(series_id, book_slug, chapter, key)
            with _guard:
                _done.add(key)
                _failed_at.pop(key, None)
        except Exception:
            logger.exception("background generate failed %s", key)
            with _guard:
                _failed_at[key] = time.time()
        finally:
            with _guard:
                _active.discard(key)
                _queued.discard(key)


def _merge_short_segments(segments: list, min_words: int = 3) -> list[str]:
    out: list[str] = []
    i = 0
    items = [str(s).strip() for s in segments or [] if str(s).strip()]
    while i < len(items):
        cur = items[i]
        while len(WORD_RE.findall(cur)) < min_words and i + 1 < len(items):
            i += 1
            cur = f"{cur} {items[i]}".strip()
        out.append(cur)
        i += 1
    return out


def _generate_one(series_id: str, book_slug: str, chapter: int, key: str) -> None:
    from .openai_llm import get_openai_client

    if not lesson_exists(series_id, book_slug, chapter):
        if get_openai_client() is None:
            logger.warning("skip lesson %s: no OPENAI_API_KEY", key)
            return
        logger.info("background lesson %s", key)
        generate_lesson(series_id, book_slug, chapter)
    path = LESSONS / series_id / book_slug / f"ch{chapter:02d}.json"
    if not path.exists():
        return
    lesson = json.loads(path.read_text(encoding="utf-8"))
    _fill_tts(lesson, key)
    _fill_ocr(series_id, book_slug, lesson, key)
    logger.info("background generate ready %s", key)


def _fill_tts(lesson: dict, label: str) -> None:
    from .assets import ensure_tts
    from .tts import collect_lesson_texts

    texts = collect_lesson_texts(lesson)
    if not texts:
        return
    logger.info("background tts %s count=%s", label, len(texts))

    done = 0
    lock = threading.Lock()

    def one(text: str) -> None:
        nonlocal done
        preview = (text or "")[:50]
        try:
            logger.info("TTS %s %s", label, preview)
            ensure_tts(text, purpose="后台预生成")
            with lock:
                done += 1
                logger.info("TTS 完成 %s %s/%s %s", label, done, len(texts), preview)
        except Exception:
            logger.exception("background tts failed %s %s", label, preview)

    workers = min(TTS_WORKERS, max(2, len(texts)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(one, text) for text in texts]
        for fut in as_completed(futs):
            fut.result()


def _fill_ocr(series_id: str, book_slug: str, lesson: dict, label: str) -> None:
    from .assets import ensure_ocr

    items: list[tuple[int, str]] = []
    for beat in lesson.get("beats") or []:
        page = int(beat.get("page") or 0)
        for seg in _merge_short_segments(beat.get("segments") or []):
            items.append((page, seg))
    if not items:
        return
    logger.info("background ocr %s count=%s", label, len(items))
    for index, (page, text) in enumerate(items, start=1):
        preview = (text or "")[:50]
        try:
            logger.info("OCR %s %s/%s p%s %s", label, index, len(items), page, preview)
            ensure_ocr(series_id, book_slug, page, text, purpose="后台预生成")
        except Exception:
            logger.exception("background ocr failed %s p%s %s", label, page, preview)


def enqueue_lesson_job(series_id: str, book_slug: str, chapter: int):
    from .gen_jobs import submit_job

    start_lesson_worker()
    return submit_job(
        "lesson",
        f"lesson:{series_id}/{book_slug}/ch{chapter:02d}",
        {"series_id": series_id, "book_slug": book_slug, "chapter": chapter},
        priority=0,
    )


def enqueue_tts_job(text: str, purpose: str = "讲解音频"):
    from .gen_jobs import submit_job

    start_lesson_worker()
    value = (text or "").strip()
    return submit_job("tts", f"tts:{audio_id(value)}", {"text": value, "purpose": purpose}, priority=1)


def enqueue_ocr_job(series_id: str, book_slug: str, page: int, text: str, purpose: str = "这一句的词框"):
    from .gen_jobs import submit_job

    start_lesson_worker()
    value = (text or "").strip()
    digest = ocr_cache_digest(value)
    return submit_job(
        "ocr",
        f"ocr:{series_id}/{book_slug}/{page}:{digest}",
        {
            "series_id": series_id,
            "book_slug": book_slug,
            "page": page,
            "text": value,
            "purpose": purpose,
        },
        priority=2,
    )


def _interactive_loop() -> None:
    logger.info("interactive generate worker started")
    while True:
        job = next_interactive_job()
        if job is None:
            continue
        mark_running(job.id)
        logger.info("即时任务开始 %s %s", job.kind, job.key)
        try:
            result = _run_interactive(job.kind, job.payload)
            mark_done(job.id, result)
            logger.info("即时任务完成 %s %s", job.kind, job.key)
        except Exception as exc:
            logger.exception("interactive generate failed %s", job.key)
            mark_error(job.id, str(exc) or "生成失败")


def _run_interactive(kind: str, payload: dict) -> dict:
    if kind == "lesson":
        logger.info(
            "生成课稿 %s/%s/ch%02d",
            payload.get("series_id"),
            payload.get("book_slug"),
            int(payload.get("chapter") or 0),
        )
        generate_lesson(payload["series_id"], payload["book_slug"], int(payload["chapter"]))
        return {"exists": True}
    if kind == "tts":
        from .assets import ensure_tts

        logger.info("生成 TTS %s", (payload.get("text") or "")[:80])
        return ensure_tts(payload["text"], payload.get("purpose") or "讲解音频")
    if kind == "ocr":
        from .assets import ensure_ocr

        logger.info(
            "生成 OCR %s/%s p%s %s",
            payload.get("series_id"),
            payload.get("book_slug"),
            payload.get("page"),
            (payload.get("text") or "")[:50],
        )
        return ensure_ocr(
            payload["series_id"],
            payload["book_slug"],
            int(payload["page"]),
            payload["text"],
            payload.get("purpose") or "这一句的词框",
        )
    if kind == "chat":
        from fastapi import HTTPException

        from .teaching import chat_reply

        logger.info("助教回复 %s", (payload.get("student_text") or "")[:80])

        try:
            reply = chat_reply(
                book_title=payload.get("book_title") or "",
                student_text=payload.get("student_text") or "",
                current_page=payload.get("current_page"),
                current_english=payload.get("current_english") or "",
                current_script=payload.get("current_script") or "",
                messages=payload.get("messages") or [],
            )
        except HTTPException as exc:
            detail = exc.detail
            raise RuntimeError(detail if isinstance(detail, str) else "助教暂时没有回复") from exc
        return {"reply": reply, "ok": True}
    raise RuntimeError(f"未知任务类型: {kind}")
