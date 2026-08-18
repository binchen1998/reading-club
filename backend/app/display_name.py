"""公开场景的展示名：手机号 / 游客号脱敏。"""

import hashlib
import re

from .nickname import has_custom_nickname

PHONE_LIKE_RE = re.compile(r"^1\d{10}$")
MASKED_PHONE_RE = re.compile(r"^1\d{2}\*{4}\d{4}$")
MASKED_GUEST_RE = re.compile(r"^888-\*{4}\d{0,8}$")
ANON_PREFIX = "阅读用户"


def mask_phone(value: str) -> str:
    s = (value or "").strip()
    if not PHONE_LIKE_RE.fullmatch(s):
        return s
    return f"{s[:3]}****{s[-4:]}"


def mask_guest_id(value: str) -> str:
    s = (value or "").strip()
    if not s.startswith("888-"):
        return s
    rest = s[4:]
    if len(rest) <= 4:
        return "888-****"
    return f"888-****{rest[-4:]}"


def mask_sensitive_id(value: str) -> str | None:
    s = (value or "").strip()
    if not s:
        return None
    if MASKED_PHONE_RE.fullmatch(s) or MASKED_GUEST_RE.fullmatch(s):
        return s
    if PHONE_LIKE_RE.fullmatch(s):
        return mask_phone(s)
    if s.startswith("888-"):
        return mask_guest_id(s)
    return None


def anonymous_display_name(username: str = "") -> str:
    uname = (username or "").strip()
    masked = mask_sensitive_id(uname)
    if masked:
        return masked
    if not uname:
        return ANON_PREFIX
    digest = hashlib.sha256(uname.encode("utf-8")).hexdigest()[:4]
    return f"{ANON_PREFIX}_{digest}"


def leaderboard_display_name(user, username: str = "") -> str:
    uname = (getattr(user, "username", None) or username or "").strip()
    if user is None:
        return anonymous_display_name(uname)
    nick = (user.nickname or "").strip()
    nick_masked = mask_sensitive_id(nick)
    if nick_masked:
        return nick_masked
    if has_custom_nickname(user.username, nick):
        return nick
    return anonymous_display_name(user.username or uname)
