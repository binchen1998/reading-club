from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, func, select, update
from sqlalchemy.orm import Session

from .. import qiniu_upload
from ..auth import assert_user_not_muted, get_current_user
from ..avatar import apply_avatar, display_avatar
from ..cache_invalidate import invalidate_notif_list, invalidate_user_display
from ..cache_keys import NOTIF_LIST, NOTIF_LIST_INDEX, NOTIF_UNREAD, USER_ME
from ..db import get_db
from ..display_name import leaderboard_display_name
from ..models import Notification, User
from ..moderation import moderate_text
from ..nickname import (
    assert_nickname_available,
    assert_nickname_content_safe,
    has_custom_nickname,
    normalize_nickname,
)
from ..notif_cache import get_unread_count, invalidate_unread_count, set_unread_count
from ..page_cache import cache_get, cache_set
from ..redis_client import get_redis

router = APIRouter(prefix="/api/users", tags=["users"])


def serialize_user(user: User) -> dict:
    custom = has_custom_nickname(user.username, user.nickname)
    return {
        "username": user.username,
        "nickname": user.nickname if custom else leaderboard_display_name(user),
        "avatar": display_avatar(user),
        "avatarEmoji": user.avatar or "",
        "avatarUrl": getattr(user, "avatar_url", "") or "",
        "bio": user.bio or "",
        "isMuted": bool(getattr(user, "is_muted", False)),
        "isGuest": user.username.startswith("888-"),
        "hasCustomNickname": custom,
        "createdAt": user.created_at.isoformat() if user.created_at else None,
        "updatedAt": user.updated_at.isoformat() if getattr(user, "updated_at", None) else None,
    }


def _after_profile_write(user: User, db: Session) -> dict:
    payload = serialize_user(user)
    invalidate_user_display(db, user.username)
    cache_set(USER_ME.format(username=user.username), payload)
    return payload


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    key = USER_ME.format(username=user.username)
    cached = cache_get(key)
    if isinstance(cached, dict):
        return cached
    payload = serialize_user(user)
    cache_set(key, payload)
    return payload


class NicknameIn(BaseModel):
    nickname: str


class BioIn(BaseModel):
    bio: str = ""


class AvatarCompleteIn(BaseModel):
    avatar_key: str = ""
    avatar: str | None = None


class ProfileIn(BaseModel):
    nickname: str = ""
    bio: str = ""


