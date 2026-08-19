# Support Bot Repository Instructions

## Project Overview

This repository contains an async Telegram support bot built with aiogram. It receives private user messages, creates or reuses forum topics in a configured group, forwards messages between the user and the topic, and provides admin commands for moderation and newsletters.

The application is stateful but has no relational database. Redis stores user records, forum-topic indexes, FSM state, and APScheduler jobs.

## Runtime and Tooling

- Python: 3.14 only (`.python-version`, `pyproject.toml`)
- Dependency manager: uv
- Dependency declarations: `pyproject.toml`
- Reproducible dependency resolution: `uv.lock`
- Container base: Python 3.14 Alpine
- Local orchestration: Docker Compose
- Services: `bot` and `redis`
- Redis persistence: Compose-managed named volume `redis-data`, mounted at `/data`; do not restore a repository bind mount or commit Redis data files
- Bot container command: `python -m app`, defined in `Dockerfile`
- Required configuration: `.env` based on `.env.example`; never commit secrets
- Dependency automation: `.github/dependabot.yml` updates Python and Docker dependencies weekly

Use uv for dependency operations:

```bash
uv sync
uv add <package>
uv lock
uv lock --check
uv run python -m app
```

Do not recreate `requirements.txt` or manually edit `uv.lock` unless there is a specific lockfile repair reason. Keep dependency changes in `pyproject.toml` and regenerate the lockfile with uv.

The project currently requires `setuptools<82` because `aiogram-newsletter 0.0.12` pulls in APScheduler 3.10.0, whose package initializer imports the legacy `pkg_resources` module. Do not remove this constraint without verifying a newer compatible newsletter/APScheduler release and testing startup on Python 3.14.

## Application Startup

The main runtime path is in `app/__main__.py`:

1. `load_config()` reads environment variables.
2. The bot, Redis FSM storage, Redis-backed APScheduler job store, and scheduler are initialized.
3. Routers are registered through the bot manager.
4. Middlewares are registered on the dispatcher.
5. Startup configures commands and starts the scheduler.
6. aiogram begins polling Telegram updates.
7. Shutdown stops the scheduler, closes storage, removes the webhook, and releases resources.

When changing startup resources, update both startup and shutdown paths. Redis is required for normal operation; local runs may log Redis connection errors unless Redis is available at the configured host and port.

## Component Map

### Configuration and infrastructure

- `app/config.py`: `BotConfig`, `RedisConfig`, `Config`, and `load_config()`. Add new environment variables here and document them in `.env.example` and `README.md`.
- `app/logger.py`: logging setup, including console and rotating-file behavior. Preserve useful operational logs and avoid logging tokens or user secrets.
- `Dockerfile`: multi-stage uv setup, Alpine runtime image, dependency installation into `/opt/venv`, and the default bot command. Keep the lockfile-based install reproducible.
- `docker-compose.yml`: local bot/Redis orchestration, service dependency, network, and named Redis volume. Keep Redis data outside the repository.

### Bot orchestration

- `app/bot/manager.py`: `Manager` centralizes message sending/deletion, localized text access, FSM state, configuration, and user context. Reuse it in handlers instead of duplicating Telegram API/message bookkeeping.
- `app/bot/commands.py`: registers and removes Telegram commands by chat scope and language. Update this when adding or renaming user-visible bot commands.
- `app/bot/handlers/__init__.py`: router assembly. A handler module is inert until its router is included here.
- `app/bot/handlers/errors.py`: maps Telegram and domain exceptions to logs and developer notifications. Preserve specific exception handling before generic handling.

### Private-chat flow

Files under `app/bot/handlers/private/` handle direct user interactions:

- `command.py`: `/start`, language selection entry points, `/source`, and developer-only `/newsletter`.
- `message.py`: incoming text/media, edited messages, forwarding to the user topic, and album handling.
- `callback_query.py`: language-selection callbacks and related menu transitions.
- `my_chat_member.py`: tracks whether a user joins, blocks, or unblocks the bot.
- `windows.py`: private-chat FSM/window helpers used by conversational flows.

Private message handling normally relies on middleware-injected `user_data`, `redis`, and `manager` values. Preserve ban checks, language selection, topic recovery, and album behavior when modifying this flow.

### Group/topic flow

Files under `app/bot/handlers/group/` handle the configured support group:

- `command.py`: topic-scoped commands such as `/ban`, `/silent`, `/information`, and ID/admin operations.
- `message.py`: forum-topic lifecycle/service messages and forwarding replies from topics back to private users.

Most group handlers require a non-null `message_thread_id` and the configured `BOT_GROUP_ID`. Messages in the group main chat are intentionally ignored unless a handler explicitly supports them.

