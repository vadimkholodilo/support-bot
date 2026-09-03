from __future__ import annotations

import logging
from contextlib import suppress
from typing import TYPE_CHECKING

from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.markdown import hbold
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.utils.redis import RedisStorage
from app.db.welcome import (
    StoredWelcome,
    delete_welcome_message,
    get_welcome_message,
    save_welcome_message,
)

if TYPE_CHECKING:
    from app.bot.manager import Manager

logger = logging.getLogger(__name__)


class WelcomeService:
    """Resolves, persists, and renders the bot's welcome message.

    A developer can replace the default greeting with any Telegram message
    (text, photo, video, ...) via ``/welcome``. The message is stored by
    reference (source chat id + message id) and re-sent with ``copy_message``,
    the same way ``aiogram_newsletter`` handles newsletter content.

    PostgreSQL is the source of truth; Redis is a read-through cache. When no
    custom message is stored, or its source can no longer be copied, callers
    fall back to the localized ``main_menu`` text. Use :meth:`render` from
    handlers instead of touching the storage layers directly.
    """

    def __init__(
        self,
        redis: RedisStorage,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._redis = redis
        self._session_factory = session_factory

    async def get(self) -> StoredWelcome | None:
        """Return the stored welcome message, or ``None`` for the default."""
        cached = await self._redis.get_welcome_message()
        if cached is not None:
            return StoredWelcome.from_dict(cached)

        stored = await get_welcome_message(self._session_factory)
        if stored is not None:
            await self._redis.set_welcome_message(stored.to_dict())
        return stored

    async def set(
        self,
        *,
        source_chat_id: int,
        source_message_id: int,
        content_type: str | None,
        updated_by: int | None,
    ) -> None:
        """Store a new welcome message and refresh the cache."""
        await save_welcome_message(
            self._session_factory,
            source_chat_id=source_chat_id,
            source_message_id=source_message_id,
            content_type=content_type,
            updated_by=updated_by,
        )
        await self._redis.set_welcome_message(
            StoredWelcome(
                source_chat_id=source_chat_id,
                source_message_id=source_message_id,
                content_type=content_type,
                updated_by=updated_by,
            ).to_dict()
        )

    async def reset(self) -> None:
        """Drop any custom welcome message, reverting to the default text."""
        await delete_welcome_message(self._session_factory)
        await self._redis.delete_welcome_message()

    async def render(self, manager: "Manager") -> None:
        """Send the welcome message to the current user.

        Falls back to the localized default text when nothing is stored or the
        stored source message can no longer be copied.
        """
        stored = await self.get()
        if stored is None:
            await self._render_default(manager)
            return

        try:
            await manager.send_copied_message(
                from_chat_id=stored.source_chat_id,
                message_id=stored.source_message_id,
            )
        except TelegramBadRequest:
            logger.warning(
                "Stored welcome message could not be copied; using default text",
                extra={
                    "source_chat_id": stored.source_chat_id,
                    "source_message_id": stored.source_message_id,
                },
            )
            await self._render_default(manager)

    @staticmethod
    async def _render_default(manager: "Manager") -> None:
        text = manager.text_message.get("main_menu")
        with suppress(IndexError, KeyError):
            text = text.format(full_name=hbold(manager.user.full_name))
        await manager.send_message(text)
