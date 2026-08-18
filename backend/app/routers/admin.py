from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from ..auth import check_admin_credentials, create_admin_token, require_admin
from ..cache_invalidate import invalidate_square_detail
from ..db import get_db
from ..models import GeneratedAsset, Recording, User, WrongItem
from ..timeutil import shanghai_today

router = APIRouter(prefix="/api/admin", tags=["admin"])


class AdminLoginIn(BaseModel):
    username: str
    password: str


class MuteIn(BaseModel):
    muted: bool | None = None
    is_muted: bool | None = None

    def resolved(self) -> bool:
        if self.muted is not None:
            return bool(self.muted)
        if self.is_muted is not None:
            return bool(self.is_muted)
        raise ValueError("缺少 muted")


def serialize_recording(row: Recording) -> dict:
    return {
        "id": row.id,
        "username": row.username,
        "status": row.status,
        "seriesId": row.series_id,
        "bookSlug": row.book_slug,
        "bookTitle": row.book_title,
        "chapterId": row.chapter_id,
        "page": row.page,
        "lessonDate": row.lesson_date.isoformat() if row.lesson_date else None,
        "durationSec": row.duration_sec,
        "overallScore": row.overall_score,
        "videoUrl": row.video_url,
        "thumbUrl": row.thumb_url,
        "isPublic": row.is_public,
        "likeCount": row.like_count,
        "completedAt": row.completed_at.isoformat() if row.completed_at else None,
    }


