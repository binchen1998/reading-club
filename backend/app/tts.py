from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import requests

from .config import AUDIO, FISH_AUDIO_URL, FISH_TEACHER, LESSONS

SENT_SPLIT = re.compile(r"(?<=[。！？!?])\s*")


def audio_id(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def audio_path(text: str) -> Path:
    return AUDIO / f"{audio_id(text)}.mp3"


def audio_url(text: str) -> str:
    return f"/media/audio/{audio_id(text)}.mp3"


def split_sentences(text: str) -> list[str]:
    return [part.strip() for part in SENT_SPLIT.split(text or "") if len(part.strip()) > 1]


def collect_lesson_texts(lesson: dict) -> list[str]:
    texts: list[str] = []
    for item in lesson.get("word_bank") or []:
        if item.get("en"):
            texts.append(item["en"])
    for item in lesson.get("phrase_bank") or []:
        if item.get("en"):
            texts.append(item["en"])
    for beat in lesson.get("beats") or []:
        texts.extend(split_sentences(beat.get("explain") or ""))
        texts.extend(seg for seg in (beat.get("segments") or []) if seg)
    seen: set[str] = set()
    unique: list[str] = []
    for text in texts:
        if text not in seen:
            seen.add(text)
            unique.append(text)
    return unique


def collect_all_texts() -> list[tuple[Path, str]]:
    items: list[tuple[Path, str]] = []
    seen: set[str] = set()
    for path in sorted(LESSONS.glob("*/*/ch*.json")):
        lesson = json.loads(path.read_text(encoding="utf-8"))
        for text in collect_lesson_texts(lesson):
            if text in seen:
                continue
            seen.add(text)
            items.append((path, text))
    return items


def synthesize(text: str, dest: Path) -> Path:
    response = requests.get(
        f"{FISH_AUDIO_URL.rstrip('/')}/fish_audio",
        params={"text": text, "teacher": FISH_TEACHER},
        timeout=180,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        raise RuntimeError(payload["error"])
    output = payload.get("output_file") or ""
    if not output:
        raise RuntimeError(f"fish-audio 无音频: {payload}")
    audio_url_remote = output if output.startswith("http") else f"{FISH_AUDIO_URL.rstrip('/')}{output}"
    audio = requests.get(audio_url_remote, timeout=120)
    audio.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(audio.content)
    return dest


def cached_audio(text: str) -> Path | None:
    path = audio_path(text)
    if path.exists() and path.stat().st_size > 200:
        return path
    return None
