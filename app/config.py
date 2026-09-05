from dataclasses import dataclass
from typing import List, Optional

from environs import Env


@dataclass
class BotConfig:
    """
    Data class representing the configuration for the bot.

    Attributes:
    - TOKEN (str): The bot token.
    - DEV_USER_IDS (List[int]): The developers' user IDs.
    - GROUP_ID (int): The group chat ID.
    - BOT_EMOJI_ID (str): The custom emoji ID for the group's topic.
    - DEFAULT_LANGUAGE_CODE (Optional[str]): When set, language selection is disabled and every
      user is pinned to this language.
    """
    TOKEN: str
    DEV_USER_IDS: List[int]
    GROUP_ID: int
    BOT_EMOJI_ID: str
    DEFAULT_LANGUAGE_CODE: Optional[str]


@dataclass
class RedisConfig:
    """
    Data class representing the configuration for Redis.

    Attributes:
    - HOST (str): The Redis host.
    - PORT (int): The Redis port.
    - DB (int): The Redis database number.
    """
    HOST: str
    PORT: int
    DB: int

    def dsn(self) -> str:
        """
        Generates a Redis connection DSN (Data Source Name) using the provided host, port, and database.

        :return: The generated DSN.
        """
        return f"redis://{self.HOST}:{self.PORT}/{self.DB}"


@dataclass
class PostgresConfig:
    DSN: str


@dataclass
class Config:
    """
    Data class representing the overall configuration for the application.

    Attributes:
    - bot (BotConfig): The bot configuration.
    - redis (RedisConfig): The Redis configuration.
    """
    bot: BotConfig
    redis: RedisConfig
    postgres: PostgresConfig


def load_config() -> Config:
    """
    Load the configuration from environment variables and return a Config object.

    :return: The Config object with loaded configuration.
    """
    # Imported lazily to avoid a circular import: app.bot.utils (imported for
    # SUPPORTED_LANGUAGES) pulls in modules that import Config from this file.
    from app.bot.utils.texts import SUPPORTED_LANGUAGES

    env = Env()
    env.read_env()

    default_language_code = env.str("BOT_DEFAULT_LANGUAGE_CODE", None)
    if default_language_code and default_language_code not in SUPPORTED_LANGUAGES:
        raise ValueError(
            f"BOT_DEFAULT_LANGUAGE_CODE={default_language_code!r} is not one of "
            f"the supported languages: {sorted(SUPPORTED_LANGUAGES.keys())}"
        )

    return Config(
        bot=BotConfig(
            TOKEN=env.str("BOT_TOKEN"),
            DEV_USER_IDS=env.list("BOT_DEV_USER_IDS", subcast=int),
            GROUP_ID=env.int("BOT_GROUP_ID"),
            BOT_EMOJI_ID=env.str("BOT_EMOJI_ID"),
            DEFAULT_LANGUAGE_CODE=default_language_code,
        ),
        redis=RedisConfig(
            HOST=env.str("REDIS_HOST"),
            PORT=env.int("REDIS_PORT"),
            DB=env.int("REDIS_DB"),
        ),
        postgres=PostgresConfig(
            DSN=env.str("POSTGRES_DSN"),
        ),
    )
