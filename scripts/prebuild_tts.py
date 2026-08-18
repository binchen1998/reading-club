from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.tts import AUDIO, audio_path, collect_all_texts, synthesize  # noqa: E402


def main() -> None:
    items = collect_all_texts()
    AUDIO.mkdir(parents=True, exist_ok=True)
    print(f"[tts] {len(items)} clips", flush=True)
    ok = skip = fail = 0
    for i, (lesson, text) in enumerate(items, 1):
        dest = audio_path(text)
        preview = text.replace("\n", " ")[:48]
        if dest.exists() and dest.stat().st_size > 200:
            skip += 1
            print(f"[skip] {i}/{len(items)} {lesson.name} {preview}", flush=True)
            continue
        last_error = None
        for attempt in range(3):
            try:
                synthesize(text, dest)
                ok += 1
                print(f"[ok] {i}/{len(items)} {lesson.name} {preview}", flush=True)
                last_error = None
                break
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                time.sleep(1.5 * (attempt + 1))
        if last_error:
            fail += 1
            print(f"[fail] {i}/{len(items)} {lesson.name} {preview} {last_error}", flush=True)
    print(f"[tts] done ok={ok} skip={skip} fail={fail}", flush=True)
    if fail:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
