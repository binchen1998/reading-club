from .cache_keys import (
    PROFILE_INDEX,
    REPORT_INDEX,
    SQUARE_DETAIL,
    SQUARE_DETAIL_INDEX,
    USER_ME,
    WRONG_INDEX,
)
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


def invalidate_on_publish(username: str, recording_id: int) -> None:
    """上传完成：刷新个人缓存与详情；广场列表只靠 worker 覆盖，禁止 invalidate 快照。"""
    invalidate_reports(username)
    invalidate_profile(username)
    invalidate_square_detail(recording_id)
