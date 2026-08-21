from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import SyncOutbox


async def enqueue_sync_event(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    event_type: str,
    event_key: str,
    payload_json: dict[str, Any],
) -> bool:
    statement = (
        insert(SyncOutbox)
        .values(
            event_type=event_type,
            event_key=event_key,
            payload_json=payload_json,
        )
        .on_conflict_do_nothing(
            constraint="uq_sync_outbox_event_type_event_key"
        )
    )

    async with session_factory() as session:
        async with session.begin():
            result = await session.execute(statement)

    return result.rowcount == 1