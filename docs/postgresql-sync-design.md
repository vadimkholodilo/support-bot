# PostgreSQL + Redis Sync Design for Support Bot

## 1. Goal

Add durable PostgreSQL storage for analytics and AI while keeping Redis for fast bot runtime state.

Targets:
- Persist chat history in PostgreSQL.
- Keep FSM in Redis only.
- Keep routing behavior stable during migration.
- Deliver in small, reviewable steps without overengineering.

## 2. Current State

Redis currently stores:
- User routing and moderation state.
- Topic lookup indexes.
- Aiogram FSM state.
- APScheduler job store.

Current message flow forwards/copies messages but does not persist durable history in this repository.

## 3. Target Architecture

- PostgreSQL:
  - Durable chat history source.
  - Later mirror/source for user/topic state.
  - Query base for analytics and AI.

- Redis:
  - FSM state.
  - Fast routing cache.
  - Existing scheduler store (unchanged initially).

## 3.1 Chosen Persistence Stack

Chosen:
- ORM: SQLAlchemy 2.x (async ORM with AsyncSession).
- Migrations: Alembic.
- PostgreSQL driver: asyncpg.

Why this stack:
- Most popular and battle-tested option in Python ecosystem.
- Native async support in SQLAlchemy 2.x API.
- Strong long-term maintainability and hiring/onboarding advantage.
- Alembic integrates directly with SQLAlchemy and supports full raw SQL control.

Migration style policy:
- Prefer raw SQL for schema-changing migrations where precision matters (partitions, indexes, autovacuum table settings, custom DDL).
- Use Alembic as migration runner/versioning tool, with SQL executed via Alembic operations.
- Views for analytics are allowed and should be created via explicit SQL migrations.

## 4. PostgreSQL Data Model

### 4.1 Phase 1: message_events
- id (bigserial, pk)
- direction (text, not null) -- private_to_group | group_to_private
- telegram_user_id (bigint)
- group_chat_id (bigint)
- private_chat_id (bigint)
- message_thread_id (bigint)
- source_message_id (bigint)
- target_message_id (bigint)
- media_group_id (text)
- has_media (boolean, not null, default false)
- payload_json (jsonb)
- status (text, not null, default 'forwarded') -- forwarded | failed | blocked | retried
- error_code (text)
- error_text (text)
- created_at (timestamptz, not null, default now())

Indexes:
- (telegram_user_id, created_at desc)
- (message_thread_id, created_at desc)
- (direction, created_at desc)
- gin(payload_json)

### 4.2 Phase 2: sync_outbox
- id (bigserial, pk)
- event_type (text, not null)
- event_key (text, not null)
- payload_json (jsonb, not null)
- status (text, not null, default 'pending') -- pending | processing | done | failed
- attempts (int, not null, default 0)
- next_attempt_at (timestamptz)
- last_error (text)
- created_at (timestamptz, not null, default now())
- updated_at (timestamptz, not null, default now())

Indexes:
- (status, next_attempt_at)
- unique(event_type, event_key)

### 4.3 Phase 3: users and user_topics

users:
- telegram_user_id (bigint, unique, not null)
- username (text)
- full_name (text, not null)
- language_code (text)
- is_banned (boolean, not null, default false)
- created_at (timestamptz, not null, default now())
- updated_at (timestamptz, not null, default now())

user_topics:
- telegram_user_id (bigint, unique, not null)
- message_thread_id (bigint, unique)
- message_silent_mode (boolean, not null, default false)
- message_silent_id (bigint)
- updated_at (timestamptz, not null, default now())

## 5. PostgreSQL High-Volume Baseline

Apply from first rollout:
- Partition message_events by time (monthly minimum).
- Define retention early; drop old partitions instead of mass deletes.
- Use table-specific autovacuum settings on hot tables.
- Avoid over-indexing write-heavy tables.
- Tune WAL/checkpoint settings to avoid checkpoint storms.

Single-process decision:
- Use application-level pooling only.
- Revisit PgBouncer when multiple processes/replicas are introduced.

## 6. Logging and Operations Scope

Keep this lightweight:
- No dashboards/alerts at this stage.
- Use structured logs and periodic manual review.

Required log fields:
- direction
- telegram_user_id
- message_thread_id
- source_message_id
- persistence status/error

## 7. Recommended Migration Path

