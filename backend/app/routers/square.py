from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from ..auth import assert_user_not_muted, get_current_user, get_optional_user, is_guest
from ..cache_invalidate import invalidate_square_detail
from ..cache_keys import SQUARE_DETAIL, SQUARE_DETAIL_INDEX
from ..db import get_db
from ..models import Recording, RecordingLike, User
from ..page_cache import cache_get, cache_set
from ..square_snapshot import FIRST_PAGE_SIZE, get_sort_items, load_snapshot, normalize_sort, snapshot_is_ready

router = APIRouter(prefix="/api/square", tags=["square"])


def serialize_public(row: Recording, nickname: str = "") -> dict:
    return {
        "id": row.id,
        "username": row.username,
        "nickname": nickname or row.username,
        "bookTitle": row.book_title,
        "page": row.page,
        "lessonDate": row.lesson_date.isoformat() if row.lesson_date else None,
        "durationSec": row.duration_sec,
        "overallScore": row.overall_score,
        "videoUrl": row.video_url,
        "thumbUrl": row.thumb_url,
        "likeCount": row.like_count,
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
    names = {
        u.username: u.nickname or u.username
        for u in db.execute(select(User).where(User.username.in_([r.username for r in rows] or ["__none__"]))).scalars()
    }
    return {
        "page": page,
        "pageSize": page_size,
        "total": int(total),
        "items": [serialize_public(row, names.get(row.username, "")) for row in rows],
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
        **serialize_public(rec, owner.nickname if owner else ""),
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
    db.commit()
    invalidate_square_detail(recording_id)
    return {"liked": liked, "likeCount": rec.like_count}