@router.put("/nickname")
def set_nickname(
    payload: NicknameIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """设置公开昵称：必须唯一，并经 AI 审核。"""
    assert_user_not_muted(user)
    nickname = normalize_nickname(payload.nickname)
    if not nickname:
        raise HTTPException(status_code=400, detail="昵称不能为空")
    if nickname == user.username or nickname.startswith("888-") or nickname.startswith(("阅读用户", "练习用户")):
        raise HTTPException(status_code=400, detail="昵称不能使用账号相关内容")
    if len(nickname) == 11 and nickname.isdigit() and nickname.startswith("1"):
        raise HTTPException(status_code=400, detail="昵称不能使用手机号")
    if nickname == user.nickname:
        return _after_profile_write(user, db)
    assert_nickname_available(db, nickname, exclude_username=user.username)
    assert_nickname_content_safe(nickname)
    user.nickname = nickname
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return _after_profile_write(user, db)


@router.put("/bio")
def set_bio(payload: BioIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    assert_user_not_muted(user)
    bio = (payload.bio or "").strip()
    if len(bio) > 200:
        raise HTTPException(status_code=400, detail="个人介绍不能超过 200 字")
    if bio:
        ok, reason = moderate_text(bio, label="个人介绍")
        if not ok:
            raise HTTPException(status_code=422, detail=reason or "个人介绍未通过审核")
    user.bio = bio
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return _after_profile_write(user, db)


@router.post("/avatar/prepare")
def avatar_prepare(user: User = Depends(get_current_user)):
    if not qiniu_upload.qiniu_enabled():
        raise HTTPException(status_code=503, detail="头像上传暂未配置")
    key = qiniu_upload.build_avatar_key(user.username)
    return {
        "upload_host": qiniu_upload.upload_host(),
        "avatar_key": key,
        "avatar": qiniu_upload.create_upload_token(key),
    }


@router.post("/avatar/complete")
def avatar_complete(
    payload: AvatarCompleteIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    key = (payload.avatar_key or "").strip()
    emoji = payload.avatar
    if key:
        if not qiniu_upload.qiniu_enabled():
            raise HTTPException(status_code=503, detail="头像上传暂未配置")
        if not qiniu_upload.avatar_key_belongs_to_user(key, user.username):
            raise HTTPException(status_code=400, detail="无效的头像 key")
        apply_avatar(user, avatar_key=key)
    elif emoji is not None:
        apply_avatar(user, avatar=str(emoji))
    else:
        raise HTTPException(status_code=400, detail="缺少头像数据")
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return _after_profile_write(user, db)


def _notification_payload(row: Notification) -> dict:
    return {
        "id": row.id,
        "type": row.type,
        "actorUsername": row.actor_username,
        "actorNickname": leaderboard_display_name(None, row.actor_username or ""),
        "refId": row.ref_id,
        "message": row.message,
        "isRead": row.is_read,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/notifications/unread-count")
def unread_notification_count(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    redis = get_redis()
    if redis is not None:
        try:
            raw = redis.get(NOTIF_UNREAD.format(username=user.username))
            if raw is not None:
                count = max(0, int(raw))
                return {"count": count, "unreadCount": count}
        except Exception:
            pass
    count = get_unread_count(db, user.username)
    return {"count": count, "unreadCount": count}


@router.get("/notifications")
def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cache_key = NOTIF_LIST.format(username=user.username, page=page, page_size=page_size)
    cached = cache_get(cache_key)
    if isinstance(cached, dict):
        return cached
    filters = (Notification.username == user.username,)
    total = db.execute(select(func.count()).select_from(Notification).where(*filters)).scalar() or 0
    unread = get_unread_count(db, user.username)
    rows = list(
        db.execute(
            select(Notification)
            .where(*filters)
            .order_by(desc(Notification.id))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    actors = {
        u.username: u
        for u in db.execute(
            select(User).where(User.username.in_([r.actor_username for r in rows if r.actor_username] or [""]))
        ).scalars().all()
    } if rows else {}
    items = []
    for row in rows:
        item = _notification_payload(row)
        if row.actor_username:
            item["actorNickname"] = leaderboard_display_name(actors.get(row.actor_username), row.actor_username)
        items.append(item)
    payload = {
        "total": int(total),
        "unreadCount": int(unread),
        "page": page,
        "pageSize": page_size,
        "items": items,
    }
    cache_set(cache_key, payload, indexes=[NOTIF_LIST_INDEX.format(username=user.username)])
    return payload


@router.post("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.get(Notification, notification_id)
    if row is None or row.username != user.username:
        raise HTTPException(status_code=404, detail="消息不存在")
    was_unread = not row.is_read
    row.is_read = True
    db.commit()
    if was_unread:
        invalidate_unread_count(user.username)
    invalidate_notif_list(user.username)
    return {"ok": True}


@router.post("/notifications/read-all")
def mark_all_notifications_read(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = db.execute(
        update(Notification)
        .where(Notification.username == user.username, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    db.commit()
    set_unread_count(user.username, 0)
    invalidate_notif_list(user.username)
    return {"ok": True, "updated": int(result.rowcount or 0), "unreadCount": 0}


@router.post("/me")
def update_me(payload: ProfileIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.nickname.strip():
        return set_nickname(NicknameIn(nickname=payload.nickname), user, db)
    return set_bio(BioIn(bio=payload.bio), user, db)
