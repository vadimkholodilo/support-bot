from typing import Iterable

from aiogram.filters import BaseFilter
from aiogram.types import User

from app.config import Config


def is_dev_user(user_id: int, dev_user_ids: Iterable[int]) -> bool:
    """
    Check whether a user ID belongs to a configured developer.

    :param user_id: The user ID to check.
    :param dev_user_ids: The configured developer user IDs.
    :return: True if the user ID is a developer's.
    """
    return user_id in dev_user_ids


class IsDevUser(BaseFilter):
    """
    Filter that only passes for configured developer users.
    """

    async def __call__(self, _, event_from_user: User, config: Config) -> bool:
        return is_dev_user(event_from_user.id, config.bot.DEV_USER_IDS)
