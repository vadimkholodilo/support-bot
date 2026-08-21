---
name: postgres-sync-observability
description: 'Analyze support-bot PostgreSQL persistence and migration health. Use when reviewing message event logs, checking whether Telegram messages were persisted, diagnosing missing or failed inserts, correlating private/group events by thread, or summarizing sync reliability over time.'
argument-hint: 'Describe the time window, thread, user, direction, or failure you want analyzed.'
user-invocable: true
---

# PostgreSQL Sync Observability

## Purpose

Use this skill to investigate the support bot's message persistence path from exported production artifacts and produce either:

- an incident diagnosis for missing, failed, or delayed events; or
- a compact health summary for a selected time window.

Do not connect this workflow to production. The operator exports bounded, non-secret PostgreSQL metadata and application logs from production, then provides the files for offline analysis. The durable event source is PostgreSQL `message_events`; logs provide migration, connection, and exception context.

## Safety Rules

- Never print `BOT_TOKEN`, database passwords, full DSNs, message payloads, message text, or private user data.
- Prefer counts, directions, IDs, thread IDs, statuses, and timestamps.
- Use a bounded time window and `LIMIT` for production exports.
- Treat `message_events` as the source of truth for persistence; do not infer persistence from a Telegram delivery log alone.
- Do not alter production data. Use read-only SQL only.

## Export From Production

The operator should run these commands on the production host, replacing the time window as needed. Create a restricted directory first:

```bash
export OBS_DIR="support-bot-observability-$(date +%Y%m%d-%H%M%S)"
mkdir -m 700 "$OBS_DIR"
```

Export event metadata without `payload_json` or message text. `COPY ... TO STDOUT` writes the CSV to the operator's host:

```bash
rtk docker compose exec -T postgres psql -U support_bot -d support_bot -c \
  "COPY (
     SELECT id, direction, telegram_user_id, group_chat_id, private_chat_id,
            message_thread_id, source_message_id, target_message_id,
            media_group_id, has_media, status, error_code, created_at
       FROM message_events
      WHERE created_at >= NOW() - INTERVAL '24 hours'
      ORDER BY created_at
      LIMIT 100000
   ) TO STDOUT WITH CSV HEADER" > "$OBS_DIR/message_events.csv"
```

Export migration state and table existence separately:

```bash
rtk docker compose exec -T postgres psql -U support_bot -d support_bot -At -c \
  "SELECT version_num FROM alembic_version;" > "$OBS_DIR/alembic_version.txt"
rtk docker compose exec -T postgres psql -U support_bot -d support_bot -At -c \
  "SELECT to_regclass('public.message_events');" > "$OBS_DIR/message_events_table.txt"
```

Export bounded application and migration logs. Keep the time window aligned with the CSV export:

```bash
rtk docker compose logs --no-color --since=24h --tail=10000 bot > "$OBS_DIR/bot.log"
rtk docker compose logs --no-color --since=24h --tail=10000 migrate > "$OBS_DIR/migrate.log"
```

Before sharing the directory, scan it for secrets and remove any affected artifact rather than attempting an unsafe partial redaction:

```bash
rtk rg -n -i 'BOT_TOKEN|POSTGRES_DSN|REDIS_PASSWORD|password=|secret|api[_-]?key' "$OBS_DIR"
```

Share only `message_events.csv`, migration state files, and sanitized logs. Do not export `payload_json` unless it has been reviewed and is known not to contain message content or personal data. Compressing the directory is optional; preserve its restrictive permissions.

## Offline Analysis Workflow

1. Identify the scope from the user's report: export window, direction, thread, user, or source message ID.
2. Confirm the artifact set before drawing conclusions:

   - `message_events.csv`
   - `alembic_version.txt`
   - `message_events_table.txt`
   - `bot.log`
   - `migrate.log`

3. Read the CSV with a structured parser such as Python's `csv` module. Do not use ad hoc splitting because CSV fields can be quoted. Keep analysis bounded to the exported files.

4. Produce counts by `direction` and `status`, earliest/latest timestamps, top `error_code` values, and the most active `message_thread_id` values.
5. For a reported source message, match `source_message_id` in the CSV and report its direction, thread, target ID, status, and timestamp.
6. Compare `bot.log` with CSV rows by direction, source message ID, and approximate timestamp. Remember that the current text formatter does not emit Python logging `extra` fields, so log lines may not contain every structured field.
7. Use `migrate.log`, `alembic_version.txt`, and `message_events_table.txt` to distinguish a migration failure from an application persistence failure.

Interpret missing data in context:

- Empty or `null` `message_events_table.txt`: migrations did not complete or the export targeted the wrong database.
- Empty `alembic_version.txt`: the migration chain did not start.
- Revision older than `0002_partition_message_events`: migrations are incomplete.
- Table exists but CSV is empty: no events fell within the export window, or inserts failed and were logged and swallowed.
- Rows exist only for one direction: inspect the corresponding handler path and its log entries.

## Interpretation

A successful Telegram forward followed by a PostgreSQL error is expected to preserve user-facing forwarding but creates a persistence gap. The current implementation has no outbox or retry worker, so failed inserts are not backfilled automatically; record this explicitly as the likely Phase 2 follow-up.

The current text logger includes the event summary message but does not serialize Python `logging` `extra` fields. Therefore, use CSV rows for structured event fields and use logs primarily for exception text, migration failures, connection failures, and service lifecycle events.

## Report Format

For an incident, report:

- Scope and services checked
- Schema/migration state
- Matching event rows or absence of rows
- Most likely cause, with evidence
- Whether user-facing forwarding was affected
- Recommended next action

For an overview, report:

- Time window and total events
- Counts by direction and status
- Forwarded rate per direction
- Failure/error count and top error codes
- Most active threads by event count
- Data gaps or limitations

Keep identifiers necessary for debugging, but omit payloads and secrets.