@router.post("/login")
def admin_login(payload: AdminLoginIn):
    if not check_admin_credentials(payload.username.strip(), payload.password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return {"token": create_admin_token(), "username": "admin"}


@router.get("/stats")
def admin_stats(_: bool = Depends(require_admin), db: Session = Depends(get_db)):
    today = shanghai_today()
    user_count = db.execute(select(func.count()).select_from(User)).scalar() or 0
    practice_count = db.execute(select(func.count()).select_from(Recording)).scalar() or 0
    completed_count = (
        db.execute(select(func.count()).select_from(Recording).where(Recording.status == "completed")).scalar()
        or 0
    )
    today_practices = (
        db.execute(
            select(func.count())
            .select_from(Recording)
            .where(Recording.status == "completed", Recording.lesson_date == today)
        ).scalar()
        or 0
    )
    wrong_open = (
        db.execute(select(func.count()).select_from(WrongItem).where(WrongItem.resolved_at.is_(None))).scalar()
        or 0
    )
    tts_count = (
        db.execute(select(func.count()).select_from(GeneratedAsset).where(GeneratedAsset.kind == "tts")).scalar()
        or 0
    )
    ocr_count = (
        db.execute(select(func.count()).select_from(GeneratedAsset).where(GeneratedAsset.kind == "ocr")).scalar()
        or 0
    )
    return {
        "user_count": int(user_count),
        "practice_count": int(practice_count),
        "completed_count": int(completed_count),
        "today_practices": int(today_practices),
        "wrong_open": int(wrong_open),
        "tts_count": int(tts_count),
        "ocr_count": int(ocr_count),
    }


@router.get("/users")
def admin_users(
    q: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    limit: int | None = Query(None),
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    size = min(limit, 200) if limit else page_size
    filters = []
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        filters.append(or_(User.username.ilike(like), User.nickname.ilike(like)))
    total_stmt = select(func.count()).select_from(User)
    if filters:
        total_stmt = total_stmt.where(*filters)
    total = db.execute(total_stmt).scalar() or 0
    stmt = select(User).order_by(desc(User.created_at)).offset((page - 1) * size).limit(size)
    if filters:
        stmt = stmt.where(*filters)
    users = list(db.execute(stmt).scalars().all())
    names = [u.username for u in users]
    counts: dict[str, int] = {}
    if names:
        rows = db.execute(
            select(Recording.username, func.count())
            .where(Recording.username.in_(names), Recording.status == "completed")
            .group_by(Recording.username)
        ).all()
        counts = {name: int(n) for name, n in rows}
    return {
        "total": int(total),
        "page": page,
        "pageSize": size,
        "items": [
            {
                "username": u.username,
                "nickname": u.nickname,
                "bio": u.bio or "",
                "isMuted": bool(getattr(u, "is_muted", False)),
                "is_muted": bool(getattr(u, "is_muted", False)),
                "practice_count": counts.get(u.username, 0),
                "createdAt": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ],
    }


@router.put("/users/{username}/mute")
def admin_mute_user(
    username: str,
    payload: MuteIn,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    target = username.strip()
    if not target:
        raise HTTPException(status_code=400, detail="用户名不能为空")
    user = db.get(User, target)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    try:
        user.is_muted = payload.resolved()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return {
        "ok": True,
        "username": target,
        "nickname": user.nickname or target,
        "isMuted": bool(user.is_muted),
        "is_muted": bool(user.is_muted),
    }


@router.get("/practices")
def admin_practices(
    status: str = Query("all"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    limit: int | None = Query(None),
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    size = min(limit, 200) if limit else page_size
    filters = []
    if status in ("pending", "completed"):
        filters.append(Recording.status == status)
    total_stmt = select(func.count()).select_from(Recording)
    if filters:
        total_stmt = total_stmt.where(*filters)
    total = db.execute(total_stmt).scalar() or 0
    stmt = select(Recording).order_by(desc(Recording.id)).offset((page - 1) * size).limit(size)
    if filters:
        stmt = stmt.where(*filters)
    rows = list(db.execute(stmt).scalars().all())
    return {
        "total": int(total),
        "page": page,
        "pageSize": size,
        "items": [serialize_recording(row) for row in rows],
    }


@router.put("/practices/{practice_id}/unpublish")
def admin_unpublish_practice(
    practice_id: int,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    rec = db.get(Recording, practice_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="朗读不存在")
    rec.is_public = False
    db.commit()
    db.refresh(rec)
    invalidate_square_detail(rec.id)
    return serialize_recording(rec)


@router.put("/practices/{practice_id}/publish")
def admin_publish_practice(
    practice_id: int,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    rec = db.get(Recording, practice_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="朗读不存在")
    rec.is_public = True
    db.commit()
    db.refresh(rec)
    invalidate_square_detail(rec.id)
    return serialize_recording(rec)


@router.get("/wrongs")
def admin_wrongs(
    status: str = Query("open"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    filters = []
    if status == "open":
        filters.append(WrongItem.resolved_at.is_(None))
    elif status == "resolved":
        filters.append(WrongItem.resolved_at.is_not(None))
    total_stmt = select(func.count()).select_from(WrongItem)
    if filters:
        total_stmt = total_stmt.where(*filters)
    total = db.execute(total_stmt).scalar() or 0
    stmt = select(WrongItem).order_by(desc(WrongItem.last_wrong_at)).offset((page - 1) * page_size).limit(page_size)
    if filters:
        stmt = stmt.where(*filters)
    rows = list(db.execute(stmt).scalars().all())
    return {
        "total": int(total),
        "page": page,
        "pageSize": page_size,
        "items": [
            {
                "id": row.id,
                "username": row.username,
                "kind": row.kind,
                "en": row.en,
                "zh": row.zh,
                "bookTitle": row.book_title,
                "page": row.page,
                "wrongCount": row.wrong_count,
                "resolved": row.resolved_at is not None,
                "lastWrongAt": row.last_wrong_at.isoformat() if row.last_wrong_at else None,
            }
            for row in rows
        ],
    }


@router.get("/assets")
def admin_assets(
    kind: str = Query("all"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    filters = []
    if kind in ("tts", "ocr"):
        filters.append(GeneratedAsset.kind == kind)
    total_stmt = select(func.count()).select_from(GeneratedAsset)
    if filters:
        total_stmt = total_stmt.where(*filters)
    total = db.execute(total_stmt).scalar() or 0
    stmt = (
        select(GeneratedAsset)
        .order_by(desc(GeneratedAsset.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    if filters:
        stmt = stmt.where(*filters)
    rows = list(db.execute(stmt).scalars().all())
    return {
        "total": int(total),
        "page": page,
        "pageSize": page_size,
        "items": [
            {
                "id": row.id,
                "kind": row.kind,
                "label": row.label,
                "preview": row.preview,
                "source": row.source,
                "assetKey": row.asset_key,
                "createdAt": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ],
    }
