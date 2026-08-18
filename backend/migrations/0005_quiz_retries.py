"""补列：page_progress.vocab_retries、page_progress.phrase_retries。

用法（在 backend 目录）:
  python -m migrations.0005_quiz_retries
"""

from sqlalchemy import text

from migrations._util import get_engine, table_columns


def upgrade() -> None:
    engine = get_engine()
    with engine.begin() as conn:
        cols = table_columns(conn, "page_progress")
        if not cols:
            print("SKIP: page_progress 不存在，请先跑 0001_init")
            return
        if "vocab_retries" not in cols:
            conn.execute(text("ALTER TABLE page_progress ADD COLUMN vocab_retries INTEGER DEFAULT 0"))
            print("OK: page_progress.vocab_retries")
        else:
            print("SKIP: page_progress.vocab_retries")
        if "phrase_retries" not in cols:
            conn.execute(text("ALTER TABLE page_progress ADD COLUMN phrase_retries INTEGER DEFAULT 0"))
            print("OK: page_progress.phrase_retries")
        else:
            print("SKIP: page_progress.phrase_retries")


if __name__ == "__main__":
    upgrade()
