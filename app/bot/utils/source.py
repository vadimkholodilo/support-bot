from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.sources import (
    UNKNOWN_SOURCE,
    get_user_source,
    parse_source,
    save_user_source,
)


class SourceService:
    """Resolves and persists the acquisition source for a Telegram user.

    The source is derived from the ``/start`` deep-link payload using the
    ``src_`` prefix convention (``t.me/<bot>?start=src_twitter`` -> ``twitter``)
    and stored durably in PostgreSQL only. Missing or empty payloads resolve to
    ``"Unknown"``. Reuse this service anywhere the source is needed instead of
    touching the ``user_sources`` table directly.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    @staticmethod
    def parse(payload: str | None) -> str:
        """Return the source encoded in a ``/start`` payload without storing it."""
        return parse_source(payload)

    async def remember(self, telegram_user_id: int, payload: str | None) -> str:
        """Parse the payload, persist the resulting source, and return it."""
        source = parse_source(payload)
        await save_user_source(self._session_factory, telegram_user_id, source)
        return source

    async def get(self, telegram_user_id: int) -> str:
        """Return the stored source for the user, or ``"Unknown"`` if there is none."""
        return await get_user_source(self._session_factory, telegram_user_id) or UNKNOWN_SOURCE
