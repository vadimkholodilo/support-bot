from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import User, UserTopic

if TYPE_CHECKING:
    from app.bot.utils.redis.models import UserData


async def mirror_user_state(
    session_factory: async_sessionmaker[AsyncSession],
    user_data: UserData,
) -> None:
    user_values: dict[str, Any] = {
        "telegram_user_id": user_data.id,
        "username": user_data.username,
        "full_name": user_data.full_name,
        "language_code": user_data.language_code,
        "is_banned": user_data.is_banned,
    }
    user_insert = insert(User).values(**user_values)
    user_statement = user_insert.on_conflict_do_update(
        index_elements=[User.telegram_user_id],
        set_={
            "username": user_insert.excluded.username,
            "full_name": user_insert.excluded.full_name,
            "language_code": user_insert.excluded.language_code,
            "is_banned": user_insert.excluded.is_banned,
            "updated_at": user_insert.excluded.updated_at,
        },
    )
    topic_insert = insert(UserTopic).values(
        telegram_user_id=user_data.id,
        message_thread_id=user_data.message_thread_id,
        message_silent_mode=user_data.message_silent_mode,
        message_silent_id=user_data.message_silent_id,
    )
    topic_statement = topic_insert.on_conflict_do_update(
        index_elements=[UserTopic.telegram_user_id],
        set_={
            "message_thread_id": topic_insert.excluded.message_thread_id,
            "message_silent_mode": topic_insert.excluded.message_silent_mode,
            "message_silent_id": topic_insert.excluded.message_silent_id,
            "updated_at": topic_insert.excluded.updated_at,
        },
    )

    async with session_factory() as session:
        async with session.begin():
            await session.execute(user_statement)
            await session.execute(topic_statement)