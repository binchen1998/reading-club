from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from .. import qiniu_upload
from ..auth import assert_user_not_muted, get_current_user, is_guest
from ..cache_invalidate import invalidate_on_publish
from ..config import RECORDINGS
from ..db import get_db
from ..models import Recording, User
from ..routers.progress import ProgressIn, upsert_progress
from ..timeutil import shanghai_today

router = APIRouter(prefix="/api/practice", tags=["practice"])


class PrepareIn(BaseModel):
    series_id: str
    book_slug: str
    book_title: str = ""
    chapter_id: str
    page: int
    duration_sec: int = 0
    mime_type: str = "video/mp4"
    is_public: bool = False
    storage: str = "local"


class CompleteIn(BaseModel):
    video_key: str
    duration_sec: int = 0
    overall_score: int | None = None
    thumb_key: str = ""
    is_public: bool = False


class CloudIn(BaseModel):
    video_key: str
    thumb_key: str = ""
    is_public: bool = False


class VisibilityIn(BaseModel):
    is_public: bool


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
        "videoKey": row.video_key,
        "videoUrl": row.video_url,
        "thumbUrl": row.thumb_url,
        "isPublic": row.is_public,
        "likeCount": row.like_count,
        "completedAt": row.completed_at.isoformat() if row.completed_at else None,
        "canCloud": qiniu_upload.qiniu_enabled(),
    }


def _own_recording(db: Session, practice_id: int, user: User) -> Recording:
    rec = db.get(Recording, practice_id)
    if rec is None or rec.username != user.username:
        raise HTTPException(status_code=404, detail="录音不存在")
    return rec


