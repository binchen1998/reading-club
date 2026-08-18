"""昵称校验与默认昵称分配。自定义昵称必须唯一，并走 AI 审核。"""

import re
import secrets

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import User
from .moderation import moderate_nickname

DEFAULT_NICK_PREFIX = "阅读达人_"
PHONE_LIKE_RE = re.compile(r"^1\d{10}$")
DEFAULT_NICK_PREFIXES = ("阅读达人_", "练习达人_")
ANON_PREFIXES = ("阅读用户", "练习用户")


def normalize_nickname(raw: str) -> str:
    return (raw or "").strip()[:50]


def has_custom_nickname(username: str, nickname: str | None) -> bool:
    uname = (username or "").strip()
    nick = (nickname or "").strip()
    if not nick or nick == uname:
        return False
    if nick.startswith("888-"):
        return False
    if any(nick.startswith(prefix) for prefix in DEFAULT_NICK_PREFIXES):
        return False
    if any(nick.startswith(prefix) for prefix in ANON_PREFIXES):
        return False
    if PHONE_LIKE_RE.fullmatch(nick):
        return False
    return True


def assert_nickname_available(
    db: Session,
    nickname: str,
    *,
    exclude_username: str | None = None,
) -> str:
    nick = normalize_nickname(nickname)
    if not nick:
        raise HTTPException(status_code=400, detail="昵称不能为空")
    stmt = select(User.username).where(func.lower(User.nickname) == nick.lower())
    if exclude_username:
        stmt = stmt.where(User.username != exclude_username)
    taken = db.execute(stmt.limit(1)).scalar_one_or_none()
    if taken is not None:
        raise HTTPException(status_code=400, detail="该昵称已被使用，请换一个")
    return nick


def assert_nickname_content_safe(nickname: str) -> None:
    passed, reason = moderate_nickname(nickname)
    if not passed:
        raise HTTPException(status_code=422, detail=reason or "昵称未通过审核，请换一个")


def allocate_default_nickname(db: Session, *, exclude_username: str) -> str:
    for _ in range(80):
        nick = f"{DEFAULT_NICK_PREFIX}{secrets.token_hex(2)}"
        taken = (
            db.execute(
                select(User.username)
                .where(User.nickname == nick, User.username != exclude_username)
                .limit(1)
            ).scalar_one_or_none()
        )
        if taken is None:
            return nick
    raise HTTPException(status_code=500, detail="无法分配默认昵称，请稍后再试")
