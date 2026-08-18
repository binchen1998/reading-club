from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from ..auth import assert_user_not_muted, get_current_user, get_optional_user, is_guest
from ..avatar import display_avatar
from ..cache_invalidate import invalidate_follow_graph, invalidate_profile_wall
from ..cache_keys import (
    FOLLOWERS,
    FOLLOWERS_INDEX,
    FOLLOWING,
    FOLLOWING_INDEX,
    PROFILE,
    PROFILE_INDEX,
    PROFILE_WALL,
    PROFILE_WALL_ALL_INDEX,
    PROFILE_WALL_INDEX,
)
from ..config import QWEN_API_KEY
from ..db import get_db
from ..display_name import leaderboard_display_name
from ..moderation import moderate_text
from ..models import Follow, Recording, User, UserMessage
from ..notifications import create_notification
from ..page_cache import cache_get, cache_set
from ..schemas import WallMessageIn
from .users import serialize_user

router = APIRouter(prefix="/api/profile", tags=["profile"])

_MAX_REPLIES_PER_PARENT = 20


def _people_payload(username: str, user: User | None) -> dict:
    return {
        "username": username,
        "nickname": leaderboard_display_name(user, username),
        "avatar": display_avatar(user),
    }


def _message_payload(message: UserMessage, author: User | None) -> dict:
    return {
        "id": message.id,
        "parentId": message.parent_id,
        "username": message.author_username,
        "authorUsername": message.author_username,
        "authorName": leaderboard_display_name(author, message.author_username),
        "authorAvatar": display_avatar(author),
        "content": message.content,
        "status": message.status,
        "createdAt": message.created_at.isoformat() if message.created_at else None,
    }


