from typing import Optional

from app.bot.utils.texts import SUPPORTED_LANGUAGES
from app.config import Config


def resolve_forced_language_code(config: Config) -> Optional[str]:
    """
    Return the language code every user should be pinned to, or ``None`` if
    users are free to pick their own language.

    A language is forced either when the bot is explicitly configured with a
    default language, or when only one language is supported.

    :param config: Config object.
    :return: The forced language code, or None if language selection stays enabled.
    """
    if config.bot.DEFAULT_LANGUAGE_CODE is not None:
        return config.bot.DEFAULT_LANGUAGE_CODE
    if len(SUPPORTED_LANGUAGES) == 1:
        return next(iter(SUPPORTED_LANGUAGES))
    return None


def is_language_selection_enabled(config: Config) -> bool:
    """
    Whether the bot should prompt users to select a language and expose the
    ``/language`` command.

    :param config: Config object.
    :return: True if language selection is enabled.
    """
    return resolve_forced_language_code(config) is None
