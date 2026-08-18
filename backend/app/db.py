from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DB_TYPE, sync_db_url

_connect_args = {"check_same_thread": False} if DB_TYPE == "sqlite" else {}
engine = create_engine(
    sync_db_url(),
    connect_args=_connect_args,
    pool_pre_ping=True,
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
