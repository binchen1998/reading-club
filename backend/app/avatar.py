"""用户头像：emoji 或七牛 CDN 图片。"""

from __future__ import annotations

from . import qiniu_upload
from .models import User

DEFAULT_AVATAR = "📖"


def display_avatar(user: User | None, *, fallback: str = DEFAULT_AVATAR) -> str:
    if user is None:
        return fallback
    if getattr(user, "avatar_url", None):
        return user.avatar_url
    return user.avatar or fallback


def apply_avatar(
    user: User,
    *,
    avatar: str | None = None,
    avatar_key: str | None = None,
) -> None:
    if avatar_key:
        user.avatar_url = qiniu_upload.cdn_url(avatar_key)
        user.avatar = ""
        return
    if avatar is None:
        return
    user.avatar = avatar[:20]
    user.avatar_url = ""
