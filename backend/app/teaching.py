"""课堂助教问答（同步，OpenAI nano）。"""

from __future__ import annotations

import logging
import re

from fastapi import HTTPException

from .openai_llm import assistant_model, complete, get_openai_client, openai_base_url

logger = logging.getLogger("teaching")

CHAT_SYSTEM = """你是一名专业的中国少儿英语教师，正在给 6—10 岁孩子上英语章节书阅读课。

请结合「当前页内容」、对话历史和当前问题，生成老师的口播回复。

硬性规则：
1. 回复简短：通常 1—2 句，尽量控制在约 40 个汉字以内；可夹少量英文单词或短句。
2. 语气亲切、清楚，适合直接读给孩子听；不要使用宝宝腔或叠词。
3. 优先围绕当前页英文与讲解回答；材料不足时也可做简短引导，不要动辄说「回答不了」。
4. 不要输出 Markdown、列表符号或 JSON，只输出一段可口播的纯文本。
"""


def chat_reply(
    *,
    book_title: str,
    student_text: str,
    current_page: int | None,
    current_english: str,
    current_script: str,
    messages: list[dict],
) -> str:
    client = get_openai_client()
    if client is None:
        raise HTTPException(status_code=503, detail="未配置 OPENAI_API_KEY，无法进行课堂问答")
    try:
        openai_base_url()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    text = (student_text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="请先说话")
    history: list[dict[str, str]] = []
    for item in messages[-40:]:
        role = str(item.get("role") or "").strip().lower()
        content = str(item.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            history.append({"role": role, "content": content[:4000]})
    page_context = (
        f"【书】{book_title or '未知'}\n"
        f"【当前页】{current_page}\n"
        f"【当前页英文】{(current_english or '（无）')[:1200]}\n"
        f"【当前页讲解】{(current_script or '（无）')[:800]}"
    )
    user_prompt = (
        f"{page_context}\n\n【学生刚说的话】\n{text}\n\n"
        "请结合对话历史与当前页内容，按系统规则生成简短的老师口播回复。"
    )
    try:
        resp = complete(
            client,
            [
                {"role": "system", "content": CHAT_SYSTEM},
                {"role": "system", "content": page_context},
                *history,
                {"role": "user", "content": user_prompt},
            ],
            model=assistant_model(),
            max_completion_tokens=256,
        )
    except Exception as exc:
        logger.exception("assistant chat failed")
        raise HTTPException(status_code=502, detail=f"助教暂时没有回复：{exc}") from exc
    reply = (resp.choices[0].message.content or "").strip()
    reply = re.sub(r"^```[\s\S]*?```$", "", reply).strip()
    if not reply:
        raise HTTPException(status_code=502, detail="助教暂时没有回复，请再试一次")
    return reply
