"""create users and user topics tables

Revision ID: 0004_users_and_user_topics
Revises: 0003_create_sync_outbox
Create Date: 2026-08-21
"""

from alembic import op

revision = "0004_users_and_user_topics"
down_revision = "0003_create_sync_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE users (
            telegram_user_id BIGINT PRIMARY KEY,
            username TEXT,
            full_name TEXT NOT NULL,
            language_code TEXT,
            is_banned BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE user_topics (
            telegram_user_id BIGINT PRIMARY KEY
                REFERENCES users (telegram_user_id) ON DELETE CASCADE,
            message_thread_id BIGINT UNIQUE,
            message_silent_mode BOOLEAN NOT NULL DEFAULT FALSE,
            message_silent_id BIGINT,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_user_topics_message_thread_id
            ON user_topics (message_thread_id)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_users_updated_at
            ON users (updated_at)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_topics")
    op.execute("DROP TABLE IF EXISTS users")
