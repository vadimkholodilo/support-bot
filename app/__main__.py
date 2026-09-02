import asyncio
import logging
import sys
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from .bot import commands
from .bot.handlers import include_routers
from .bot.middlewares import register_middlewares
from .cli import migrate
from .config import load_config, Config
from .db import create_async_engine, create_session_factory
from .db.outbox import run_sync_outbox_retry
from .feature_flags import setup_feature_flags
from .logger import setup_logger


async def on_shutdown(
    apscheduler: AsyncIOScheduler,
    outbox_scheduler: AsyncIOScheduler,
    dispatcher: Dispatcher,
    config: Config,
    bot: Bot,
    postgres_engine: AsyncEngine,
) -> None:
    """
    Shutdown event handler. This runs when the bot shuts down.

    :param apscheduler: AsyncIOScheduler: The apscheduler instance.
    :param outbox_scheduler: AsyncIOScheduler: The outbox retry scheduler instance.
    :param dispatcher: Dispatcher: The bot dispatcher.
    :param config: Config: The config instance.
    :param bot: Bot: The bot instance.
    """
    # Stop apschedulers
    apscheduler.shutdown()
    outbox_scheduler.shutdown()
    await postgres_engine.dispose()
    # Delete commands and close storage when shutting down
    await commands.delete(bot, config)
    await dispatcher.storage.close()
    await bot.delete_webhook()
    await bot.session.close()


async def on_startup(
    apscheduler: AsyncIOScheduler,
    outbox_scheduler: AsyncIOScheduler,
    config: Config,
    bot: Bot,
) -> None:
    """
    Startup event handler. This runs when the bot starts up.

    :param apscheduler: AsyncIOScheduler: The apscheduler instance.
    :param outbox_scheduler: AsyncIOScheduler: The outbox retry scheduler instance.
    :param config: Config: The config instance.
    :param bot: Bot: The bot instance.
    """
    # Start apschedulers
    apscheduler.start()
    outbox_scheduler.start()
    # Setup commands when starting up
    await commands.setup(bot, config)


async def main() -> None:
    """
    Main function that initializes the bot and starts the event loop.
    """
    # Load config
    config = load_config()

    # Register the environment-variable feature-flag provider
    setup_feature_flags()

    # Initialize PostgreSQL resources
    postgres_engine = create_async_engine(config.postgres.DSN, pool_pre_ping=True)
    postgres_session_factory: async_sessionmaker = create_session_factory(postgres_engine)

    # Initialize apscheduler used for newsletters
    job_store = RedisJobStore(
        host=config.redis.HOST,
        port=config.redis.PORT,
        db=config.redis.DB,
    )
    apscheduler = AsyncIOScheduler(
        jobstores={"default": job_store},
    )

    # Initialize a separate apscheduler for the outbox retry job so it never
    # shows up in aiogram_newsletter's job listing, which assumes every job
    # in the scheduler it's given uses a DateTrigger.
    outbox_job_store = RedisJobStore(
        host=config.redis.HOST,
        port=config.redis.PORT,
        db=config.redis.DB,
        jobs_key="apscheduler.outbox_jobs",
        run_times_key="apscheduler.outbox_run_times",
    )
    outbox_scheduler = AsyncIOScheduler(
        jobstores={"default": outbox_job_store},
    )
    outbox_scheduler.add_job(
        run_sync_outbox_retry,
        "interval",
        seconds=30,
        id="retry_sync_outbox",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(timezone.utc),
    )

    # Initialize Redis storage
    storage = RedisStorage.from_url(
        url=config.redis.dsn(),
    )

    # Create Bot and Dispatcher instances
    bot = Bot(
        token=config.bot.TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
        ),
    )
    dp = Dispatcher(
        apscheduler=apscheduler,
        outbox_scheduler=outbox_scheduler,
        storage=storage,
        config=config,
        bot=bot,
        postgres_session_factory=postgres_session_factory,
        postgres_engine=postgres_engine,
    )

    # Register startup handler
    dp.startup.register(on_startup)
    # Register shutdown handler
    dp.shutdown.register(on_shutdown)

    # Include routes
    include_routers(dp)
    # Register middlewares
    register_middlewares(
        dp, config=config, redis=storage.redis, apscheduler=apscheduler
    )

    # Start the bot
    await bot.delete_webhook()
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    # Set up logging
    setup_logger()
    if len(sys.argv) > 1:
        if sys.argv[1] != "migrate" or len(sys.argv) != 2:
            raise SystemExit("Usage: python -m app [migrate]")
        try:
            migrate()
        except Exception:
            logging.getLogger(__name__).exception("Database migration failed")
            raise SystemExit(1)
    else:
        # Run the bot
        asyncio.run(main())
