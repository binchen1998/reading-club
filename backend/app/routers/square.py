from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from ..auth import assert_user_not_muted, get_current_user, get_optional_user, is_guest
from ..avatar import display_avatar
from ..cache_invalidate import invalidate_square_comments, invalidate_square_detail
from ..cache_keys import (
    SQUARE_COMMENTS,
    SQUARE_COMMENTS_ALL_INDEX,
    SQUARE_COMMENTS_INDEX,
    SQUARE_DETAIL,
    SQUARE_DETAIL_INDEX,
)
from ..db import get_db
from ..display_name import leaderboard_display_name
from ..moderation import moderate_text
from ..models import Recording, RecordingComment, RecordingLike, User
from ..notifications import create_notification
from ..page_cache import cache_get, cache_set
from ..schemas import CommentIn
from ..square_snapshot import FIRST_PAGE_SIZE, get_sort_items, load_snapshot, normalize_sort, snapshot_is_ready

router = APIRouter(prefix="/api/square", tags=["square"])

_MAX_REPLIES_PER_PARENT = 20


def serialize_public(row: Recording, nickname: str = "", avatar: str = "") -> dict:
    return {
        "id": row.id,
        "username": row.username,
        "nickname": nickname or row.username,
        "avatar": avatar,
        "bookTitle": row.book_title,
        "page": row.page,
        "lessonDate": row.lesson_date.isoformat() if row.lesson_date else None,
        "durationSec": row.duration_sec,
        "overallScore": row.overall_score,
        "videoUrl": row.video_url,
        "thumbUrl": row.thumb_url,
        "likeCount": row.like_count,
    }


def _author_map(db: Session, usernames: list[str]) -> dict[str, User]:
    names = [name for name in set(usernames) if name]
    if not names:
        return {}
    rows = db.execute(select(User).where(User.username.in_(names))).scalars().all()
    return {u.username: u for u in rows}


def _comment_payload(comment: RecordingComment, author: User | None) -> dict:
    return {
        "id": comment.id,
        "parentId": comment.parent_id,
        "username": comment.username,
        "authorName": leaderboard_display_name(author, comment.username),
        "authorAvatar": display_avatar(author),
        "content": comment.content,
        "moderated": comment.moderated,
        "createdAt": comment.created_at.isoformat() if comment.created_at else None,
    }


@router.get("/stats")
def square_stats():
    snap = load_snapshot()
    return snap.get("stats") or {"publicCount": 0, "todayCount": 0}


