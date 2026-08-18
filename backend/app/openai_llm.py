"""OpenAI 客户端：讲解用 luna，助教用 nano；base_url 只读 .env。"""

from __future__ import annotations

import logging
from typing import Any

from .config import (
    OPENAI_API_KEY,
    OPENAI_ASSISTANT_MODEL,
    OPENAI_BASE_URL,
    OPENAI_TEACHING_MODEL,
)

logger = logging.getLogger("openai_llm")

_client: Any | None = None
_client_fingerprint = ""


def teaching_model() -> str:
    return OPENAI_TEACHING_MODEL or "gpt-5.6-luna"


def assistant_model() -> str:
    return OPENAI_ASSISTANT_MODEL or "gpt-5.6-nano"


def openai_base_url() -> str:
    base = (OPENAI_BASE_URL or "").strip().rstrip("/")
    if not base:
        raise RuntimeError("未配置 OPENAI_BASE_URL")
    if not base.endswith("/v1"):
        return f"{base}/v1"
    return base


def get_openai_client():
    global _client, _client_fingerprint
    key = (OPENAI_API_KEY or "").strip()
    if not key:
        return None
    from openai import OpenAI

    base = openai_base_url()
    fingerprint = f"{key}|{base}"
    if _client is None or _client_fingerprint != fingerprint:
        _client = OpenAI(api_key=key, base_url=base)
        _client_fingerprint = fingerprint
        logger.info("OpenAI client ready (base=%s teaching=%s assistant=%s)", base, teaching_model(), assistant_model())
    return _client


def complete(
    client,
    messages: list[dict],
    *,
    model: str,
    max_completion_tokens: int | None = None,
):
    attempts: list[dict] = [
        {"model": model, "messages": messages},
        {"model": model, "messages": messages, "temperature": 0.2},
    ]
    if max_completion_tokens:
        for item in attempts:
            item["max_completion_tokens"] = max_completion_tokens
    last = None
    for kwargs in attempts:
        try:
            resp = client.chat.completions.create(**kwargs)
        except Exception as exc:
            last = exc
            continue
        err = getattr(resp, "error", None)
        if err:
            last = err
            continue
        if resp.choices:
            return resp
        last = resp
    raise RuntimeError(f"模型无有效输出: {last}")
