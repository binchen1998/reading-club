import json
import re
import urllib.parse
import urllib.request

from fastapi import APIRouter, HTTPException, Query

from ..config import STORAGE

router = APIRouter(prefix="/api")
CACHE = STORAGE / "dict"
UA = "Mozilla/5.0 (compatible; reading-club/1.0)"


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.loads(resp.read().decode("utf-8", errors="ignore"))


def fetch_zh(word: str) -> str:
    youdao = "https://fanyi.youdao.com/translate?" + urllib.parse.urlencode(
        {"doctype": "json", "type": "EN2ZH_CN", "i": word}
    )
    try:
        data = _get_json(youdao)
        return str(data["translateResult"][0][0]["tgt"]).strip()
    except Exception:
        pass
    memory = "https://api.mymemory.translated.net/get?" + urllib.parse.urlencode(
        {"q": word, "langpair": "en|zh-CN"}
    )
    try:
        data = _get_json(memory)
        return str(data.get("responseData", {}).get("translatedText") or "").strip()
    except Exception:
        return ""


@router.get("/dict")
def lookup(word: str = Query(..., min_length=1)):
    key = re.sub(r"[^a-zA-Z']", "", word).lower()
    if not key:
        raise HTTPException(400, "empty word")
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / f"{key}.json"
    if cached.exists():
        return json.loads(cached.read_text(encoding="utf-8"))
    zh = fetch_zh(key)
    payload = {"en": key, "zh": zh}
    cached.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return payload
