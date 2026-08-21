import asyncio
from typing import List, Optional, Sequence, Set, Tuple

from aiogram import Bot
from aiogram.types import MessageEntity
from cachetools import TTLCache

# Telegram admin lists rarely change; a short TTL keeps get_chat_administrators
# calls off the hot path without serving stale data for long.
_CACHE_TTL = 300
_cache: TTLCache = TTLCache(maxsize=8, ttl=_CACHE_TTL)
_lock = asyncio.Lock()

MENTION_ENTITY_TYPES = {"mention", "text_mention"}


async def get_group_admin_ids(bot: Bot, chat_id: int) -> Tuple[Set[int], Set[str]]:
    """
    Get the group's administrator user IDs and usernames, cached for a few minutes.

    The bot itself is excluded, since it is always an admin of the support group
    but is never the intended target of a mention check.

    :param bot: Bot instance.
    :param chat_id: The group chat ID.
    :return: A tuple of (admin user IDs, lowercase usernames without '@').
    """
    cached = _cache.get(chat_id)
    if cached is not None:
        return cached

    async with _lock:
        cached = _cache.get(chat_id)
        if cached is not None:
            return cached

        members = await bot.get_chat_administrators(chat_id)
        admin_ids = {member.user.id for member in members if member.user.id != bot.id}
        admin_usernames = {
            member.user.username.lower()
            for member in members
            if member.user.username and member.user.id != bot.id
        }

        result = (admin_ids, admin_usernames)
        _cache[chat_id] = result
        return result


def message_mentions_admin(
        text: Optional[str],
        entities: Optional[Sequence[MessageEntity]],
        admin_ids: Set[int],
        admin_usernames: Set[str],
) -> bool:
    """
    Check whether any mention in the message text/caption resolves to a group admin.

    Handles both entity kinds Telegram can produce for a mention: "mention" (an
    "@username" substring, resolved by username) and "text_mention" (a mention of a
    user without a username, which carries the target user directly on the entity).

    :param text: The message text or caption the entities apply to.
    :param entities: The message entities or caption entities.
    :param admin_ids: Set of admin Telegram user IDs.
    :param admin_usernames: Set of admin usernames (lowercase, without '@').
    :return: True if a mention resolves to a known admin.
    """
    if not text or not entities:
        return False

    for entity in entities:
        if entity.type == "text_mention" and entity.user and entity.user.id in admin_ids:
            return True
        if entity.type == "mention":
            username = entity.extract_from(text).lstrip("@").lower()
            if username in admin_usernames:
                return True

    return False


def collect_mention_entities(messages: List) -> Tuple[Optional[str], Optional[List[MessageEntity]]]:
    """
    Find the first text/caption and matching entities among a list of messages.

    Used for albums, where the caption and its entities may live on any one of the
    grouped messages depending on which item the sender attached it to.

    :param messages: Messages to search, e.g. the items of an album.
    :return: A (text, entities) pair, or (None, None) if none carry a mention.
    """
    for message in messages:
        text = message.text or message.caption
        entities = message.entities or message.caption_entities
        if text and entities:
            return text, entities
    return None, None
