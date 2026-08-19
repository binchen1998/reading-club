from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..cache_invalidate import invalidate_reports
from ..db import get_db
from ..models import BookCursor, PageProgress, User
from ..timeutil import shanghai_today

router = APIRouter(prefix="/api/progress", tags=["progress"])


class CursorIn(BaseModel):
    series_id: str
    book_slug: str
    chapter_id: str
    page: int


class ProgressIn(BaseModel):
    series_id: str
    book_slug: str
    book_title: str = ""
    chapter_id: str
    page: int
    vocab_done: bool | None = None
    phrase_done: bool | None = None
    vocab_retries: int | None = None
    phrase_retries: int | None = None
    record_done: bool | None = None
    record_score: int | None = None
    recording_id: int | None = None


def serialize_progress(row: PageProgress) -> dict:
    return {
        "id": row.id,
        "seriesId": row.series_id,
        "bookSlug": row.book_slug,
        "bookTitle": row.book_title,
        "chapterId": row.chapter_id,
        "page": row.page,
        "lessonDate": row.lesson_date.isoformat() if row.lesson_date else None,
        "vocabDone": row.vocab_done,
        "phraseDone": row.phrase_done,
        "vocabRetries": row.vocab_retries,
        "phraseRetries": row.phrase_retries,
        "recordDone": row.record_done,
        "recordScore": row.record_score,
        "recordingId": row.recording_id,
    }


def upsert_progress(db: Session, username: str, payload: ProgressIn) -> PageProgress:
    row = db.execute(
        select(PageProgress).where(
            PageProgress.username == username,
            PageProgress.series_id == payload.series_id,
            PageProgress.book_slug == payload.book_slug,
            PageProgress.chapter_id == payload.chapter_id,
            PageProgress.page == payload.page,
        )
    ).scalar_one_or_none()
    if row is None:
        row = PageProgress(
            username=username,
            series_id=payload.series_id,
            book_slug=payload.book_slug,
            book_title=payload.book_title[:200],
            chapter_id=payload.chapter_id,
            page=payload.page,
            lesson_date=shanghai_today(),
        )
        db.add(row)
    if payload.book_title:
        row.book_title = payload.book_title[:200]
    if payload.vocab_done is not None:
        row.vocab_done = payload.vocab_done
    if payload.phrase_done is not None:
        row.phrase_done = payload.phrase_done
    if payload.vocab_retries is not None:
        row.vocab_retries = max(0, int(payload.vocab_retries))
    if payload.phrase_retries is not None:
        row.phrase_retries = max(0, int(payload.phrase_retries))
    if payload.record_done is not None:
        row.record_done = payload.record_done
        if payload.record_done:
            row.lesson_date = shanghai_today()
    if payload.record_score is not None:
        row.record_score = max(0, min(100, int(payload.record_score)))
    if payload.recording_id is not None:
        row.recording_id = int(payload.recording_id)
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    invalidate_reports(username)
    return row


@router.post("")
def save_progress(payload: ProgressIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return serialize_progress(upsert_progress(db, user.username, payload))


@router.get("/page")
def page_progress(
    series_id: str,
    book_slug: str,
    chapter_id: str,
    page: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.execute(
        select(PageProgress).where(
            PageProgress.username == user.username,
            PageProgress.series_id == series_id,
            PageProgress.book_slug == book_slug,
            PageProgress.chapter_id == chapter_id,
            PageProgress.page == page,
        )
    ).scalar_one_or_none()
    return serialize_progress(row) if row else None


def serialize_cursor(row: BookCursor, last_page: int = 0) -> dict:
    page = int(row.page or 0)
    return {
        "seriesId": row.series_id,
        "bookSlug": row.book_slug,
        "chapterId": row.chapter_id,
        "page": page,
        "finished": bool(last_page and page >= last_page),
    }


def upsert_book_cursor(db: Session, username: str, payload: CursorIn) -> BookCursor:
    page = max(0, int(payload.page or 0))
    chapter_id = (payload.chapter_id or "").strip()
    row = db.execute(
        select(BookCursor).where(
            BookCursor.username == username,
            BookCursor.series_id == payload.series_id,
            BookCursor.book_slug == payload.book_slug,
        )
    ).scalar_one_or_none()
    if row is None:
        row = BookCursor(
            username=username,
            series_id=payload.series_id,
            book_slug=payload.book_slug,
            chapter_id=chapter_id,
            page=page,
        )
        db.add(row)
    else:
        row.chapter_id = chapter_id
        row.page = page
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return row


def book_cursors_for_series(db: Session, username: str, series_id: str) -> dict[str, BookCursor]:
    rows = db.execute(
        select(BookCursor).where(BookCursor.username == username, BookCursor.series_id == series_id)
    ).scalars().all()
    return {row.book_slug: row for row in rows}


@router.post("/cursor")
def save_cursor(payload: CursorIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not payload.series_id or not payload.book_slug or not payload.chapter_id or payload.page <= 0:
        return {"page": 0, "chapterId": "", "finished": False}
    row = upsert_book_cursor(db, user.username, payload)
    return serialize_cursor(row)
