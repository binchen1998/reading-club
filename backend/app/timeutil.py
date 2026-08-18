"""统一使用上海时区，避免依赖客户端本地时钟。"""

from datetime import date, datetime, timedelta, timezone

SHANGHAI = timezone(timedelta(hours=8))


def server_now() -> datetime:
    return datetime.now(SHANGHAI)


def shanghai_today() -> date:
    return server_now().date()


def server_now_iso() -> str:
    return server_now().isoformat(timespec="seconds")
