#!/usr/bin/env bash
#
# Wipes local dev data so the bot flow can be tested from a clean state:
# truncates every PostgreSQL table (except alembic_version, so migration
# history is preserved) and flushes the configured Redis database.
#
# Usage:
#   scripts/reset_dev_data.sh          # asks for confirmation
#   scripts/reset_dev_data.sh -y       # skips confirmation
#
# Requires the postgres and redis services from docker-compose.yml to be up.

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

ASSUME_YES=false
if [[ "${1:-}" == "-y" || "${1:-}" == "--yes" ]]; then
    ASSUME_YES=true
fi

ENV_FILE=".env"
POSTGRES_DB="${POSTGRES_DB:-support_bot}"
POSTGRES_USER="${POSTGRES_USER:-support_bot}"
REDIS_DB="0"

if [[ -f "$ENV_FILE" ]]; then
    env_value() {
        local key="$1"
        grep -E "^${key}=" "$ENV_FILE" | tail -n1 | cut -d= -f2- || true
    }
    REDIS_DB="$(env_value REDIS_DB)"
    REDIS_DB="${REDIS_DB:-0}"
fi

if ! docker compose ps --status running --services 2>/dev/null | grep -qx postgres; then
    echo "error: the 'postgres' service is not running (docker compose up -d postgres)" >&2
    exit 1
fi
if ! docker compose ps --status running --services 2>/dev/null | grep -qx redis; then
    echo "error: the 'redis' service is not running (docker compose up -d redis)" >&2
    exit 1
fi

if [[ "$ASSUME_YES" != true ]]; then
    read -r -p "This will DELETE ALL data in the '${POSTGRES_DB}' database and flush Redis DB ${REDIS_DB}. Continue? [y/N] " reply
    if [[ ! "$reply" =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
fi

echo "Truncating PostgreSQL tables in '${POSTGRES_DB}' (except alembic_version)..."
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 <<'SQL'
DO $$
DECLARE
    target_tables text;
BEGIN
    SELECT string_agg(format('%I.%I', schemaname, tablename), ', ')
    INTO target_tables
    FROM pg_tables
    WHERE schemaname = 'public'
      AND tablename <> 'alembic_version';

    IF target_tables IS NOT NULL THEN
        EXECUTE format('TRUNCATE TABLE %s RESTART IDENTITY CASCADE', target_tables);
    END IF;
END $$;
SQL

echo "Flushing Redis DB ${REDIS_DB}..."
docker compose exec -T redis redis-cli -n "$REDIS_DB" FLUSHDB

echo "Done. Database tables truncated and Redis DB ${REDIS_DB} flushed."
