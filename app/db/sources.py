from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import UserSource

# Value stored when the ``/start`` payload carries no usable source.
UNKNOWN_SOURCE = "Unknown"
# Deep-link convention: ``t.me/<bot>?start=src_twitter`` -> source ``twitter``.
SOURCE_PREFIX = "src_"
# Telegram caps the start payload at 64 characters; mirror that on our side.
MAX_SOURCE_LENGTH = 64


def parse_source(payload: str | None) -> str:
    """Extract the acquisition source from a ``/start`` deep-link payload.

    Returns ``UNKNOWN_SOURCE`` when the payload is missing, empty, or does not
    follow the ``src_`` prefix convention.
    """
    if not payload:
        logging.info("parse_source: empty payload=%r -> %s", payload, UNKNOWN_SOURCE)
        return UNKNOWN_SOURCE
    stripped = payload.strip()
    if not stripped.startswith(SOURCE_PREFIX):
        logging.info(
            "parse_source: payload=%r missing %r prefix -> %s",
            payload,
            SOURCE_PREFIX,
            UNKNOWN_SOURCE,
        )
        return UNKNOWN_SOURCE
    value = stripped[len(SOURCE_PREFIX):].strip()
    if not value:
        logging.info("parse_source: payload=%r has empty source -> %s", payload, UNKNOWN_SOURCE)
        return UNKNOWN_SOURCE
    resolved = value[:MAX_SOURCE_LENGTH]
    logging.info("parse_source: payload=%r -> %r", payload, resolved)
    return resolved


async def save_user_source(
        session_factory: async_sessionmaker[AsyncSession],
        telegram_user_id: int,
        source: str,
) -> None:
    """Persist the user's source.

    First write wins for a concrete source: once a non-``Unknown`` value is
    stored it is never overwritten, but an existing ``Unknown`` row is upgraded
    when a later ``/start`` carries a real ``src_`` payload.
    """
    stmt = insert(UserSource).values(
        telegram_user_id=telegram_user_id,
        source=source,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[UserSource.telegram_user_id],
        set_={"source": stmt.excluded.source, "updated_at": func.now()},
        where=(
            (UserSource.source == UNKNOWN_SOURCE)
            & (stmt.excluded.source != UNKNOWN_SOURCE)
        ),
    )

    async with session_factory() as session:
        async with session.begin():
            await session.execute(stmt)


async def get_user_source(
        session_factory: async_sessionmaker[AsyncSession],
        telegram_user_id: int,
) -> str | None:
    """Return the stored source for the user, or ``None`` if nothing is stored."""
    async with session_factory() as session:
        return await session.scalar(
            select(UserSource.source).where(
                UserSource.telegram_user_id == telegram_user_id
            )
        )