@router.get("/mine")
def list_mine(
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filters = (
        Recording.username == user.username,
        Recording.status == "completed",
    )
    total = db.execute(select(func.count()).select_from(Recording).where(*filters)).scalar() or 0
    rows = (
        db.execute(
            select(Recording)
            .where(*filters)
            .order_by(desc(Recording.completed_at), desc(Recording.id))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return {
        "total": int(total),
        "page": page,
        "pageSize": page_size,
        "items": [serialize_recording(row) for row in rows],
    }


def _mark_progress(db: Session, rec: Recording) -> None:
    upsert_progress(
        db,
        rec.username,
        ProgressIn(
            series_id=rec.series_id,
            book_slug=rec.book_slug,
            book_title=rec.book_title,
            chapter_id=rec.chapter_id,
            page=rec.page,
            record_done=True,
            record_score=rec.overall_score,
            recording_id=rec.id,
        ),
    )


@router.post("/prepare")
def prepare(payload: PrepareIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if is_guest(user.username):
        raise HTTPException(status_code=403, detail="游客不能保存朗读")
    assert_user_not_muted(user)
    rec = Recording(
        username=user.username,
        status="pending",
        series_id=payload.series_id,
        book_slug=payload.book_slug,
        book_title=payload.book_title[:200],
        chapter_id=payload.chapter_id,
        page=payload.page,
        lesson_date=shanghai_today(),
        duration_sec=max(0, payload.duration_sec),
        is_public=False,
    )
    db.add(rec)
    db.flush()
    use_qiniu = (payload.storage or "local").strip().lower() == "qiniu" and qiniu_upload.qiniu_enabled()
    if use_qiniu:
        video_key = qiniu_upload.build_practice_key(user.username, rec.id, "mp4")
        thumb_key = qiniu_upload.build_thumb_key(user.username, rec.id, "jpg")
        db.commit()
        db.refresh(rec)
        return {
            **serialize_recording(rec),
            "mode": "qiniu",
            "upload_host": qiniu_upload.upload_host(),
            "video_key": video_key,
            "video": qiniu_upload.create_upload_token(video_key),
            "thumb_key": thumb_key,
            "thumb": qiniu_upload.create_upload_token(thumb_key),
        }
    db.commit()
    db.refresh(rec)
    return {
        **serialize_recording(rec),
        "mode": "local",
        "upload_url": f"/api/practice/{rec.id}/local",
        "video_key": "",
    }


@router.post("/{practice_id}/local")
async def local_upload(
    practice_id: int,
    file: UploadFile = File(...),
    overall_score: int = Form(0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rec = _own_recording(db, practice_id, user)
    assert_user_not_muted(user)
    if rec.status == "completed":
        raise HTTPException(status_code=400, detail="练习已完成，请勿重复提交")
    RECORDINGS.mkdir(parents=True, exist_ok=True)
    name = qiniu_upload.local_media_name(user.username, rec.id, "mp4")
    dest = RECORDINGS / name
    dest.write_bytes(await file.read())
    rec.video_key = name
    rec.video_url = f"/media/recordings/{name}"
    rec.overall_score = max(0, min(100, int(overall_score or 0)))
    rec.is_public = False
    rec.status = "completed"
    rec.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(rec)
    _mark_progress(db, rec)
    invalidate_on_publish(user.username, rec.id)
    return serialize_recording(rec)


@router.post("/{practice_id}/cloud-token")
def cloud_token(practice_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if is_guest(user.username):
        raise HTTPException(status_code=403, detail="游客不能上传朗读")
    assert_user_not_muted(user)
    rec = _own_recording(db, practice_id, user)
    if rec.status != "completed":
        raise HTTPException(status_code=400, detail="请先完成本地保存")
    if not qiniu_upload.qiniu_enabled():
        raise HTTPException(status_code=503, detail="未配置七牛，无法上传")
    video_key = qiniu_upload.build_practice_key(user.username, rec.id, "mp4")
    thumb_key = qiniu_upload.build_thumb_key(user.username, rec.id, "jpg")
    return {
        **serialize_recording(rec),
        "mode": "qiniu",
        "upload_host": qiniu_upload.upload_host(),
        "video_key": video_key,
        "video": qiniu_upload.create_upload_token(video_key),
        "thumb_key": thumb_key,
        "thumb": qiniu_upload.create_upload_token(thumb_key),
    }


@router.post("/{practice_id}/cloud")
def attach_cloud(
    practice_id: int,
    payload: CloudIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if is_guest(user.username):
        raise HTTPException(status_code=403, detail="游客不能上传朗读")
    assert_user_not_muted(user)
    rec = _own_recording(db, practice_id, user)
    if rec.status != "completed":
        raise HTTPException(status_code=400, detail="请先完成本地保存")
    video_key = (payload.video_key or "").strip()
    if not video_key or not qiniu_upload.practice_key_belongs_to_user(video_key, user.username, practice_id):
        raise HTTPException(status_code=400, detail="无效的视频 key")
    thumb_key = (payload.thumb_key or "").strip()
    if thumb_key and not qiniu_upload.practice_key_belongs_to_user(thumb_key, user.username, practice_id):
        raise HTTPException(status_code=400, detail="无效的封面 key")
    rec.video_key = video_key
    rec.thumb_key = thumb_key
    rec.video_url = qiniu_upload.cdn_url(video_key)
    rec.thumb_url = qiniu_upload.cdn_url(thumb_key) if thumb_key else ""
    rec.is_public = bool(payload.is_public)
    db.commit()
    db.refresh(rec)
    invalidate_on_publish(user.username, rec.id)
    return serialize_recording(rec)


@router.patch("/{practice_id}/visibility")
def set_visibility(
    practice_id: int,
    payload: VisibilityIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if is_guest(user.username):
        raise HTTPException(status_code=403, detail="游客不能公开朗读")
    assert_user_not_muted(user)
    rec = _own_recording(db, practice_id, user)
    if rec.status != "completed":
        raise HTTPException(status_code=400, detail="朗读还没保存完成")
    rec.is_public = bool(payload.is_public)
    db.commit()
    db.refresh(rec)
    invalidate_on_publish(user.username, rec.id)
    return serialize_recording(rec)


@router.post("/{practice_id}/complete")
def complete(
    practice_id: int,
    payload: CompleteIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if is_guest(user.username):
        raise HTTPException(status_code=403, detail="游客不能上传朗读")
    assert_user_not_muted(user)
    rec = _own_recording(db, practice_id, user)
    if rec.status == "completed":
        raise HTTPException(status_code=400, detail="练习已完成，请勿重复提交")
    video_key = (payload.video_key or "").strip()
    if not video_key or not qiniu_upload.practice_key_belongs_to_user(video_key, user.username, practice_id):
        raise HTTPException(status_code=400, detail="无效的视频 key")
    thumb_key = (payload.thumb_key or "").strip()
    if thumb_key and not qiniu_upload.practice_key_belongs_to_user(thumb_key, user.username, practice_id):
        raise HTTPException(status_code=400, detail="无效的封面 key")
    rec.video_key = video_key
    rec.thumb_key = thumb_key
    rec.video_url = qiniu_upload.cdn_url(video_key)
    rec.thumb_url = qiniu_upload.cdn_url(thumb_key) if thumb_key else ""
    rec.duration_sec = max(0, int(payload.duration_sec or 0))
    if payload.overall_score is not None:
        rec.overall_score = max(0, min(100, int(payload.overall_score)))
    rec.is_public = bool(payload.is_public)
    rec.status = "completed"
    rec.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(rec)
    _mark_progress(db, rec)
    invalidate_on_publish(user.username, rec.id)
    return serialize_recording(rec)
