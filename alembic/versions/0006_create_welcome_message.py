"""create welcome message table

Revision ID: 0006_create_welcome_message
Revises: 0005_create_user_sources
Create Date: 2026-09-02
"""

from alembic import op

revision = "0006_create_welcome_message"
down_revision = "0005_create_user_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE welcome_message (
            id SMALLINT PRIMARY KEY DEFAULT 1,
            source_chat_id BIGINT NOT NULL,
            source_message_id BIGINT NOT NULL,
            content_type TEXT,
            updated_by BIGINT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT welcome_message_singleton CHECK (id = 1)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS welcome_message")
