from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..cache_invalidate import invalidate_wrong
from ..cache_keys import WRONG_CURRENT, WRONG_HISTORY, WRONG_INDEX
from ..db import get_db
from ..models import User, WrongItem
from ..page_cache import cache_get, cache_set

router = APIRouter(prefix="/api/wrongbook", tags=["wrongbook"])


class WrongIn(BaseModel):
    kind: str = "vocab"
    en: str
    zh: str = ""
    series_id: str = ""
    book_slug: str = ""
    book_title: str = ""
    chapter_id: str = ""
    page: int = 0


class ResolveIn(BaseModel):
    id: int


def serialize_wrong(row: WrongItem) -> dict:
    return {
        "id": row.id,
        "kind": row.kind,
        "en": row.en,
        "zh": row.zh,
        "seriesId": row.series_id,
        "bookSlug": row.book_slug,
        "bookTitle": row.book_title,
        "chapterId": row.chapter_id,
        "page": row.page,
        "wrongCount": row.wrong_count,
        "firstWrongAt": row.first_wrong_at.isoformat() if row.first_wrong_at else None,
        "lastWrongAt": row.last_wrong_at.isoformat() if row.last_wrong_at else None,
        "resolvedAt": row.resolved_at.isoformat() if row.resolved_at else None,
        "open": row.resolved_at is None,
    }


@router.post("/add")
def add_wrong(payload: WrongIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    kind = "phrase" if payload.kind == "phrase" else "vocab"
    en = payload.en.strip()[:120]
    row = db.execute(
        select(WrongItem).where(
            WrongItem.username == user.username,
            WrongItem.kind == kind,
            WrongItem.en == en,
            WrongItem.series_id == payload.series_id,
            WrongItem.book_slug == payload.book_slug,
            WrongItem.chapter_id == payload.chapter_id,
            WrongItem.page == payload.page,
        )
    ).scalar_one_or_none()
    now = datetime.utcnow()
    if row is None:
        row = WrongItem(
            username=user.username,
            kind=kind,
            en=en,
            zh=payload.zh[:200],
            series_id=payload.series_id,
            book_slug=payload.book_slug,
            book_title=payload.book_title[:200],
            chapter_id=payload.chapter_id,
            page=payload.page,
            first_wrong_at=now,
            last_wrong_at=now,
        )
        db.add(row)
    else:
        row.wrong_count += 1
        row.last_wrong_at = now
        row.resolved_at = None
        if payload.zh:
            row.zh = payload.zh[:200]
    db.commit()
    db.refresh(row)
    invalidate_wrong(user.username)
    return serialize_wrong(row)


@router.post("/resolve")
def resolve_wrong(payload: ResolveIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.get(WrongItem, int(payload.id))
    if row is None or row.username != user.username:
        return {"ok": False}
    if row.resolved_at is None:
        row.resolved_at = datetime.utcnow()
        db.commit()
        invalidate_wrong(user.username)
    return {"ok": True}


@router.get("")
def list_wrong(
    scope: str = Query("current"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    want_open = scope != "history"
    key = (WRONG_CURRENT if want_open else WRONG_HISTORY).format(username=user.username)
    cached = cache_get(key)
    if isinstance(cached, dict):
        return cached
    rows = db.execute(
        select(WrongItem)
        .where(WrongItem.username == user.username)
        .order_by(WrongItem.last_wrong_at.desc())
    ).scalars().all()
    items = [serialize_wrong(row) for row in rows if (row.resolved_at is None) == want_open]
    payload = {"scope": "current" if want_open else "history", "items": items}
    cache_set(key, payload, indexes=[WRONG_INDEX.format(username=user.username)])
    return payload
