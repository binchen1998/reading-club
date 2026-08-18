"""排行榜计算与 Redis 缓存（无 TTL，仅由 background worker 定时覆盖）。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from .avatar import display_avatar
from .cache_keys import LEADERBOARD_HONOR, LEADERBOARD_RISE, LEADERBOARD_TALENT, LEADERBOARD_UPDATED
from .config import LEADERBOARD_MIN_HONOR_POINTS, LEADERBOARD_MIN_WORK_COUNT
from .db import SessionLocal
from .display_name import leaderboard_display_name
from .models import PageProgress, Recording, User
from .page_cache import cache_get, cache_set
from .redis_client import get_redis

logger = logging.getLogger("leaderboard_worker")

TZ_CN = timezone(timedelta(hours=8))
CACHE_LIMIT = 200


def my_rank_from_entries(entries: list[dict[str, Any]], username: str) -> int | None:
    for item in entries:
        if item.get("username") == username and item.get("rank") is not None:
            return int(item["rank"])
    return None


def week_range_cn() -> tuple[datetime, datetime, str]:
    now_cn = datetime.now(TZ_CN)
    monday_cn = now_cn.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=now_cn.weekday())
    sunday_cn = monday_cn + timedelta(days=6)
    week_start = monday_cn.date()
    label = f"{monday_cn.month}/{monday_cn.day} - {sunday_cn.month}/{sunday_cn.day}"
    return week_start, sunday_cn.date(), label


def _user_map(db: Session, usernames: list[str]) -> dict[str, User]:
    names = [name for name in usernames if name]
    if not names:
        return {}
    return {
        user.username: user
        for user in db.execute(select(User).where(User.username.in_(names))).scalars().all()
    }


def _compute_rise_payload(db: Session) -> dict[str, Any]:
    week_start, _, week_label = week_range_cn()
    rows = list(
        db.execute(
            select(
                PageProgress.username,
                func.sum(case((PageProgress.record_done.is_(True), 1), else_=0)).label("weekly_rise"),
                func.count(PageProgress.id).label("match_count"),
            )
            .where(PageProgress.lesson_date >= week_start)
            .group_by(PageProgress.username)
            .having(func.sum(case((PageProgress.record_done.is_(True), 1), else_=0)) > 0)
            .order_by(func.sum(case((PageProgress.record_done.is_(True), 1), else_=0)).desc())
            .limit(CACHE_LIMIT)
        ).all()
    )
    users = _user_map(db, [row.username for row in rows])
    entries = []
    for index, row in enumerate(rows):
        user = users.get(row.username)
        entries.append(
            {
                "rank": index + 1,
                "username": row.username,
                "name": leaderboard_display_name(user, row.username),
                "avatar": display_avatar(user),
                "weeklyRise": int(row.weekly_rise or 0),
                "matchCount": int(row.match_count or 0),
            }
        )
    return {"weekLabel": week_label, "entries": entries}


def _compute_talent_entries(db: Session) -> list[dict[str, Any]]:
    rows = list(
        db.execute(
            select(
                Recording.username,
                func.count(Recording.id).label("work_count"),
                func.avg(Recording.overall_score).label("avg_score"),
                func.max(Recording.overall_score).label("best_score"),
            )
            .where(Recording.status == "completed", Recording.is_public.is_(True))
            .group_by(Recording.username)
            .having(func.count(Recording.id) >= LEADERBOARD_MIN_WORK_COUNT)
            .order_by(func.count(Recording.id).desc(), func.avg(Recording.overall_score).desc())
            .limit(CACHE_LIMIT)
        ).all()
    )
    users = _user_map(db, [row.username for row in rows])
    entries = []
    for index, row in enumerate(rows):
        user = users.get(row.username)
        work_count = int(row.work_count or 0)
        avg_score = int(round(float(row.avg_score or 0)))
        entries.append(
            {
                "rank": index + 1,
                "username": row.username,
                "name": leaderboard_display_name(user, row.username),
                "avatar": display_avatar(user),
                "rating": work_count * 100 + avg_score,
                "workCount": work_count,
                "avgScore": avg_score,
                "bestScore": int(row.best_score or 0),
            }
        )
    entries.sort(key=lambda item: (item["rating"], item["workCount"]), reverse=True)
    for index, item in enumerate(entries):
        item["rank"] = index + 1
    return entries


def _compute_honor_entries(db: Session) -> list[dict[str, Any]]:
    rows = list(
        db.execute(
            select(
                Recording.username,
                func.coalesce(func.sum(Recording.like_count), 0).label("honor_points"),
            )
            .where(Recording.status == "completed", Recording.is_public.is_(True))
            .group_by(Recording.username)
            .having(func.coalesce(func.sum(Recording.like_count), 0) >= LEADERBOARD_MIN_HONOR_POINTS)
            .order_by(func.coalesce(func.sum(Recording.like_count), 0).desc())
            .limit(CACHE_LIMIT)
        ).all()
    )
    users = _user_map(db, [row.username for row in rows])
    return [
        {
            "rank": index + 1,
            "username": row.username,
            "name": leaderboard_display_name(users.get(row.username), row.username),
            "avatar": display_avatar(users.get(row.username)),
            "honorPoints": int(row.honor_points or 0),
        }
        for index, row in enumerate(rows)
    ]


def refresh_leaderboard_cache() -> bool:
    if get_redis() is None:
        logger.warning("Redis 未启用，跳过排行榜缓存刷新")
        return False
    db = SessionLocal()
    try:
        rise = _compute_rise_payload(db)
        talent = _compute_talent_entries(db)
        honor = _compute_honor_entries(db)
        cache_set(LEADERBOARD_RISE, rise)
        cache_set(LEADERBOARD_TALENT, talent)
        cache_set(LEADERBOARD_HONOR, honor)
        cache_set(LEADERBOARD_UPDATED, datetime.now(timezone.utc).isoformat())
        logger.info(
            "排行榜缓存已刷新 rise=%s talent=%s honor=%s",
            len(rise.get("entries") or []),
            len(talent),
            len(honor),
        )
        return True
    finally:
        db.close()


def get_cached_rise() -> tuple[dict[str, Any], str | None] | None:
    payload = cache_get(LEADERBOARD_RISE)
    if not isinstance(payload, dict):
        return None
    return payload, cache_get(LEADERBOARD_UPDATED)


def get_cached_talent() -> tuple[list[dict[str, Any]], str | None] | None:
    payload = cache_get(LEADERBOARD_TALENT)
    if not isinstance(payload, list):
        return None
    return payload, cache_get(LEADERBOARD_UPDATED)


def get_cached_honor() -> tuple[list[dict[str, Any]], str | None] | None:
    payload = cache_get(LEADERBOARD_HONOR)
    if not isinstance(payload, list):
        return None
    return payload, cache_get(LEADERBOARD_UPDATED)
