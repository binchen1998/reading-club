from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class User(Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(50), primary_key=True)
    nickname: Mapped[str] = mapped_column(String(50), default="")
    avatar: Mapped[str] = mapped_column(String(500), default="📖")
    avatar_url: Mapped[str] = mapped_column(String(600), default="")
    bio: Mapped[str] = mapped_column(String(200), default="")
    is_muted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PageProgress(Base):
    __tablename__ = "page_progress"
    __table_args__ = (
        UniqueConstraint(
            "username",
            "series_id",
            "book_slug",
            "chapter_id",
            "page",
            name="uq_page_progress",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), index=True)
    series_id: Mapped[str] = mapped_column(String(80), default="")
    book_slug: Mapped[str] = mapped_column(String(120), default="")
    book_title: Mapped[str] = mapped_column(String(200), default="")
    chapter_id: Mapped[str] = mapped_column(String(40), default="")
    page: Mapped[int] = mapped_column(Integer, default=0)
    lesson_date: Mapped[date] = mapped_column(Date, index=True)
    vocab_done: Mapped[bool] = mapped_column(Boolean, default=False)
    phrase_done: Mapped[bool] = mapped_column(Boolean, default=False)
    record_done: Mapped[bool] = mapped_column(Boolean, default=False)
    record_score: Mapped[int] = mapped_column(Integer, default=0)
    recording_id: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Recording(Base):
    __tablename__ = "recordings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    series_id: Mapped[str] = mapped_column(String(80), default="")
    book_slug: Mapped[str] = mapped_column(String(120), default="")
    book_title: Mapped[str] = mapped_column(String(200), default="")
    chapter_id: Mapped[str] = mapped_column(String(40), default="")
    page: Mapped[int] = mapped_column(Integer, default=0)
    lesson_date: Mapped[date] = mapped_column(Date, index=True)
    duration_sec: Mapped[int] = mapped_column(Integer, default=0)
    overall_score: Mapped[int] = mapped_column(Integer, default=0)
    video_key: Mapped[str] = mapped_column(String(400), default="")
    video_url: Mapped[str] = mapped_column(String(600), default="")
    thumb_key: Mapped[str] = mapped_column(String(400), default="")
    thumb_url: Mapped[str] = mapped_column(String(600), default="")
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class RecordingLike(Base):
    __tablename__ = "recording_likes"
    __table_args__ = (UniqueConstraint("username", "recording_id", name="uq_recording_like"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), index=True)
    recording_id: Mapped[int] = mapped_column(Integer, ForeignKey("recordings.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WrongItem(Base):
    __tablename__ = "wrong_items"
    __table_args__ = (
        UniqueConstraint(
            "username",
            "kind",
            "en",
            "series_id",
            "book_slug",
            "chapter_id",
            "page",
            name="uq_wrong_item",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="vocab")
    en: Mapped[str] = mapped_column(String(120), default="")
    zh: Mapped[str] = mapped_column(String(200), default="")
    series_id: Mapped[str] = mapped_column(String(80), default="")
    book_slug: Mapped[str] = mapped_column(String(120), default="")
    book_title: Mapped[str] = mapped_column(String(200), default="")
    chapter_id: Mapped[str] = mapped_column(String(40), default="")
    page: Mapped[int] = mapped_column(Integer, default=0)
    wrong_count: Mapped[int] = mapped_column(Integer, default=1)
    first_wrong_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_wrong_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")


class GeneratedAsset(Base):
    __tablename__ = "generated_assets"
    __table_args__ = (UniqueConstraint("kind", "asset_key", name="uq_generated_asset"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(20), default="tts")
    asset_key: Mapped[str] = mapped_column(String(400), default="")
    label: Mapped[str] = mapped_column(String(80), default="")
    preview: Mapped[str] = mapped_column(String(200), default="")
    source: Mapped[str] = mapped_column(String(20), default="generated")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Follow(Base):
    __tablename__ = "follows"
    __table_args__ = (UniqueConstraint("follower", "following", name="uq_follow"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    follower: Mapped[str] = mapped_column(String(50), index=True)
    following: Mapped[str] = mapped_column(String(50), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RecordingComment(Base):
    __tablename__ = "recording_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recording_id: Mapped[int] = mapped_column(Integer, ForeignKey("recordings.id"), index=True)
    username: Mapped[str] = mapped_column(String(50), index=True)
    content: Mapped[str] = mapped_column(Text, default="")
    parent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("recording_comments.id"), nullable=True, index=True
    )
    moderated: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UserMessage(Base):
    __tablename__ = "user_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wall_username: Mapped[str] = mapped_column(String(50), index=True)
    author_username: Mapped[str] = mapped_column(String(50), index=True)
    content: Mapped[str] = mapped_column(Text, default="")
    parent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("user_messages.id"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), index=True)
    type: Mapped[str] = mapped_column(String(40), index=True)
    actor_username: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ref_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str] = mapped_column(String(500), default="")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
