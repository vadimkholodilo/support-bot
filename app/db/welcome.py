from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import WelcomeMessage

# The welcome_message table holds at most one row, pinned to this id.
WELCOME_ROW_ID = 1


@dataclass(frozen=True)
class StoredWelcome:
    """A welcome message stored by reference to its original Telegram message."""

    source_chat_id: int
    source_message_id: int
    content_type: str | None = None
    updated_by: int | None = None

    def to_dict(self) -> dict:
        return {
            "source_chat_id": self.source_chat_id,
            "source_message_id": self.source_message_id,
            "content_type": self.content_type,
            "updated_by": self.updated_by,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StoredWelcome":
        return cls(
            source_chat_id=data["source_chat_id"],
            source_message_id=data["source_message_id"],
            content_type=data.get("content_type"),
            updated_by=data.get("updated_by"),
        )


async def get_welcome_message(
        session_factory: async_sessionmaker[AsyncSession],
) -> StoredWelcome | None:
    """Return the stored welcome message, or ``None`` if none is configured."""
    async with session_factory() as session:
        row = await session.scalar(
            select(WelcomeMessage).where(WelcomeMessage.id == WELCOME_ROW_ID)
        )
        if row is None:
            return None
        return StoredWelcome(
            source_chat_id=row.source_chat_id,
            source_message_id=row.source_message_id,
            content_type=row.content_type,
            updated_by=row.updated_by,
        )


async def save_welcome_message(
        session_factory: async_sessionmaker[AsyncSession],
        *,
        source_chat_id: int,
        source_message_id: int,
        content_type: str | None,
        updated_by: int | None,
) -> None:
    """Insert or replace the single welcome message row."""
    stmt = insert(WelcomeMessage).values(
        id=WELCOME_ROW_ID,
        source_chat_id=source_chat_id,
        source_message_id=source_message_id,
        content_type=content_type,
        updated_by=updated_by,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[WelcomeMessage.id],
        set_={
            "source_chat_id": stmt.excluded.source_chat_id,
            "source_message_id": stmt.excluded.source_message_id,
            "content_type": stmt.excluded.content_type,
            "updated_by": stmt.excluded.updated_by,
            "updated_at": func.now(),
        },
    )

    async with session_factory() as session:
        async with session.begin():
            await session.execute(stmt)


async def delete_welcome_message(
        session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Remove the stored welcome message, reverting to the default text."""
    async with session_factory() as session:
        async with session.begin():
            await session.execute(
                delete(WelcomeMessage).where(WelcomeMessage.id == WELCOME_ROW_ID)
            )
