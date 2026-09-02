from __future__ import annotations

import logging

from environs import Env, EnvError
from openfeature import api
from openfeature.evaluation_context import EvaluationContext
from openfeature.flag_evaluation import FlagResolutionDetails, Reason
from openfeature.provider import Metadata
from openfeature.provider.no_op_provider import NoOpProvider

logger = logging.getLogger(__name__)

# Prefix for the environment variables that back feature flags.
ENV_PREFIX = "BOT_FF_"

# Feature flag keys. Keep in sync with the environment variables documented in
# ``.env.example`` and the README.
SOURCE_TRACKING = "source-tracking"

# Every known flag and its default when the backing env var is absent. Used to
# log the resolved flag state on startup.
KNOWN_FLAGS: dict[str, bool] = {
    SOURCE_TRACKING: False,
}


def _env_name(flag_key: str) -> str:
    return ENV_PREFIX + flag_key.upper().replace("-", "_")


class EnvVarProvider(NoOpProvider):
    """OpenFeature provider that resolves flags from environment variables.

    ``source-tracking`` is read from ``BOT_FF_SOURCE_TRACKING``. Values are read
    through an :class:`environs.Env` (the same mechanism as ``app.config``) so a
    ``.env`` file is honoured as well as the real process environment. Missing or
    unparsable values fall back to the caller-provided default.
    """

    def __init__(self, env: Env) -> None:
        super().__init__()
        self._env = env

    def get_metadata(self) -> Metadata:
        return Metadata(name="EnvVarProvider")

    def resolve_boolean_details(
            self,
            flag_key: str,
            default_value: bool,
            evaluation_context: EvaluationContext | None = None,
    ) -> FlagResolutionDetails[bool]:
        env_name = _env_name(flag_key)
        try:
            value = self._env.bool(env_name, None)
        except EnvError:
            return FlagResolutionDetails(value=default_value, reason=Reason.ERROR)
        if value is None:
            return FlagResolutionDetails(value=default_value, reason=Reason.DEFAULT)
        return FlagResolutionDetails(value=value, reason=Reason.STATIC)

    def resolve_string_details(
            self,
            flag_key: str,
            default_value: str,
            evaluation_context: EvaluationContext | None = None,
    ) -> FlagResolutionDetails[str]:
        value = self._env.str(_env_name(flag_key), None)
        if value is None:
            return FlagResolutionDetails(value=default_value, reason=Reason.DEFAULT)
        return FlagResolutionDetails(value=value, reason=Reason.STATIC)


def setup_feature_flags() -> None:
    """Register the environment-variable feature-flag provider. Call once at startup."""
    env = Env()
    env.read_env()
    api.set_provider_and_wait(EnvVarProvider(env))
    log_feature_flags()


def log_feature_flags() -> None:
    """Log the resolved state of every known feature flag."""
    for flag_key, default in KNOWN_FLAGS.items():
        enabled = is_enabled(flag_key, default=default)
        logger.info(
            "Feature flag %s = %s (env %s, default=%s)",
            flag_key,
            "enabled" if enabled else "disabled",
            _env_name(flag_key),
            default,
        )


def is_enabled(flag_key: str, *, default: bool = False) -> bool:
    """Return whether the given feature flag is enabled."""
    return api.get_client().get_boolean_value(flag_key, default)
