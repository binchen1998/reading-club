from __future__ import annotations

import logging

from backend.app.assets import ensure_ocr, ensure_tts
from backend.app.routers.lessons import merge_short_segments
from backend.app.tts import collect_lesson_texts

logger = logging.getLogger("prebuild_content")


def generate_tts(lesson: dict, label: str) -> tuple[int, int]:
    texts = collect_lesson_texts(lesson)
    ok = skip = 0
    for i, text in enumerate(texts, 1):
        preview = text.replace("\n", " ")[:40]
        result = ensure_tts(text, purpose="预生成课稿")
        created = bool(result.get("created"))
        if created:
            ok += 1
            print(f"[tts] {label} {i}/{len(texts)} new {preview}", flush=True)
        else:
            skip += 1
            print(f"[tts] {label} {i}/{len(texts)} skip {preview}", flush=True)
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