Be careful with Telegram messages from anonymous administrators: they may have `sender_chat` and no `from_user`. Do not assume every group message has a user sender when reading identity, permissions, or user data.

### Middleware

Middleware registration is in `app/bot/middlewares/__init__.py` and the implementations are:

- `redis.py`: injects Redis storage and user data, synchronizes user identity fields, and applies the single-language shortcut when only one language is configured.
- `manager.py`: injects `Manager` with the effective language and request context.
- `album.py`: collects media-group updates with a TTL cache and delay, then exposes an `Album` object.
- `throttling.py`: rate-limits message handling and removes throttled messages.
- `redis.py` and `manager.py` run at the update/outer middleware layer; album and throttling behavior is message-specific. Preserve ordering when changing registration.

### Domain types and persistence

- `app/bot/types/album.py`: `Album` aggregates Telegram media-group messages and converts them to aiogram input media or sends them as a group.
- `app/bot/utils/redis/models.py`: `UserData` is the serialized user record, including the forum thread ID, language, ban state, silent-mode state, FSM state, and timestamps.
- `app/bot/utils/redis/redis.py`: `RedisStorage` manages user hashes and reverse indexes by forum thread. Extend this abstraction for new Redis operations rather than scattering raw Redis commands through handlers.
- `app/bot/utils/create_forum_topic.py`: creates or retrieves topics, handles Telegram retry limits, updates Redis indexes, and raises domain exceptions.
- `app/bot/utils/exceptions.py`: domain exception types consumed by `handlers/errors.py`.
- `app/bot/utils/texts.py`: `SUPPORTED_LANGUAGES`, localized `TextMessage.data`, and text lookup. Add a language in both the language map and every required localized text entry.

## Where to Make Common Changes

- New private command: `app/bot/handlers/private/command.py`, then update `app/bot/commands.py` and localized text entries.
- New group/topic command: `app/bot/handlers/group/command.py`, respecting group ID and topic filters.
- New private message/media behavior: `app/bot/handlers/private/message.py`; update `AlbumMiddleware` or `Album` only when media-group semantics change.
- New callback flow: `app/bot/handlers/private/callback_query.py` and its router/texts.
- New user state: `UserData`, `RedisStorage`, and the middleware that loads/saves the record must agree on serialization and indexes.
- New environment setting: `app/config.py`, `.env.example`, README environment table, and deployment configuration if needed.
- New error category: define an exception in `app/bot/utils/exceptions.py` and add specific routing in `app/bot/handlers/errors.py`.
- New dependency: use `uv add`, review the resolver output, commit both `pyproject.toml` and `uv.lock`, and test the Docker build.
- New deployment behavior: update `Dockerfile`, `docker-compose.yml`, and README together. Do not put the bot command back into Compose unless intentionally overriding the image default.

## Behavioral Invariants

- `BOT_TOKEN`, `BOT_DEV_ID`, `BOT_GROUP_ID`, `BOT_EMOJI_ID`, `REDIS_HOST`, `REDIS_PORT`, and `REDIS_DB` are required configuration values.
- `DEV_ID` gates developer-only operations such as `/newsletter` and receives operational error notifications.
- User-to-topic mapping is persisted in Redis; deleting or changing indexes can orphan conversations.
- Forum-topic creation is rate-limited by Telegram and may require retry handling.
- Silent mode, ban state, language, and topic IDs are user-specific state and must survive normal restarts.
- Localized text changes should preserve all supported language keys and avoid hard-coding user-facing text in handlers.
- Do not expose bot tokens, Redis credentials, or private user data in logs, tests, commits, or documentation.

## Validation Workflow

Before submitting a change, use the narrowest relevant checks, then run the container checks for runtime or dependency changes:

```bash
uv lock --check
uv run python -c 'import app; import aiogram; import redis; print("imports ok")'
docker compose config --quiet
docker build --tag support-bot:check .
```

For changes affecting Redis or startup, use the full integration check and clean it up afterward:

```bash
docker compose up --build -d
docker compose ps
docker compose logs --tail=150 bot redis
docker compose down
```

Successful startup should include Redis `Ready to accept connections` and bot scheduler/polling messages. Do not leave Compose services running after verification. There is currently no test suite, CI workflow, or lint configuration; do not claim those checks ran unless they are added and executed.

## Change Style

- Keep changes focused and follow existing module boundaries.
- Prefer existing aiogram, Redis, and manager abstractions over new parallel infrastructure.
- Preserve public APIs and serialized Redis shapes unless a migration is intentional and documented.
- Add tests when introducing test infrastructure or when a focused test location exists.
- Keep comments rare and explain only non-obvious control flow.
- Never commit `.env`, `.venv`, Redis data, generated logs, or local Docker state.