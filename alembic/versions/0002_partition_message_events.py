"""partition message events by month

Revision ID: 0002_partition_message_events
Revises: 0001_create_message_events
Create Date: 2026-08-19
"""

from alembic import op

revision = "0002_partition_message_events"
down_revision = "0001_create_message_events"
branch_labels = None
depends_on = None


_PARTITION_OPTIONS = """
    SET (
        autovacuum_vacuum_scale_factor = 0.02,
        autovacuum_analyze_scale_factor = 0.01,
        autovacuum_vacuum_cost_delay = 10
    )
"""


def upgrade() -> None:
    op.execute("ALTER SEQUENCE message_events_id_seq OWNED BY NONE")
    op.execute(
        """
        CREATE TABLE message_events_partitioned (
            id BIGINT NOT NULL DEFAULT nextval('message_events_id_seq'),
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
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (id, created_at)
        ) PARTITION BY RANGE (created_at)
        """
    )
    op.execute(
        """
        DO $$
        DECLARE
            partition_start DATE;
            partition_end DATE;
            partition_name TEXT;
            month_offset INTEGER;
        BEGIN
            FOR month_offset IN -24..12 LOOP
                partition_start :=
                    (date_trunc('month', CURRENT_DATE) + make_interval(months => month_offset))::date;
                partition_end :=
                    (partition_start + INTERVAL '1 month')::date;
                partition_name := 'message_events_' || to_char(partition_start, 'YYYY_MM');
                EXECUTE format(
                    'CREATE TABLE %I PARTITION OF message_events_partitioned FOR VALUES FROM (%L) TO (%L)',
                    partition_name,
                    partition_start,
                    partition_end
                );
            END LOOP;
        END $$;
        """
    )
    op.execute(
        """
        CREATE TABLE message_events_default
            PARTITION OF message_events_partitioned DEFAULT
        """
    )
    op.execute("INSERT INTO message_events_partitioned SELECT * FROM message_events")
    op.execute("DROP TABLE message_events")
    op.execute("ALTER TABLE message_events_partitioned RENAME TO message_events")
    op.execute("ALTER SEQUENCE message_events_id_seq OWNED BY message_events.id")
    op.execute(
        """
        SELECT setval(
            'message_events_id_seq',
            COALESCE((SELECT MAX(id) FROM message_events), 1),
            EXISTS (SELECT 1 FROM message_events)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_message_events_telegram_user_created_at
            ON message_events (telegram_user_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_message_events_message_thread_created_at
            ON message_events (message_thread_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_message_events_direction_created_at
            ON message_events (direction, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_message_events_payload_json
            ON message_events USING GIN (payload_json)
        """
    )
    op.execute(
        """
        DO $$
        DECLARE
            partition_record RECORD;
        BEGIN
            FOR partition_record IN
                SELECT quote_ident(schemaname) || '.' || quote_ident(tablename) AS partition_name
                FROM pg_tables
                WHERE schemaname = 'public'
                  AND (tablename LIKE 'message_events_20%%' OR tablename = 'message_events_default')
            LOOP
                EXECUTE 'ALTER TABLE ' || partition_record.partition_name ||
                    ' SET (autovacuum_vacuum_scale_factor = 0.02,' ||
                    ' autovacuum_analyze_scale_factor = 0.01,' ||
                    ' autovacuum_vacuum_cost_delay = 10)';
            END LOOP;
        END $$;
        """
    )
    op.execute(
        "COMMENT ON TABLE message_events IS "
        "'Monthly partitions; retain 24 months and drop expired partitions instead of deleting rows.'"
    )


def downgrade() -> None:
    op.execute("ALTER SEQUENCE message_events_id_seq OWNED BY NONE")
    op.execute(
        """
        CREATE TABLE message_events_unpartitioned (
            id BIGINT PRIMARY KEY DEFAULT nextval('message_events_id_seq'),
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
        """
        INSERT INTO message_events_unpartitioned
        SELECT DISTINCT ON (id) id, direction, telegram_user_id, group_chat_id,
            private_chat_id, message_thread_id, source_message_id, target_message_id,
            media_group_id, has_media, payload_json, status, error_code, error_text, created_at
        FROM message_events
        ORDER BY id, created_at
        """
    )
    op.execute("DROP TABLE message_events CASCADE")
    op.execute("ALTER TABLE message_events_unpartitioned RENAME TO message_events")
    op.execute("ALTER SEQUENCE message_events_id_seq OWNED BY message_events.id")
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
