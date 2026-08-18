from __future__ import annotations

import hashlib
import json
import re
import struct
from pathlib import Path

from PIL import Image, ImageOps
import pytesseract


def jpeg_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        if handle.read(2) != b"\xff\xd8":
            return 1, 1
        while True:
            marker = handle.read(2)
            if len(marker) < 2 or marker[0] != 0xFF:
                return 1, 1
            if marker[1] in (0xC0, 0xC1, 0xC2):
                handle.read(3)
                height, width = struct.unpack(">HH", handle.read(4))
                return width, height
            length = struct.unpack(">H", handle.read(2))[0]
            handle.read(max(0, length - 2))


def _flatten_lines(raw) -> list:
    if not isinstance(raw, list) or not raw:
        return []
    first = raw[0]
    if (
        isinstance(first, list)
        and len(first) == 2
        and isinstance(first[0], list)
        and first[0]
        and isinstance(first[0][0], list)
        and len(first[0][0]) == 2
    ):
        return raw
    if isinstance(first, list):
        return _flatten_lines(first)
    return []


def parse_paddle(raw, width: int, height: int) -> list[dict]:
    regions = []
    for line in _flatten_lines(raw):
        try:
            pts, payload = line
            text = payload[0] if isinstance(payload, list) else str(payload)
        except (TypeError, ValueError, IndexError):
            continue
        xs = [float(p[0]) for p in pts]
        ys = [float(p[1]) for p in pts]
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
        regions.append(
            {
                "text": text,
                "left": round(x0 * 100 / max(1, width), 2),
                "top": round(y0 * 100 / max(1, height), 2),
                "width": round((x1 - x0) * 100 / max(1, width), 2),
                "height": round((y1 - y0) * 100 / max(1, height), 2),
            }
        )
    return regions


