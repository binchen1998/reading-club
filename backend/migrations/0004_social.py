"""社交表：关注、作品评论、留言板、通知。

用法（在 backend 目录）:
  python -m migrations.0004_social
"""

from migrations._util import get_engine
from app.db import Base
import app.models  # noqa: F401


def upgrade() -> None:
    engine = get_engine()
    Base.metadata.create_all(engine)
    print("OK: 已补齐 follows / recording_comments / user_messages / notifications")


if __name__ == "__main__":
    upgrade()
