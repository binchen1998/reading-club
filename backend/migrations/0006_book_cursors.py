"""书架进度：每位用户每本书上次读到的章节和页。

用法（在 backend 目录）:
  python -m migrations.0006_book_cursors
"""

from migrations._util import get_engine
from app.db import Base
import app.models  # noqa: F401


def upgrade() -> None:
    engine = get_engine()
    Base.metadata.create_all(engine)
    print("OK: 已补齐 book_cursors")


if __name__ == "__main__":
    upgrade()
