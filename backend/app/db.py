from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import STORAGE

STORAGE.mkdir(parents=True, exist_ok=True)
DB_PATH = STORAGE / "club.sqlite"

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from sqlalchemy import text

    from . import models  # noqa: F401

    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        cols = [row[1] for row in conn.execute(text("PRAGMA table_info(users)"))]
        if cols and "is_muted" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN is_muted BOOLEAN DEFAULT 0"))
        asset_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(generated_assets)"))]
        if asset_cols and "preview" not in asset_cols:
            conn.execute(text("ALTER TABLE generated_assets ADD COLUMN preview VARCHAR(200) DEFAULT ''"))
        conn.commit()