@router.get("/{user_key}")
def profile(
    user_key: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    works_page: int | None = Query(None),
    works_page_size: int | None = Query(None),
    db: Session = Depends(get_db),
    viewer: User | None = Depends(get_optional_user),
):
    page = works_page or page
    page_size = works_page_size or page_size
    owner = db.get(User, user_key)
    if owner is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    cache_key = PROFILE.format(username=user_key, page=page, page_size=page_size)
    cached = cache_get(cache_key)
    if isinstance(cached, dict):
        payload = dict(cached)
    else:
        works_filters = (
            Recording.username == user_key,
            Recording.status == "completed",
            Recording.is_public.is_(True),
        )
        counts = db.execute(
            select(
                select(func.count()).select_from(Follow).where(Follow.following == user_key).scalar_subquery(),
                select(func.count()).select_from(Follow).where(Follow.follower == user_key).scalar_subquery(),
                select(func.count()).select_from(Recording).where(*works_filters).scalar_subquery(),
            )
        ).one()
        followers = int(counts[0] or 0)
        following = int(counts[1] or 0)
        total = int(counts[2] or 0)
        rows = (
            db.execute(
                select(Recording)
                .where(*works_filters)
                .order_by(desc(Recording.completed_at), desc(Recording.id))
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            .scalars()
            .all()
        )
        payload = {
            "user": serialize_user(owner),
            "username": owner.username,
            "nickname": leaderboard_display_name(owner),
            "avatar": display_avatar(owner),
            "avatarUrl": getattr(owner, "avatar_url", "") or "",
            "bio": owner.bio or "",
            "followers": followers,
            "following": following,
            "total": total,
            "worksTotal": total,
            "page": page,
            "pageSize": page_size,
            "worksPage": page,
            "worksPageSize": page_size,
            "works": [
                {
                    "id": row.id,
                    "bookTitle": row.book_title,
                    "page": row.page,
                    "overallScore": row.overall_score,
                    "videoUrl": row.video_url,
                    "thumbUrl": row.thumb_url,
                    "likeCount": row.like_count,
                    "lessonDate": row.lesson_date.isoformat() if row.lesson_date else None,
                }
                for row in rows
            ],
        }
        cache_set(cache_key, payload, indexes=[PROFILE_INDEX.format(username=user_key)])

    is_following = False
    if viewer and viewer.username != user_key:
        is_following = (
            db.execute(
                select(Follow.id).where(
                    Follow.follower == viewer.username,
                    Follow.following == user_key,
                )
            ).scalar_one_or_none()
            is not None
        )
    payload["isFollowing"] = is_following
    payload["isSelf"] = bool(viewer and viewer.username == user_key)
    return payload


@router.post("/{user_key}/follow")
def follow_user(
    user_key: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if is_guest(user.username):
        raise HTTPException(status_code=403, detail="游客不能关注")
    assert_user_not_muted(user)
    if user_key == user.username:
        raise HTTPException(status_code=400, detail="不能关注自己")
    target = db.get(User, user_key)
    if target is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    existing = db.execute(
        select(Follow).where(Follow.follower == user.username, Follow.following == user_key)
    ).scalar_one_or_none()
    if existing is None:
        db.add(Follow(follower=user.username, following=user_key))
        create_notification(db, username=user_key, type="follow", actor_username=user.username)
        db.commit()
        invalidate_follow_graph(user.username, user_key)
    followers = db.execute(select(func.count()).select_from(Follow).where(Follow.following == user_key)).scalar() or 0
    return {"ok": True, "following": True, "followers": int(followers)}


@router.post("/{user_key}/unfollow")
def unfollow_user(
    user_key: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = db.execute(
        select(Follow).where(Follow.follower == user.username, Follow.following == user_key)
    ).scalar_one_or_none()
    if existing:
        db.delete(existing)
        db.commit()
        invalidate_follow_graph(user.username, user_key)
    followers = db.execute(select(func.count()).select_from(Follow).where(Follow.following == user_key)).scalar() or 0
    return {"ok": True, "following": False, "followers": int(followers)}


@router.get("/{user_key}/followers")
def list_followers(
    user_key: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    cache_key = FOLLOWERS.format(username=user_key, page=page, page_size=page_size)
    cached = cache_get(cache_key)
    if isinstance(cached, dict):
        return cached
    total = db.execute(select(func.count()).select_from(Follow).where(Follow.following == user_key)).scalar() or 0
    rows = list(
        db.execute(
            select(Follow)
            .where(Follow.following == user_key)
            .order_by(desc(Follow.id))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    users = _author_users(db, [r.follower for r in rows])
    payload = {
        "total": int(total),
        "page": page,
        "pageSize": page_size,
        "items": [_people_payload(r.follower, users.get(r.follower)) for r in rows],
    }
    cache_set(cache_key, payload, indexes=[FOLLOWERS_INDEX.format(username=user_key)])
    return payload


@router.get("/{user_key}/following")
def list_following(
    user_key: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    cache_key = FOLLOWING.format(username=user_key, page=page, page_size=page_size)
    cached = cache_get(cache_key)
    if isinstance(cached, dict):
        return cached
    total = db.execute(select(func.count()).select_from(Follow).where(Follow.follower == user_key)).scalar() or 0
    rows = list(
        db.execute(
            select(Follow)
            .where(Follow.follower == user_key)
            .order_by(desc(Follow.id))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    users = _author_users(db, [r.following for r in rows])
    payload = {
        "total": int(total),
        "page": page,
        "pageSize": page_size,
        "items": [_people_payload(r.following, users.get(r.following)) for r in rows],
    }
    cache_set(cache_key, payload, indexes=[FOLLOWING_INDEX.format(username=user_key)])
    return payload


def _author_users(db: Session, usernames: list[str]) -> dict[str, User]:
    names = [name for name in set(usernames) if name]
    if not names:
        return {}
    return {u.username: u for u in db.execute(select(User).where(User.username.in_(names))).scalars().all()}


@router.get("/{user_key}/messages")
def list_wall_messages(
    user_key: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    cache_key = PROFILE_WALL.format(username=user_key, page=page, page_size=page_size)
    cached = cache_get(cache_key)
    if isinstance(cached, dict):
        return cached
    if db.get(User, user_key) is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    filters = (
        UserMessage.wall_username == user_key,
        UserMessage.parent_id.is_(None),
        UserMessage.status == "approved",
    )
    total = db.execute(select(func.count()).select_from(UserMessage).where(*filters)).scalar() or 0
    messages = list(
        db.execute(
            select(UserMessage)
            .where(*filters)
            .order_by(desc(UserMessage.id))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    parent_ids = [m.id for m in messages]
    replies = list(
        db.execute(
            select(UserMessage)
            .where(
                UserMessage.parent_id.in_(parent_ids or [0]),
                UserMessage.status == "approved",
            )
            .order_by(UserMessage.created_at.asc(), UserMessage.id.asc())
            .limit(max(len(parent_ids), 1) * _MAX_REPLIES_PER_PARENT)
        )
        .scalars()
        .all()
    )
    authors = _author_users(db, [m.author_username for m in messages + replies])
    reply_map: dict[int, list[dict]] = {}
    for reply in replies:
        bucket = reply_map.setdefault(int(reply.parent_id or 0), [])
        if len(bucket) >= _MAX_REPLIES_PER_PARENT:
            continue
        bucket.append(_message_payload(reply, authors.get(reply.author_username)))
    payload = {
        "total": int(total),
        "page": page,
        "pageSize": page_size,
        "items": [
            {**_message_payload(message, authors.get(message.author_username)), "replies": reply_map.get(message.id, [])}
            for message in messages
        ],
    }
    cache_set(
        cache_key,
        payload,
        indexes=[
            PROFILE_WALL_INDEX.format(username=user_key),
            PROFILE_WALL_ALL_INDEX,
        ],
    )
    return payload


@router.post("/{user_key}/messages")
def create_wall_message(
    user_key: str,
    payload: WallMessageIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if is_guest(user.username):
        raise HTTPException(status_code=403, detail="游客不能留言")
    assert_user_not_muted(user)
    owner = db.get(User, user_key)
    if owner is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    content = (payload.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="留言不能为空")
    if len(content) > 500:
        raise HTTPException(status_code=400, detail="留言不能超过 500 字")
    ok, reason = moderate_text(content, label="留言")
    if not ok:
        raise HTTPException(status_code=422, detail=reason or "留言未通过审核")
    status = "approved" if (not (QWEN_API_KEY or "").strip() or ok) else "pending"
    parent_id = payload.parent_id
    if parent_id is not None:
        parent = db.get(UserMessage, parent_id)
        if parent is None or parent.wall_username != user_key or parent.status == "rejected":
            raise HTTPException(status_code=404, detail="回复目标不存在")
        parent_id = parent.parent_id or parent.id
    message = UserMessage(
        wall_username=user_key,
        author_username=user.username,
        content=content,
        parent_id=parent_id,
        status=status,
    )
    db.add(message)
    db.flush()
    if status == "approved":
        create_notification(
            db,
            username=user_key,
            type="wall_message",
            actor_username=user.username,
            ref_id=message.id,
            message=f"{leaderboard_display_name(user)} 留言：{content[:80]}",
        )
    db.commit()
    db.refresh(message)
    if status == "approved":
        invalidate_profile_wall(user_key)
    return _message_payload(message, user)


@router.delete("/{user_key}/messages/{message_id}")
def delete_wall_message(
    user_key: str,
    message_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    message = db.get(UserMessage, message_id)
    if message is None or message.wall_username != user_key:
        raise HTTPException(status_code=404, detail="留言不存在")
    if user.username not in {message.author_username, user_key}:
        raise HTTPException(status_code=403, detail="无权删除该留言")
    message.status = "rejected"
    db.commit()
    invalidate_profile_wall(user_key)
    return {"ok": True}
