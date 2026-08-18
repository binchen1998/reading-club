from calendar import monthrange
from datetime import date as Date
from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..cache_keys import REPORT_DAY, REPORT_HOME, REPORT_INDEX, REPORT_MONTH
from ..db import get_db
from ..models import PageProgress, Recording, User
from ..page_cache import cache_get, cache_set
from ..timeutil import server_now_iso, shanghai_today

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _week_range(today: Date) -> tuple[Date, Date]:
    start = today - timedelta(days=today.weekday())
    return start, today


def _compute_streak(active_dates: set[Date], today: Date) -> int:
    streak = 0
    cursor = today
    while cursor in active_dates:
        streak += 1
        cursor -= timedelta(days=1)
        if streak > 366:
            break
    return streak


@router.get("/home-stats")
def home_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = shanghai_today()
    cache_key = REPORT_HOME.format(username=user.username, date=today.isoformat())
    cached = cache_get(cache_key)
    if isinstance(cached, dict):
        return cached

    yesterday = today - timedelta(days=1)
    week_start, week_end = _week_range(today)
    month_start = today.replace(day=1)

    def pack(start: Date | None, end: Date | None):
        filters = [PageProgress.username == user.username]
        if start and end:
            filters.append(PageProgress.lesson_date >= start)
            filters.append(PageProgress.lesson_date <= end)
        row = db.execute(
            select(
                func.count(PageProgress.id),
                func.coalesce(func.sum(case((PageProgress.vocab_done.is_(True), 1), else_=0)), 0),
                func.coalesce(func.sum(case((PageProgress.phrase_done.is_(True), 1), else_=0)), 0),
                func.coalesce(func.sum(case((PageProgress.record_done.is_(True), 1), else_=0)), 0),
            ).where(*filters)
        ).one()
        rec_filters = [Recording.username == user.username, Recording.status == "completed"]
        if start and end:
            rec_filters.append(Recording.lesson_date >= start)
            rec_filters.append(Recording.lesson_date <= end)
        duration = db.execute(select(func.coalesce(func.sum(Recording.duration_sec), 0)).where(*rec_filters)).scalar() or 0
        return {
            "count": int(row[0] or 0),
            "vocab": int(row[1] or 0),
            "phrase": int(row[2] or 0),
            "record": int(row[3] or 0),
            "minutes": int(duration) // 60,
            "durationSec": int(duration),
        }

    yesterday_s = pack(yesterday, yesterday)
    week_s = pack(week_start, week_end)
    month_s = pack(month_start, today)
    total_s = pack(None, None)
    payload = {
        "timezone": "Asia/Shanghai",
        "server_now": server_now_iso(),
        "today": today.isoformat(),
        "yesterday_count": yesterday_s["count"],
        "yesterday_minutes": yesterday_s["minutes"],
        "week_count": week_s["count"],
        "week_minutes": week_s["minutes"],
        "month_count": month_s["count"],
        "month_minutes": month_s["minutes"],
        "total_count": total_s["count"],
        "total_minutes": total_s["minutes"],
        "yesterday": {"date": yesterday.isoformat(), **yesterday_s},
        "thisWeek": {"start": week_start.isoformat(), "end": week_end.isoformat(), **week_s},
        "thisMonth": {"start": month_start.isoformat(), "end": today.isoformat(), **month_s},
        "total": total_s,
    }
    cache_set(cache_key, payload, indexes=[REPORT_INDEX.format(username=user.username)])
    return payload


@router.get("/month")
def month_report(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = shanghai_today()
    cache_key = REPORT_MONTH.format(
        username=user.username, year=year, month=month, as_of=today.isoformat()
    )
    cached = cache_get(cache_key)
    if isinstance(cached, dict):
        return cached

    days_in_month = monthrange(year, month)[1]
    first = Date(year, month, 1)
    last = Date(year, month, days_in_month)
    rows = db.execute(
        select(
            PageProgress.lesson_date,
            func.count(PageProgress.id),
            func.coalesce(func.sum(case((PageProgress.record_done.is_(True), 1), else_=0)), 0),
        )
        .where(
            PageProgress.username == user.username,
            PageProgress.lesson_date >= first,
            PageProgress.lesson_date <= last,
        )
        .group_by(PageProgress.lesson_date)
    ).all()
    by_day = {row[0]: {"count": int(row[1]), "record": int(row[2])} for row in rows}
    weekday = first.weekday()
    days = []
    for day in range(1, days_in_month + 1):
        cur = Date(year, month, day)
        info = by_day.get(cur) or {"count": 0, "record": 0}
        days.append(
            {
                "date": cur.isoformat(),
                "day": day,
                "active": info["count"] > 0,
                "count": info["count"],
                "record": info["record"],
                "is_today": cur == today,
                "is_future": cur > today,
            }
        )
    active_dates = {row[0] for row in rows if row[1]}
    payload = {
        "year": year,
        "month": month,
        "month_days": days_in_month,
        "first_weekday": weekday,
        "active_count": len(active_dates),
        "streak": _compute_streak(active_dates, today) if year == today.year and month == today.month else 0,
        "days": days,
        "server_now": server_now_iso(),
        "today": today.isoformat(),
        "timezone": "Asia/Shanghai",
    }
    cache_set(cache_key, payload, indexes=[REPORT_INDEX.format(username=user.username)])
    return payload


@router.get("/day")
def day_report(date: str = Query(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    day = Date.fromisoformat(date)
    cache_key = REPORT_DAY.format(username=user.username, day=day.isoformat())
    cached = cache_get(cache_key)
    if isinstance(cached, dict):
        return cached
    rows = (
        db.execute(
            select(PageProgress)
            .where(PageProgress.username == user.username, PageProgress.lesson_date == day)
            .order_by(PageProgress.page)
        )
        .scalars()
        .all()
    )
    recs = {
        row.id: row
        for row in db.execute(
            select(Recording).where(
                Recording.username == user.username,
                Recording.lesson_date == day,
                Recording.status == "completed",
            )
        ).scalars().all()
    }
    items = []
    for row in rows:
        rec = recs.get(row.recording_id)
        items.append(
            {
                "seriesId": row.series_id,
                "bookSlug": row.book_slug,
                "bookTitle": row.book_title,
                "chapterId": row.chapter_id,
                "page": row.page,
                "vocabDone": row.vocab_done,
                "phraseDone": row.phrase_done,
                "vocabRetries": row.vocab_retries,
                "phraseRetries": row.phrase_retries,
                "recordDone": row.record_done,
                "recordScore": row.record_score,
                "recordingId": row.recording_id,
                "videoUrl": rec.video_url if rec else "",
            }
        )
    payload = {"date": day.isoformat(), "items": items, "server_now": server_now_iso()}
    cache_set(cache_key, payload, indexes=[REPORT_INDEX.format(username=user.username)])
    return payload
