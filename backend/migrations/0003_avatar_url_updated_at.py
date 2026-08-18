"""补列：users.avatar_url、users.updated_at。

用法（在 backend 目录）:
  python -m migrations.0003_avatar_url_updated_at
"""

from sqlalchemy import text

from migrations._util import get_engine, table_columns


def upgrade() -> None:
    engine = get_engine()
    with engine.begin() as conn:
        cols = table_columns(conn, "users")
        if not cols:
            print("SKIP: users 不存在，请先跑 0001_init")
            return
        if "avatar_url" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN avatar_url VARCHAR(600) DEFAULT ''"))
            print("OK: users.avatar_url")
        else:
            print("SKIP: users.avatar_url")
        if "updated_at" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN updated_at DATETIME"))
            print("OK: users.updated_at")
        else:
            print("SKIP: users.updated_at")


if __name__ == "__main__":
    upgrade()
