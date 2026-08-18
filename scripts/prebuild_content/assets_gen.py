from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from backend.app.assets import ensure_ocr, ensure_tts
from backend.app.routers.lessons import merge_short_segments
from backend.app.tts import collect_lesson_texts

logger = logging.getLogger("prebuild_content")
TTS_WORKERS = max(2, int(os.getenv("TTS_WORKERS") or "8"))


def generate_tts(lesson: dict, label: str) -> tuple[int, int]:
    texts = collect_lesson_texts(lesson)
    total = len(texts)
    ok = skip = 0
    if not texts:
        return 0, 0

    def one(text: str) -> tuple[str, bool]:
        result = ensure_tts(text, purpose="预生成课稿")
        return text, bool(result.get("created"))

    print(f"[tts] {label} 并行 {TTS_WORKERS} 路，共 {total} 条", flush=True)
    with ThreadPoolExecutor(max_workers=TTS_WORKERS) as pool:
        futures = {pool.submit(one, text): text for text in texts}
        done = 0
        for fut in as_completed(futures):
            done += 1
            text, created = fut.result()
            preview = text.replace("\n", " ")[:40]
            if created:
                ok += 1
                kind = "new"
            else:
                skip += 1
                kind = "skip"
            print(f"[tts] {label} {done}/{total} {kind} {preview}", flush=True)
    return ok, skip


def generate_ocr(series_id: str, book_slug: str, lesson: dict, label: str) -> tuple[int, int]:
    ok = skip = 0
    items: list[tuple[int, str]] = []
    for beat in lesson.get("beats") or []:
        page = int(beat.get("page") or 0)
        for seg in merge_short_segments(beat.get("segments") or []):
            items.append((page, seg))
    for i, (page, text) in enumerate(items, 1):
        preview = text.replace("\n", " ")[:40]
        result = ensure_ocr(series_id, book_slug, page, text, purpose="预生成词框")
        created = bool(result.get("created"))
        if created:
            ok += 1
            print(f"[ocr] {label} p{page} {i}/{len(items)} new {preview}", flush=True)
        else:
            skip += 1
            print(f"[ocr] {label} p{page} {i}/{len(items)} skip {preview}", flush=True)
    return ok, skip
