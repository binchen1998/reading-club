from sqlalchemy import select
from sqlalchemy.orm import Session

from .cache_keys import (
    FOLLOWERS_INDEX,
    FOLLOWING_INDEX,
    NOTIF_LIST_INDEX,
    PROFILE_INDEX,
    PROFILE_WALL_ALL_INDEX,
    PROFILE_WALL_INDEX,
    REPORT_INDEX,
    SQUARE_COMMENTS_ALL_INDEX,
    SQUARE_COMMENTS_INDEX,
    SQUARE_DETAIL,
    SQUARE_DETAIL_INDEX,
    USER_ME,
    WRONG_INDEX,
)
from .models import Follow, Recording
from .page_cache import cache_delete, cache_delete_indexed


def invalidate_reports(username: str) -> None:
    cache_delete_indexed(REPORT_INDEX.format(username=username))
    cache_delete(USER_ME.format(username=username))


def invalidate_wrong(username: str) -> None:
    cache_delete_indexed(WRONG_INDEX.format(username=username))


def invalidate_profile(username: str) -> None:
    cache_delete_indexed(PROFILE_INDEX.format(username=username))
    cache_delete(USER_ME.format(username=username))


def invalidate_square_detail(recording_id: int) -> None:
    cache_delete(SQUARE_DETAIL.format(recording_id=recording_id))
    cache_delete_indexed(SQUARE_DETAIL_INDEX)


def invalidate_square_comments(recording_id: int) -> None:
    cache_delete_indexed(
        SQUARE_COMMENTS_INDEX.format(recording_id=recording_id),
        SQUARE_COMMENTS_ALL_INDEX,
    )


def invalidate_profile_wall(username: str) -> None:
    cache_delete_indexed(
        PROFILE_WALL_INDEX.format(username=username),
        PROFILE_WALL_ALL_INDEX,
    )


def invalidate_followers(username: str) -> None:
    cache_delete_indexed(FOLLOWERS_INDEX.format(username=username))


def invalidate_following(username: str) -> None:
    cache_delete_indexed(FOLLOWING_INDEX.format(username=username))


def invalidate_follow_graph(follower: str, following: str) -> None:
    invalidate_following(follower)
    invalidate_followers(following)
    invalidate_profile(follower)
    invalidate_profile(following)


def invalidate_notif_list(username: str) -> None:
    cache_delete_indexed(NOTIF_LIST_INDEX.format(username=username))


def invalidate_on_publish(username: str, recording_id: int) -> None:
    """上传完成：刷新个人缓存与详情；广场列表只靠 worker 覆盖，禁止 invalidate 快照。"""
    invalidate_reports(username)
    invalidate_profile(username)
    invalidate_square_detail(recording_id)


def invalidate_user_display(db: Session, username: str) -> None:
    """昵称/头像变更：个人页、关注图、其作品详情与相关评论/留言缓存。"""
    invalidate_profile(username)
    invalidate_following(username)
    invalidate_followers(username)
    invalidate_profile_wall(username)

    follower_rows = db.execute(select(Follow.follower).where(Follow.following == username)).scalars().all()
    for follower in follower_rows:
        invalidate_following(follower)

    following_rows = db.execute(select(Follow.following).where(Follow.follower == username)).scalars().all()
    for following in following_rows:
        invalidate_followers(following)

    recording_ids = (
        db.execute(
            select(Recording.id).where(
                Recording.username == username,
                Recording.status == "completed",
                Recording.is_public.is_(True),
            )
        )
        .scalars()
        .all()
    )
    for recording_id in recording_ids:
        invalidate_square_detail(int(recording_id))
        invalidate_square_comments(int(recording_id))

    cache_delete_indexed(SQUARE_COMMENTS_ALL_INDEX)
    cache_delete_indexed(PROFILE_WALL_ALL_INDEX)
