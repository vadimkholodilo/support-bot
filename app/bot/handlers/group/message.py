import asyncio
import logging
from html import escape
from typing import Optional

from aiogram import Router, F
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import MagicData
from aiogram.types import Message
from aiogram.utils.markdown import hlink

from app.bot.manager import Manager
from app.bot.types.album import Album
from app.bot.utils.admins import (
    collect_mention_entities,
    get_group_admin_ids,
    message_mentions_admin,
)
from app.bot.utils.redis import RedisStorage
from app.bot.utils.source import SourceService
from app.db.message_events import insert_message_event
from app.db.outbox import enqueue_sync_event
from app.feature_flags import SOURCE_TRACKING, is_enabled
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

router = Router()
router.message.filter(
    MagicData(F.event_chat.id == F.config.bot.GROUP_ID),  # type: ignore
    F.chat.type.in_(["group", "supergroup"]),
    F.message_thread_id.is_not(None),
)


@router.message(F.forum_topic_created)
async def handler(
    message: Message,
    manager: Manager,
    redis: RedisStorage,
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await asyncio.sleep(3)
    user_data = await redis.get_by_message_thread_id(message.message_thread_id)
    if not user_data: return None  # noqa

    # Generate a URL for the user's profile
    url = f"https://t.me/{user_data.username[1:]}" if user_data.username != "-" else f"tg://user?id={user_data.id}"

    # Get the appropriate text based on the user's state
    text = manager.text_message.get("user_started_bot").format(name=hlink(user_data.full_name, url))

    if is_enabled(SOURCE_TRACKING):
        try:
            source = await SourceService(postgres_session_factory).get(user_data.id)
        except Exception:
            logger.exception(
                "Failed to load user source",
                extra={"telegram_user_id": user_data.id},
            )
        else:
            text += manager.text_message.get("user_started_bot_source").format(
                source=escape(source)
            )

    message = await message.bot.send_message(
        chat_id=manager.config.bot.GROUP_ID,
        text=text,
        message_thread_id=user_data.message_thread_id
    )

    # Pin the message
    await message.pin()


@router.message(F.pinned_message | F.forum_topic_edited | F.forum_topic_closed | F.forum_topic_reopened)
async def handler(message: Message) -> None:
    """
    Delete service messages such as pinned, edited, closed, or reopened forum topics.

    :param message: Message object.
    :return: None
    """
    await message.delete()


@router.message(F.media_group_id, F.from_user[F.is_bot.is_(False)])
@router.message(F.media_group_id.is_(None), F.from_user[F.is_bot.is_(False)])
async def handler(
    message: Message,
    manager: Manager,
    redis: RedisStorage,
    postgres_session_factory: async_sessionmaker[AsyncSession],
    album: Optional[Album] = None,
) -> None:
    """
    Handles user messages and sends them to the respective user.
    If silent mode is enabled for the user, the messages are ignored.

    :param message: Message object.
    :param manager: Manager object.
    :param redis: RedisStorage object.
    :param album: Album object or None.
    :return: None
    """
    user_data = await redis.get_by_message_thread_id(message.message_thread_id)
    if not user_data: return None  # noqa

    if user_data.message_silent_mode:
        # If silent mode is enabled, ignore all messages.
        return

    if not album:
        mention_text = message.text or message.caption
        mention_entities = message.entities or message.caption_entities
    else:
        mention_text, mention_entities = collect_mention_entities(album.messages)

    admin_ids, admin_usernames = await get_group_admin_ids(message.bot, message.chat.id)
    if message_mentions_admin(mention_text, mention_entities, admin_ids, admin_usernames):
        logger.warning(
            "Blocked message forwarding due to admin mention",
            extra={
                "direction": "group_to_private",
                "telegram_user_id": user_data.id,
                "message_thread_id": message.message_thread_id,
                "source_message_id": message.message_id,
                "persistence_status": "blocked",
            },
        )
        try:
            await insert_message_event(
                postgres_session_factory,
                direction="group_to_private",
                telegram_user_id=user_data.id,
                group_chat_id=message.chat.id,
                private_chat_id=user_data.id,
                message_thread_id=message.message_thread_id,
                source_message_id=message.message_id,
                media_group_id=message.media_group_id,
                has_media=bool(message.content_type != "text"),
                status="blocked",
                payload_json={"reason": "admin_mention"},
            )
        except Exception:
            logger.exception(
                "Failed to persist blocked message event",
                extra={
                    "direction": "group_to_private",
                    "telegram_user_id": user_data.id,
                    "message_thread_id": message.message_thread_id,
                    "source_message_id": message.message_id,
                    "persistence_status": "failed",
                },
            )

        msg = await message.reply(manager.text_message.get("message_blocked_admin_mention"))
        await asyncio.sleep(5)
        await msg.delete()
        return

    text = manager.text_message.get("message_sent_to_user")

    try:
        if not album:
            copied_messages = await message.copy_to(chat_id=user_data.id)
        else:
            copied_messages = await album.copy_to(chat_id=user_data.id)

        target_message_id = (
            copied_messages.message_id
            if not album
            else copied_messages[0].message_id
        )
        event_data = {
            "direction": "group_to_private",
            "telegram_user_id": user_data.id,
            "group_chat_id": message.chat.id,
            "private_chat_id": user_data.id,
            "message_thread_id": message.message_thread_id,
            "source_message_id": message.message_id,
            "target_message_id": target_message_id,
            "media_group_id": message.media_group_id,
            "has_media": bool(message.content_type != "text"),
            "payload_json": {"message_id": message.message_id},
        }
        try:
            await insert_message_event(
                postgres_session_factory,
                **event_data,
            )
            logger.info(
                "Persisted message event",
                extra={
                    "direction": "group_to_private",
                    "telegram_user_id": user_data.id,
                    "message_thread_id": message.message_thread_id,
                    "source_message_id": message.message_id,
                    "target_message_id": target_message_id,
                    "persistence_status": "success",
                },
            )
        except Exception:
            logger.exception(
                "Failed to persist message event",
                extra={
                    "direction": "group_to_private",
                    "telegram_user_id": user_data.id,
                    "message_thread_id": message.message_thread_id,
                    "source_message_id": message.message_id,
                    "persistence_status": "failed",
                },
            )
            try:
                queued = await enqueue_sync_event(
                    postgres_session_factory,
                    event_type="message_event",
                    event_key=f"group_to_private:{message.chat.id}:{message.message_id}",
                    payload_json=event_data,
                )
                logger.warning(
                    "Queued failed message event for retry",
                    extra={
                        "direction": "group_to_private",
                        "telegram_user_id": user_data.id,
                        "message_thread_id": message.message_thread_id,
                        "source_message_id": message.message_id,
                        "persistence_status": "queued" if queued else "already_queued",
                    },
                )
            except Exception:
                logger.exception(
                    "Failed to queue message event for retry",
                    extra={
                        "direction": "group_to_private",
                        "telegram_user_id": user_data.id,
                        "message_thread_id": message.message_thread_id,
                        "source_message_id": message.message_id,
                        "persistence_status": "queue_failed",
                    },
                )

    except TelegramAPIError as ex:
        if "blocked" in ex.message:
            text = manager.text_message.get("blocked_by_user")

    except (Exception,):
        text = manager.text_message.get("message_not_sent")

    # Reply to the edited message with the specified text
    msg = await message.reply(text)
    # Wait for 5 seconds before deleting the reply
    await asyncio.sleep(5)
    # Delete the reply to the edited message
    await msg.delete()
