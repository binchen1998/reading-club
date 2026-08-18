"""迁移脚本公共工具（同步 SQLAlchemy 连接）。不会在启动时执行。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, inspect  # noqa: E402

from app.config import DB_TYPE, sync_db_url  # noqa: E402


def get_engine():
    url = sync_db_url()
    connect_args = {"check_same_thread": False} if DB_TYPE == "sqlite" else {}
    return create_engine(url, connect_args=connect_args, pool_pre_ping=True, future=True)


def table_columns(conn, table: str) -> set[str]:
    if not inspect(conn).has_table(table):
        return set()
    return {col["name"] for col in inspect(conn).get_columns(table)}
