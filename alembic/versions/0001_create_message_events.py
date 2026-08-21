"""create message events table

Revision ID: 0001_create_message_events
Revises:
Create Date: 2026-08-19
"""

from alembic import op

revision = "0001_create_message_events"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE message_events (
            id BIGSERIAL PRIMARY KEY,
            direction TEXT NOT NULL,
            telegram_user_id BIGINT,
            group_chat_id BIGINT,
            private_chat_id BIGINT,
            message_thread_id BIGINT,
            source_message_id BIGINT,
            target_message_id BIGINT,
            media_group_id TEXT,
            has_media BOOLEAN NOT NULL DEFAULT FALSE,
            payload_json JSONB,
            status TEXT NOT NULL DEFAULT 'forwarded',
            error_code TEXT,
            error_text TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_message_events_telegram_user_created_at "
        "ON message_events (telegram_user_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX ix_message_events_message_thread_created_at "
        "ON message_events (message_thread_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX ix_message_events_direction_created_at "
        "ON message_events (direction, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX ix_message_events_payload_json "
        "ON message_events USING GIN (payload_json)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS message_events")