def load_page_ocr(pages_dir: Path, page_no: int) -> list[dict]:
    jpg = pages_dir / f"{page_no:03d}.jpg"
    paddle = pages_dir / f"{page_no:03d}_paddle.json"
    if not jpg.exists() or not paddle.exists():
        return []
    try:
        raw = json.loads(paddle.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    width, height = jpeg_size(jpg)
    return parse_paddle(raw, width, height)


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def _tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9']+", text or "")


def _line_pixels(raw) -> list[dict]:
    lines = []
    for line in _flatten_lines(raw):
        try:
            pts, payload = line
            text = payload[0] if isinstance(payload, list) else str(payload)
        except (TypeError, ValueError, IndexError):
            continue
        xs = [float(p[0]) for p in pts]
        ys = [float(p[1]) for p in pts]
        lines.append(
            {
                "text": text,
                "x0": min(xs),
                "y0": min(ys),
                "x1": max(xs),
                "y1": max(ys),
            }
        )
    return lines


def _match_lines(lines: list[dict], text: str) -> list[dict]:
    needle = _norm(text)
    hits = []
    for line in lines:
        key = _norm(line["text"])
        if not key:
            continue
        if key in needle or needle in key:
            hits.append(line)
    hits.sort(key=lambda row: (row["y0"], row["x0"]))
    return hits


def _similar(a: str, b: str) -> bool:
    left, right = _norm(a), _norm(b)
    if not left or not right:
        return False
    return left == right or left.startswith(right) or right.startswith(left)


def _tesseract_words(crop: Image.Image, origin_x: int, origin_y: int, page_w: int, page_h: int, psm: int = 7) -> list[dict]:
    scale = 3
    big = crop.resize((max(1, crop.width * scale), max(1, crop.height * scale)), Image.Resampling.LANCZOS)
    gray = ImageOps.grayscale(big)
    data = pytesseract.image_to_data(gray, lang="eng", config=f"--psm {psm}", output_type=pytesseract.Output.DICT)
    words = []
    for i, raw in enumerate(data.get("text") or []):
        tokens = _tokens(raw)
        if not tokens:
            continue
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1
        if conf < 0:
            continue
        left = origin_x + int(data["left"][i]) / scale
        top = origin_y + int(data["top"][i]) / scale
        width = int(data["width"][i]) / scale
        height = int(data["height"][i]) / scale
        words.append(
            {
                "text": tokens[0],
                "left": round(left * 100 / max(1, page_w), 2),
                "top": round(top * 100 / max(1, page_h), 2),
                "width": round(width * 100 / max(1, page_w), 2),
                "height": round(height * 100 / max(1, page_h), 2),
            }
        )
    return words


def _align_words(expected: list[str], found: list[dict]) -> list[dict]:
    aligned = []
    cursor = 0
    for token in expected:
        match = None
        for idx in range(cursor, len(found)):
            if _similar(found[idx]["text"], token):
                match = found[idx]
                cursor = idx + 1
                break
            if idx > cursor + 2:
                break
        if match:
            aligned.append({**match, "text": token})
    return aligned or found


def _glyph_units(word: str) -> float:
    units = 0.0
    for ch in word:
        lower = ch.lower()
        if lower in "ilj.,'":
            units += 0.38
        elif lower in "ft-":
            units += 0.55
        elif lower in "mw":
            units += 1.45
        else:
            units += 1.0
    return max(0.35, units)


def _split_line_words(line: dict, page_w: int, page_h: int) -> list[dict]:
    tokens = _tokens(line["text"])
    if not tokens:
        return []
    weights = [_glyph_units(token) for token in tokens]
    gap = 0.55
    total = sum(weights) + gap * max(0, len(tokens) - 1)
    span = max(1.0, line["x1"] - line["x0"])
    x = line["x0"]
    top = line["y0"]
    height = max(1.0, line["y1"] - line["y0"])
    boxes = []
    for i, token in enumerate(tokens):
        width = span * weights[i] / total
        boxes.append(
            {
                "text": token,
                "left": round(x * 100 / max(1, page_w), 2),
                "top": round(top * 100 / max(1, page_h), 2),
                "width": round(width * 100 / max(1, page_w), 2),
                "height": round(height * 100 / max(1, page_h), 2),
            }
        )
        x += width
        if i < len(tokens) - 1:
            x += span * gap / total
    return boxes


def _tesseract_fallback(image: Image.Image, hits: list[dict], page_w: int, page_h: int) -> list[dict]:
    found: list[dict] = []
    pad = 10
    for line in hits:
        x0 = max(0, int(line["x0"]) - pad)
        y0 = max(0, int(line["y0"]) - pad)
        x1 = min(page_w, int(line["x1"]) + pad)
        y1 = min(page_h, int(line["y1"]) + pad)
        if x1 <= x0 or y1 <= y0:
            continue
        crop = image.crop((x0, y0, x1, y1))
        psm = 6 if (y1 - y0) > 80 else 7
        found.extend(_tesseract_words(crop, x0, y0, page_w, page_h, psm=psm))
    return found


def ocr_cache_digest(text: str) -> str:
    return hashlib.md5(f"split:{text}".encode("utf-8")).hexdigest()[:16]


def word_boxes_for_text(pages_dir: Path, page_no: int, text: str, cache_dir: Path | None = None) -> list[dict]:
    expected = _tokens(text)
    if not expected:
        return []
    jpg = pages_dir / f"{page_no:03d}.jpg"
    paddle = pages_dir / f"{page_no:03d}_paddle.json"
    if not jpg.exists():
        return []
    digest = ocr_cache_digest(text)
    if cache_dir:
        cached = cache_dir / f"{page_no:03d}-{digest}.json"
        if cached.exists():
            try:
                return json.loads(cached.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
    image = Image.open(jpg).convert("RGB")
    page_w, page_h = image.size
    lines = []
    if paddle.exists():
        try:
            lines = _line_pixels(json.loads(paddle.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            lines = []
    hits = _match_lines(lines, text) if lines else []
    found: list[dict] = []
    if hits:
        for line in hits:
            found.extend(_split_line_words(line, page_w, page_h))
    if len(_align_words(expected, found)) < max(1, int(len(expected) * 0.7)):
        if not hits:
            hits = [{"text": text, "x0": 0, "y0": 0, "x1": page_w, "y1": page_h}]
        found = _tesseract_fallback(image, hits, page_w, page_h)
    words = _align_words(expected, found)
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / f"{page_no:03d}-{digest}.json").write_text(
            json.dumps(words, ensure_ascii=False),
            encoding="utf-8",
        )
    return words
