from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class MessageEvent(Base):
    __tablename__ = "message_events"
    __table_args__ = (
        Index("ix_message_events_telegram_user_created_at", "telegram_user_id", "created_at"),
        Index("ix_message_events_message_thread_created_at", "message_thread_id", "created_at"),
        Index("ix_message_events_direction_created_at", "direction", "created_at"),
        Index("ix_message_events_payload_json", "payload_json", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        server_default=text("nextval('message_events_id_seq')"),
    )
    direction: Mapped[str] = mapped_column(Text)
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger)
    group_chat_id: Mapped[int | None] = mapped_column(BigInteger)
    private_chat_id: Mapped[int | None] = mapped_column(BigInteger)
    message_thread_id: Mapped[int | None] = mapped_column(BigInteger)
    source_message_id: Mapped[int | None] = mapped_column(BigInteger)
    target_message_id: Mapped[int | None] = mapped_column(BigInteger)
    media_group_id: Mapped[str | None] = mapped_column(Text)
    has_media: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    payload_json: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text, default="forwarded", server_default="forwarded")
    error_code: Mapped[str | None] = mapped_column(Text)
    error_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, server_default=func.now()
    )


class SyncOutbox(Base):
    __tablename__ = "sync_outbox"
    __table_args__ = (
        UniqueConstraint(
            "event_type",
            "event_key",
            name="uq_sync_outbox_event_type_event_key",
        ),
        Index("ix_sync_outbox_status_next_attempt_at", "status", "next_attempt_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(Text)
    event_key: Mapped[str] = mapped_column(Text)
    payload_json: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text, default="pending", server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class User(Base):
    __tablename__ = "users"

    telegram_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(Text)
    full_name: Mapped[str] = mapped_column(Text)
    language_code: Mapped[str | None] = mapped_column(Text)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class UserTopic(Base):
    __tablename__ = "user_topics"

    telegram_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    message_thread_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    message_silent_mode: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    message_silent_id: Mapped[int | None] = mapped_column(BigInteger)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
