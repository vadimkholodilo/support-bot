"""create sync outbox table

Revision ID: 0003_create_sync_outbox
Revises: 0002_partition_message_events
Create Date: 2026-08-21
"""

from alembic import op

revision = "0003_create_sync_outbox"
down_revision = "0002_partition_message_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE sync_outbox (
            id BIGSERIAL PRIMARY KEY,
            event_type TEXT NOT NULL,
            event_key TEXT NOT NULL,
            payload_json JSONB NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0,
            next_attempt_at TIMESTAMPTZ,
            last_error TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_sync_outbox_event_type_event_key
                UNIQUE (event_type, event_key)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_sync_outbox_status_next_attempt_at
            ON sync_outbox (status, next_attempt_at)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS sync_outbox")
