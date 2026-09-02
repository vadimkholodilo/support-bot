"""create user sources table

Revision ID: 0005_create_user_sources
Revises: 0004_users_and_user_topics
Create Date: 2026-09-02
"""

from alembic import op

revision = "0005_create_user_sources"
down_revision = "0004_users_and_user_topics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE user_sources (
            telegram_user_id BIGINT PRIMARY KEY
                REFERENCES users (telegram_user_id) ON DELETE CASCADE,
            source TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_user_sources_source
            ON user_sources (source)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_sources")
