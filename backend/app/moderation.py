"""LLM 内容审核（Qwen Max / DashScope）。同步接口，供 FastAPI 同步路由使用。"""

from __future__ import annotations

import json
import logging
from typing import Any

from .config import QWEN_API_KEY

logger = logging.getLogger(__name__)

_client: Any | None = None
_client_key = ""

_NICKNAME_SYSTEM_PROMPT = """你是一个内容审核助手，负责审核儿童教育平台的用户昵称。
请判断以下昵称是否适合作为公开展示名。只有在明确违反以下任一规则时才拒绝：
1. 含有色情、低俗或成人暗示
2. 含有政治性、敏感性或争议性内容
3. 含有脏话、粗口、侮辱性词汇（包括谐音、变体、拼音缩写）
4. 含有人身攻击、歧视、仇恨性言论
5. 含有广告、联系方式、外部链接、引流信息

重要规则：
- 昵称会显示在排行榜等公开位置，对脏话和侮辱性内容零容忍。
- 如果内容模糊或无法明确判定违规，请通过（passed: true）。
- 正常的中文名、游戏角色名、趣味昵称（不含上述违规内容）应通过。

只返回纯JSON，不要任何额外文字：
{"passed": true, "reason": ""}
或
{"passed": false, "reason": "具体原因"}
"""


def _get_client() -> Any | None:
    global _client, _client_key
    api_key = (QWEN_API_KEY or "").strip()
    if not api_key:
        logger.warning("QWEN_API_KEY is not set — nickname moderation disabled")
        return None
    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("openai package not installed — nickname moderation disabled")
        return None
    if _client is None or _client_key != api_key:
        _client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        _client_key = api_key
    return _client


def _parse_moderation_response(raw: str) -> tuple[bool, str]:
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    result = json.loads(raw.strip())
    return bool(result.get("passed", False)), str(result.get("reason", "") or "")


_TEXT_SYSTEM_PROMPT = """你是一个内容审核助手，专门负责审核儿童教育平台的用户提交内容。
请判断以下【{label}】是否通过审核。只有在明确违反以下任一规则时才拒绝：
1. 含有色情、低俗或成人内容
2. 含有政治性、敏感性或争议性内容
3. 含有人身攻击、侮辱、谩骂或针对他人的仇恨性言论

重要规则：
- 除此三类之外的内容一律通过，包括：广告、推广、外部链接、刷屏、无意义内容、粗俗但不针对个人的用语等。
- 如果内容模糊、意图不明或无法判断是否违规，请直接通过（passed: true）。只拒绝能明确认定违规的内容。

只返回纯JSON，不要任何额外文字：
{{"passed": true, "reason": ""}}
或
{{"passed": false, "reason": "具体原因"}}
"""


def _moderate_with_prompt(content: str, *, label: str, system_prompt: str) -> tuple[bool, str]:
    client = _get_client()
    if client is None:
        return True, ""
    try:
        resp = client.chat.completions.create(
            model="qwen-max",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"请审核以下【{label}】：\n\n{content}"},
            ],
            temperature=0.1,
        )
        raw = (resp.choices[0].message.content or "").strip()
        return _parse_moderation_response(raw)
    except Exception as exc:  # noqa: BLE001
        logger.error("Moderation error: %s", exc)
        return False, "审核服务暂时不可用，请稍后再试"


def moderate_nickname(content: str) -> tuple[bool, str]:
    return _moderate_with_prompt(content, label="昵称", system_prompt=_NICKNAME_SYSTEM_PROMPT)


def moderate_text(content: str, label: str = "内容") -> tuple[bool, str]:
    return _moderate_with_prompt(content, label=label, system_prompt=_TEXT_SYSTEM_PROMPT.format(label=label))
