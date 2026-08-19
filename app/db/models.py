from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Text, func
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

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
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
        DateTime(timezone=True), server_default=func.now()
    )
