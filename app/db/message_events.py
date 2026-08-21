from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import MessageEvent


async def insert_message_event(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    direction: str,
    telegram_user_id: int | None = None,
    group_chat_id: int | None = None,
    private_chat_id: int | None = None,
    message_thread_id: int | None = None,
    source_message_id: int | None = None,
    target_message_id: int | None = None,
    media_group_id: str | None = None,
    has_media: bool = False,
    payload_json: dict[str, Any] | None = None,
    status: str = "forwarded",
    error_code: str | None = None,
    error_text: str | None = None,
    created_at: datetime | None = None,
) -> MessageEvent:
    event = MessageEvent(
        direction=direction,
        telegram_user_id=telegram_user_id,
        group_chat_id=group_chat_id,
        private_chat_id=private_chat_id,
        message_thread_id=message_thread_id,
        source_message_id=source_message_id,
        target_message_id=target_message_id,
        media_group_id=media_group_id,
        has_media=has_media,
        payload_json=payload_json,
        status=status,
        error_code=error_code,
        error_text=error_text,
        created_at=created_at,
    )

    async with session_factory() as session:
        async with session.begin():
            session.add(event)

    return event