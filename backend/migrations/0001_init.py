"""初始建表。不会创建 MySQL 数据库本身，请先手工建好库。

用法（在 backend 目录）:
  python -m migrations.0001_init
"""

from migrations._util import get_engine
from app.db import Base
import app.models  # noqa: F401


def upgrade() -> None:
    engine = get_engine()
    Base.metadata.create_all(engine)
    print("OK: 已创建全部表（已存在的表不会改）")


if __name__ == "__main__":
    upgrade()
