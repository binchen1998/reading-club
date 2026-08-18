"""为 Hungry Book Club 第一章生成课稿：讲解、词汇、短语、朗读分段。"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOK = ROOT / "content" / "books" / "NateTheGreat" / "NATETHEGREATANDTHEHUNGRyBOOKCLUB81"
WORD_RE = re.compile(r"[A-Za-z']+")

PAGES = [
    {
        "page": 8,
        "explain": "第一章题目是 Torn, Ripped, Ruined，撕破、扯破、毁掉。故事开头，小朋友自我介绍：My name is Nate the Great. 他是侦探，detective 就是专门查案子的人。他的狗 Sludge 也是侦探。他刚喊了一声 Ouch，因为被 Rosamond 留在家里的 a pile of books 绊倒了。pile 就是一堆。咱们先把这几句读顺。",
        "words": [
            {"en": "detective", "zh": "侦探"},
            {"en": "pile", "zh": "一堆"},
            {"en": "tripped", "zh": "绊倒"},
        ],
        "phrases": [
            {"en": "Nate the Great", "zh": "大侦探奈特"},
            {"en": "a pile of books", "zh": "一大堆书"},
            {"en": "I am a detective", "zh": "我是侦探"},
        ],
    },
    {
        "page": 9,
        "explain": "Sludge 一直在 sniffing，就是用鼻子闻那些书。早上 Rosamond 敲门进来，怀里抱着 a bunch of books，头上还顶着三本。她说好消息：自己办了个 book club，叫 Rosamond's Ready Readers。可是俱乐部里有麻烦，有人想 wreck 她的 cookbook。wreck 是搞坏，cookbook 是食谱书。她从脑袋上拿下一本，另外两本掉下来。Nate 问她为什么把书顶在头上，她说因为自己现在是 president，主席。",
        "words": [
            {"en": "sniffing", "zh": "闻；嗅"},
            {"en": "cookbook", "zh": "食谱书"},
            {"en": "wreck", "zh": "破坏"},
            {"en": "president", "zh": "主席；会长"},
            {"en": "strange", "zh": "奇怪的"},
        ],
        "phrases": [
            {"en": "book club", "zh": "读书俱乐部"},
            {"en": "a bunch of books", "zh": "一堆书"},
            {"en": "great news", "zh": "好消息"},
            {"en": "piled on her head", "zh": "堆在她头上"},
            {"en": "Rosamond's Ready Readers", "zh": "罗莎蒙德的准备读者"},
        ],
    },
    {
        "page": 10,
        "explain": "Rosamond 解释：These books help me hold my head high and look like a president. hold my head high 是把头抬高，显得很神气。Nate 心里想，这可是个 very strange president，strange 就是奇怪。书顶在头上当主席，他觉得这件事本身就很怪。",
        "words": [
            {"en": "strange", "zh": "奇怪的"},
            {"en": "president", "zh": "主席；会长"},
        ],
        "phrases": [
            {"en": "hold my head high", "zh": "昂首挺胸"},
            {"en": "look like", "zh": "看起来像"},
        ],
    },
    {
        "page": 11,
        "explain": "Rosamond 拿出那本新 cookbook。昨天她做好 club meeting 的 treats，点心，把书打开放在 kitchen table 上。会开完去拿点心，发现摊开的那一页 torn, ripped, ruined，撕了、扯了、毁了。Nate 和 Sludge 看了一眼，他也重复这三个词。这一章的谜就在这儿：谁把食谱页弄坏了。",
        "words": [
            {"en": "treats", "zh": "点心"},
            {"en": "torn", "zh": "撕破的"},
            {"en": "ruined", "zh": "毁了的"},
        ],
        "phrases": [
            {"en": "kitchen table", "zh": "厨房桌子"},
            {"en": "club meeting", "zh": "俱乐部聚会"},
            {"en": "torn, ripped, ruined", "zh": "撕了、扯了、毁了"},
        ],
    },
]


def split_segments(text: str, max_words: int = 42) -> list[str]:
    chunks = [p.strip() for p in re.split(r"\n+", text) if p.strip()]
    out: list[str] = []
    for chunk in chunks:
        words = WORD_RE.findall(chunk)
        if len(words) <= max_words:
            out.append(chunk)
            continue
        parts = re.split(r"(?<=[.!?])\s+", chunk)
        buf = ""
        for part in parts:
            cand = f"{buf} {part}".strip() if buf else part
            if len(WORD_RE.findall(cand)) <= max_words:
                buf = cand
            else:
                if buf:
                    out.append(buf)
                buf = part
        if buf:
            out.append(buf)
    merged: list[str] = []
    i = 0
    while i < len(out):
        cur = out[i]
        while len(WORD_RE.findall(cur)) < 3 and i + 1 < len(out):
            i += 1
            cur = f"{cur} {out[i]}".strip()
        merged.append(cur)
        i += 1
    return merged


def load_english(page: int) -> tuple[str, str]:
    raw = json.loads((BOOK / f"{page:03d}.json").read_text(encoding="utf-8"))
    return (raw.get("学习内容") or "").strip(), (raw.get("翻译") or "").strip()


def main() -> None:
    pages = []
    seen_words: list[dict] = []
    seen_phrases: list[dict] = []
    for row in PAGES:
        english, translate = load_english(row["page"])
        seen_words.extend(row["words"])
        seen_phrases.extend(row["phrases"])
        pages.append(
            {
                "page": row["page"],
                "has_text": True,
                "english": english,
                "translate": translate,
                "explain": row["explain"],
                "words": row["words"],
                "phrases": row["phrases"],
                "review_words": [dict(w) for w in seen_words],
                "review_phrases": [dict(p) for p in seen_phrases],
                "segments": split_segments(english),
            }
        )
    lesson = {
        "series": "NateTheGreat",
        "book_name": "NATETHEGREATANDTHEHUNGRyBOOKCLUB81",
        "title": "Hungry Book Club",
        "chapter": 1,
        "chapter_title": "Torn, Ripped, Ruined",
        "pages": pages,
    }
    dest = ROOT / "content" / "lessons" / "NateTheGreat" / "NATETHEGREATANDTHEHUNGRyBOOKCLUB81" / "ch01.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(lesson, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {dest} pages={len(pages)}", flush=True)


if __name__ == "__main__":
    main()