@router.get("/list")
def square_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    sort: str = Query("latest"),
    db: Session = Depends(get_db),
):
    sort_key = normalize_sort(sort)
    snap = load_snapshot()
    if page == 1 and page_size <= FIRST_PAGE_SIZE and snapshot_is_ready(snap):
        items = get_sort_items(snap, sort_key)[:page_size]
        stats = snap.get("stats") or {}
        return {
            "page": 1,
            "pageSize": page_size,
            "total": int(stats.get("publicCount") or stats.get("public_count") or 0),
            "items": items,
            "fromSnapshot": True,
        }
    total = (
        db.execute(
            select(func.count()).select_from(Recording).where(
                Recording.status == "completed",
                Recording.is_public.is_(True),
            )
        ).scalar()
        or 0
    )
    order = desc(Recording.like_count) if sort_key == "likes" else desc(Recording.completed_at)
    rows = (
        db.execute(
            select(Recording)
            .where(Recording.status == "completed", Recording.is_public.is_(True))
            .order_by(order)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    owners = {
        u.username: u
        for u in db.execute(select(User).where(User.username.in_([r.username for r in rows] or ["__none__"]))).scalars()
    }
    return {
        "page": page,
        "pageSize": page_size,
        "total": int(total),
        "items": [
            serialize_public(
                row,
                leaderboard_display_name(owners.get(row.username), row.username),
                display_avatar(owners.get(row.username)),
            )
            for row in rows
        ],
        "fromSnapshot": False,
    }


@router.get("/{recording_id}")
def square_detail(
    recording_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    key = SQUARE_DETAIL.format(recording_id=recording_id)
    cached = cache_get(key)
    rec = db.get(Recording, recording_id)
    if rec is None or rec.status != "completed" or not rec.is_public:
        raise HTTPException(status_code=404, detail="作品不存在")
    owner = db.get(User, rec.username)
    liked = False
    if user:
        liked = (
            db.execute(
                select(RecordingLike.id).where(
                    RecordingLike.username == user.username,
                    RecordingLike.recording_id == recording_id,
                )
            ).scalar_one_or_none()
            is not None
        )
    payload = {
        **serialize_public(
            rec,
            leaderboard_display_name(owner, rec.username),
            display_avatar(owner),
        ),
        "liked": liked,
    }
    if not isinstance(cached, dict):
        cache_set(key, {k: v for k, v in payload.items() if k != "liked"}, indexes=[SQUARE_DETAIL_INDEX])
    return payload


@router.post("/{recording_id}/like")
def toggle_like(
    recording_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if is_guest(user.username):
        raise HTTPException(status_code=403, detail="游客不能点赞")
    assert_user_not_muted(user)
    rec = db.get(Recording, recording_id)
    if rec is None or rec.status != "completed":
        raise HTTPException(status_code=404, detail="作品不存在")
    row = db.execute(
        select(RecordingLike).where(
            RecordingLike.username == user.username,
            RecordingLike.recording_id == recording_id,
        )
    ).scalar_one_or_none()
    if row:
        db.delete(row)
        rec.like_count = max(0, rec.like_count - 1)
        liked = False
    else:
        db.add(RecordingLike(username=user.username, recording_id=recording_id))
        rec.like_count += 1
        liked = True
        create_notification(
            db,
            username=rec.username,
            type="like",
            actor_username=user.username,
            ref_id=recording_id,
        )
    db.commit()
    invalidate_square_detail(recording_id)
    return {"ok": True, "liked": liked, "likeCount": rec.like_count}


@router.delete("/{recording_id}/like")
def unlike_recording(
    recording_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rec = db.get(Recording, recording_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="作品不存在")
    row = db.execute(
        select(RecordingLike).where(
            RecordingLike.username == user.username,
            RecordingLike.recording_id == recording_id,
        )
    ).scalar_one_or_none()
    if row:
        db.delete(row)
        rec.like_count = max(0, rec.like_count - 1)
        db.commit()
        invalidate_square_detail(recording_id)
    return {"ok": True, "liked": False, "likeCount": rec.like_count}


@router.get("/{recording_id}/comments")
def list_comments(
    recording_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    cache_key = SQUARE_COMMENTS.format(recording_id=recording_id, page=page, page_size=page_size)
    cached = cache_get(cache_key)
    if isinstance(cached, dict):
        return cached

    rec = db.get(Recording, recording_id)
    if rec is None or rec.status != "completed":
        raise HTTPException(status_code=404, detail="作品不存在")
    filters = (
        RecordingComment.recording_id == recording_id,
        RecordingComment.parent_id.is_(None),
        RecordingComment.moderated.is_(True),
    )
    total = db.execute(select(func.count()).select_from(RecordingComment).where(*filters)).scalar() or 0
    comments = list(
        db.execute(
            select(RecordingComment)
            .where(*filters)
            .order_by(desc(RecordingComment.id))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    parent_ids = [c.id for c in comments]
    replies = list(
        db.execute(
            select(RecordingComment)
            .where(
                RecordingComment.parent_id.in_(parent_ids or [0]),
                RecordingComment.moderated.is_(True),
            )
            .order_by(RecordingComment.created_at.asc(), RecordingComment.id.asc())
            .limit(max(len(parent_ids), 1) * _MAX_REPLIES_PER_PARENT)
        )
        .scalars()
        .all()
    )
    authors = _author_map(db, [c.username for c in comments + replies])
    reply_map: dict[int, list[dict]] = {}
    for reply in replies:
        bucket = reply_map.setdefault(int(reply.parent_id or 0), [])
        if len(bucket) >= _MAX_REPLIES_PER_PARENT:
            continue
        bucket.append(_comment_payload(reply, authors.get(reply.username)))
    payload = {
        "total": int(total),
        "page": page,
        "pageSize": page_size,
        "items": [
            {**_comment_payload(c, authors.get(c.username)), "replies": reply_map.get(c.id, [])}
            for c in comments
        ],
    }
    cache_set(
        cache_key,
        payload,
        indexes=[
            SQUARE_COMMENTS_INDEX.format(recording_id=recording_id),
            SQUARE_COMMENTS_ALL_INDEX,
        ],
    )
    return payload


@router.post("/{recording_id}/comments")
def add_comment(
    recording_id: int,
    payload: CommentIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if is_guest(user.username):
        raise HTTPException(status_code=403, detail="游客不能评论")
    assert_user_not_muted(user)
    rec = db.get(Recording, recording_id)
    if rec is None or rec.status != "completed" or not rec.is_public:
        raise HTTPException(status_code=404, detail="作品不存在")
    content = (payload.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="评论不能为空")
    if len(content) > 500:
        raise HTTPException(status_code=400, detail="评论不能超过 500 字")
    ok, reason = moderate_text(content, label="评论")
    if not ok:
        raise HTTPException(status_code=422, detail=reason or "评论未通过审核")
    parent_id = payload.parent_id
    if parent_id is not None:
        parent = db.get(RecordingComment, parent_id)
        if parent is None or parent.recording_id != recording_id:
            raise HTTPException(status_code=404, detail="回复目标不存在")
        parent_id = parent.parent_id or parent.id
    comment = RecordingComment(
        recording_id=recording_id,
        username=user.username,
        content=content,
        parent_id=parent_id,
        moderated=True,
    )
    db.add(comment)
    db.flush()
    create_notification(
        db,
        username=rec.username,
        type="comment",
        actor_username=user.username,
        ref_id=recording_id,
        message=f"{leaderboard_display_name(user)} 评论了你的朗读：{content[:80]}",
    )
    db.commit()
    db.refresh(comment)
    invalidate_square_comments(recording_id)
    return _comment_payload(comment, user)


@router.delete("/{recording_id}/comments/{comment_id}")
def delete_comment(
    recording_id: int,
    comment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    comment = db.get(RecordingComment, comment_id)
    rec = db.get(Recording, recording_id)
    if comment is None or rec is None or comment.recording_id != recording_id:
        raise HTTPException(status_code=404, detail="评论不存在")
    if user.username not in {comment.username, rec.username}:
        raise HTTPException(status_code=403, detail="无权删除该评论")
    db.delete(comment)
    db.commit()
    invalidate_square_comments(recording_id)
    return {"ok": True}
