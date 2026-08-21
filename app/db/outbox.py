import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import load_config
from app.db import create_async_engine, create_session_factory
from app.db.message_events import insert_message_event
from app.db.models import SyncOutbox

logger = logging.getLogger(__name__)

OUTBOX_BATCH_SIZE = 50
OUTBOX_MAX_ATTEMPTS = 5
OUTBOX_BASE_BACKOFF_SECONDS = 30


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


async def retry_pending_sync_events(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, int]:
    processed = 0
    completed = 0
    failed = 0

    for _ in range(OUTBOX_BATCH_SIZE):
        async with session_factory() as session:
            async with session.begin():
                result = await session.execute(
                    select(SyncOutbox)
                    .where(
                        SyncOutbox.event_type == "message_event",
                        SyncOutbox.status == "pending",
                        (SyncOutbox.next_attempt_at.is_(None))
                        | (SyncOutbox.next_attempt_at <= datetime.now(timezone.utc)),
                    )
                    .order_by(SyncOutbox.created_at)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
                outbox_event = result.scalar_one_or_none()
                if outbox_event is None:
                    break

                event_id = outbox_event.id
                event_payload = dict(outbox_event.payload_json)
                attempts = outbox_event.attempts + 1
                outbox_event.status = "processing"
                outbox_event.attempts = attempts
                outbox_event.updated_at = datetime.now(timezone.utc)

        processed += 1
        try:
            await insert_message_event(session_factory, **event_payload)
        except Exception as ex:
            exhausted = attempts >= OUTBOX_MAX_ATTEMPTS
            next_attempt_at = None
            if not exhausted:
                backoff_seconds = OUTBOX_BASE_BACKOFF_SECONDS * 2 ** (attempts - 1)
                next_attempt_at = datetime.now(timezone.utc) + timedelta(
                    seconds=backoff_seconds
                )

            async with session_factory() as session:
                async with session.begin():
                    await session.execute(
                        update(SyncOutbox)
                        .where(SyncOutbox.id == event_id)
                        .values(
                            status="failed" if exhausted else "pending",
                            next_attempt_at=next_attempt_at,
                            last_error=str(ex),
                            updated_at=datetime.now(timezone.utc),
                        )
                    )
            failed += 1
            logger.exception(
                "Failed to retry sync outbox event",
                extra={
                    "event_id": event_id,
                    "attempts": attempts,
                    "persistence_status": "failed",
                    "retry_exhausted": exhausted,
                },
            )
        else:
            async with session_factory() as session:
                async with session.begin():
                    await session.execute(
                        update(SyncOutbox)
                        .where(SyncOutbox.id == event_id)
                        .values(
                            status="done",
                            next_attempt_at=None,
                            updated_at=datetime.now(timezone.utc),
                        )
                    )
            completed += 1

    return {"processed": processed, "completed": completed, "failed": failed}


async def run_sync_outbox_retry() -> dict[str, int]:
    config = load_config()
    engine = create_async_engine(config.postgres.DSN, pool_pre_ping=True)
    session_factory = create_session_factory(engine)
    try:
        result = await retry_pending_sync_events(session_factory)
        logger.info("Completed sync outbox retry", extra=result)
        return result
    finally:
        await engine.dispose()