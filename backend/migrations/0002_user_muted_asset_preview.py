"""为已有库补列：users.is_muted、generated_assets.preview。

用法（在 backend 目录）:
  python -m migrations.0002_user_muted_asset_preview
"""

from sqlalchemy import text

from migrations._util import get_engine, table_columns


def upgrade() -> None:
    engine = get_engine()
    with engine.begin() as conn:
        user_cols = table_columns(conn, "users")
        if user_cols and "is_muted" not in user_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN is_muted BOOLEAN DEFAULT 0"))
            print("OK: users.is_muted")
        else:
            print("SKIP: users.is_muted")

        asset_cols = table_columns(conn, "generated_assets")
        if asset_cols and "preview" not in asset_cols:
            conn.execute(text("ALTER TABLE generated_assets ADD COLUMN preview VARCHAR(200) DEFAULT ''"))
            print("OK: generated_assets.preview")
        else:
            print("SKIP: generated_assets.preview")


if __name__ == "__main__":
    upgrade()
