import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter

from app.config import Config
from .exceptions import CreateForumTopicException, NotEnoughRightsException, NotAForumException
from .redis import RedisStorage
from .redis.models import UserData
from app.db.state import mirror_user_state


async def get_or_create_forum_topic(
        bot: Bot,
        redis: RedisStorage,
        config: Config,
        user_data: UserData,
        postgres_session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> int:
    if user_data.message_thread_id is None:
        try:
            # If message_thread_id is not found, create a forum topic
            message_thread_id = await create_forum_topic(
                bot, config, user_data.full_name,
            )
            user_data.message_thread_id = message_thread_id
            await redis.update_user(user_data.id, user_data)
            if postgres_session_factory is not None:
                try:
                    await mirror_user_state(postgres_session_factory, user_data)
                except Exception:
                    logging.exception(
                        "Failed to mirror topic mapping to PostgreSQL",
                        extra={
                            "telegram_user_id": user_data.id,
                            "message_thread_id": message_thread_id,
                            "persistence_status": "failed",
                        },
                    )

        except Exception as e:
            for dev_user_id in config.bot.DEV_USER_IDS:
                await bot.send_message(dev_user_id, str(e))
            logging.exception(e)

    return user_data.message_thread_id


async def create_forum_topic(bot: Bot, config: Config, name: str) -> int:
    """
    Creates a forum topic in the specified chat.

    :param bot: The Aiogram Bot instance.
    :param config: The configuration object.
    :param name: The name of the forum topic.

    :return: The message thread ID of the created forum topic.
    :raises NotEnoughRightsException: If the bot doesn't have enough rights to create a forum topic.
    :raises CreateForumTopicException: If an error occurs while creating the forum topic.
    """
    try:
        # Attempt to create a forum topic
        forum_topic = await bot.create_forum_topic(
            chat_id=config.bot.GROUP_ID,
            name=name,
            icon_custom_emoji_id=config.bot.BOT_EMOJI_ID,
            request_timeout=30,
        )
        return forum_topic.message_thread_id

    except TelegramRetryAfter as ex:
        # Handle Retry-After exception (rate limiting)
        logging.warning(ex.message)
        await asyncio.sleep(ex.retry_after)
        return await create_forum_topic(bot, config, name)

    except TelegramBadRequest as ex:
        if "not enough rights" in ex.message:
            # Raise an exception if the bot doesn't have enough rights
            raise NotEnoughRightsException

        elif "not a forum" in ex.message:
            # Raise an exception if the chat is not a forum
            raise NotAForumException

        # Raise a generic exception for other cases
        raise CreateForumTopicException

    except Exception as ex:
        # Re-raise any other exceptions
        raise ex
