from __future__ import annotations

import re

WORD_RE = re.compile(r"[A-Za-z']+")
ABBREV_RE = re.compile(
    r"""(?:^|[\s"'“‘(\[])(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr|St|vs|etc|U\.S|U\.K|a\.m|p\.m)\.$""",
    re.I,
)
SENTENCE_END_RE = re.compile(r"""[.!?。！？]["'”’)]*$""")
OPEN_QUOTE = set("“「『")
CLOSE_QUOTE = set("”」』")
TRAIL_CLOSE = set("\"”’」』)")
LOWER_START_RE = re.compile(r"""^["'“‘(\[]*[a-z]""")


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _word_count(text: str) -> int:
    return len(WORD_RE.findall(text or ""))


def _is_abbrev(text: str) -> bool:
    return bool(ABBREV_RE.search((text or "").strip()))


def ends_with_sentence_punct(text: str) -> bool:
    value = (text or "").strip()
    if not value or _is_abbrev(value):
        return False
    return bool(SENTENCE_END_RE.search(value))


def starts_with_lowercase(text: str) -> bool:
    return bool(LOWER_START_RE.search((text or "").strip()))


def _should_merge_next(cur: str, nxt: str, min_words: int) -> bool:
    if not nxt:
        return True
    if starts_with_lowercase(nxt):
        return True
    if nxt.lstrip()[:1] in "”’」』":
        return True
    if not ends_with_sentence_punct(cur):
        return True
    words = _word_count(cur)
    if not words:
        return False
    return words == 1 and words < min_words


def merge_short_segments(segments: list, min_words: int = 3) -> list[str]:
    items = [_compact(str(item)) for item in (segments or []) if _compact(str(item))]
    out: list[str] = []
    i = 0
    while i < len(items):
        cur = items[i]
        while i + 1 < len(items) and _should_merge_next(cur, items[i + 1], min_words):
            i += 1
            cur = _compact(f"{cur} {items[i]}")
        if cur:
            out.append(cur)
        i += 1
    return out


def split_sentences(text: str) -> list[str]:
    src = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    raw: list[str] = []
    buf = ""
    ascii_dbl = False
    curly = 0

    def in_quote() -> bool:
        return ascii_dbl or curly > 0

    def apply_quote(ch: str) -> None:
        nonlocal ascii_dbl, curly
        if ch == '"':
            ascii_dbl = not ascii_dbl
        elif ch in OPEN_QUOTE:
            curly += 1
        elif ch in CLOSE_QUOTE:
            curly = max(0, curly - 1)

    def push_buf() -> None:
        nonlocal buf
        piece = _compact(buf)
        buf = ""
        if piece:
            raw.append(piece)

    i = 0
    while i < len(src):
        ch = src[i]
        if ch == "\n":
            if not in_quote() and ends_with_sentence_punct(buf):
                push_buf()
            elif buf and not buf.endswith(" "):
                buf += " "
            i += 1
            continue

        apply_quote(ch)
        buf += ch
        chinese_end = ch in "。！？"
        english_end = ch in ".!?" and not in_quote() and not _is_abbrev(buf)
        if chinese_end or english_end:
            while i + 1 < len(src) and src[i + 1] in TRAIL_CLOSE:
                i += 1
                apply_quote(src[i])
                buf += src[i]
            nxt = src[i + 1] if i + 1 < len(src) else None
            if chinese_end or nxt is None or nxt.isspace():
                push_buf()
        i += 1
    push_buf()
    return merge_short_segments(raw, min_words=1)