1. Phase 0: Foundation (PostgreSQL runtime + config + migrations).
2. Phase 1: Write message_events (log-and-continue on DB failures).
3. Phase 2: Add sync_outbox + retry worker.
4. Phase 3: Dual-write users and user_topics.
5. Phase 4: Redis-first read with PostgreSQL fallback for mapping.
6. Phase 5: PostgreSQL-first state writes (optional later).

## 8. Implementation Checklist (Review-Driven)

Do not start the next step until current step is reviewed.

### 8.1 Phase 0: Foundations

#### Step 0.1 PostgreSQL runtime
- [x] Add postgres service to docker-compose.yml with persistent volume.
- [x] Add log rotation options for postgres container.
- [x] Keep bot and redis behavior unchanged.

Acceptance:
- [x] docker compose config --quiet passes.
- [x] docker compose up -d postgres starts successfully.

#### Step 0.2 Configuration model
- [x] Extend app/config.py with PostgresConfig.
- [x] Add PostgreSQL env vars to .env.example.
- [x] Document vars in README.md.

Required vars:
- [x] POSTGRES_DSN

Acceptance:
- [x] Config loads PostgreSQL settings correctly.

#### Step 0.3 Migration setup
- [x] Add migration tooling (Alembic, required).
- [x] Add SQLAlchemy async setup (engine + session management).
- [x] Configure Alembic for SQLAlchemy metadata and raw SQL migrations.
- [x] Create initial migration for message_events.

Acceptance:
- [x] Fresh DB migrates successfully.
- [x] Raw SQL migration flow is validated (upgrade and downgrade).

#### Step 0.4 High-volume baseline
- [x] Add partitioning strategy for message_events.
- [x] Define retention policy.
- [x] Add table-level autovacuum settings in migrations where needed.

Acceptance:
- [ ] Baseline appears in migrations and is reproducible.

### 8.2 Phase 1: Message history writes

#### Step 1.1 PostgreSQL write layer
- [x] Add dedicated PostgreSQL write module.
- [x] Implement async insert for message_events.

Acceptance:
- [ ] Minimal event insert works.

#### Step 1.2 Handler integration
- [x] Write event records from app/bot/handlers/private/message.py.
- [x] Write event records from app/bot/handlers/group/message.py.
- [x] Keep forwarding path log-and-continue on DB failures.

Acceptance:
- [ ] Forwarding is unaffected by PostgreSQL outages.
- [ ] Events are persisted when PostgreSQL is available.

#### Step 1.3 Structured logs
- [x] Add structured persistence logs for success/failure.

Acceptance:
- [x] Manual log review is enough to diagnose persistence failures.

### 8.3 Phase 2: Retry/outbox

#### Step 2.1 Outbox schema
- [x] Add sync_outbox migration with idempotency key.

Acceptance:
- [x] Duplicate queue entries are prevented.

#### Step 2.2 Queue on failure
- [x] Enqueue failed event writes into outbox.

Acceptance:
- [x] Failed writes are captured for retry.

#### Step 2.3 Retry worker
- [ ] Add periodic retry worker (APScheduler task or background loop).
- [ ] Implement capped attempts and backoff.

Acceptance:
- [ ] Transient outage recovery backfills queued events.

### 8.4 Phase 3: State dual-write

#### Step 3.1 State tables
- [ ] Add migrations for users and user_topics.

Acceptance:
- [ ] Unique constraints and lookup indexes are in place.

#### Step 3.2 Mirror updates
- [ ] Mirror user updates from app/bot/middlewares/redis.py.
- [ ] Mirror topic mapping updates from app/bot/utils/create_forum_topic.py.

Acceptance:
- [ ] Redis remains primary; PostgreSQL mirrors are correct.

### 8.5 Phase 4: Redis-first read with PostgreSQL fallback

#### Step 4.1 Fallback lookup
- [ ] On Redis miss, read mapping from PostgreSQL and repopulate Redis.

Acceptance:
- [ ] Routing works after deleting Redis mapping keys.

### 8.6 Phase 5: PostgreSQL-first state (later)

#### Step 5.1 Promote source of truth
- [ ] Switch state writes to PostgreSQL-first.
- [ ] Keep Redis as cache and FSM.

Acceptance:
- [ ] Routing correctness remains stable with Redis cache eviction.

### 8.7 Review gate after each step
- [ ] Share changed files.
- [ ] Share migration summary (if any).
- [ ] Share validation results.
- [ ] Wait for explicit approval before continuing.
