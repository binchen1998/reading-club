from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from ..auth import get_optional_user
from ..cache_keys import PROFILE, PROFILE_INDEX
from ..db import get_db
from ..models import Recording, User
from ..page_cache import cache_get, cache_set
from .users import serialize_user

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("/{user_key}")
def profile(
    user_key: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
    viewer: User | None = Depends(get_optional_user),
):
    owner = db.get(User, user_key)
    if owner is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    cache_key = PROFILE.format(username=user_key, page=page, page_size=page_size)
    cached = cache_get(cache_key)
    if isinstance(cached, dict):
        cached = dict(cached)
        cached["isSelf"] = bool(viewer and viewer.username == user_key)
        return cached
    total = (
        db.execute(
            select(func.count()).select_from(Recording).where(
                Recording.username == user_key,
                Recording.status == "completed",
                Recording.is_public.is_(True),
            )
        ).scalar()
        or 0
    )
    rows = (
        db.execute(
            select(Recording)
            .where(
                Recording.username == user_key,
                Recording.status == "completed",
                Recording.is_public.is_(True),
            )
            .order_by(desc(Recording.completed_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    payload = {
        "user": serialize_user(owner),
        "total": int(total),
        "page": page,
        "pageSize": page_size,
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
    payload["isSelf"] = bool(viewer and viewer.username == user_key)
    return payload
