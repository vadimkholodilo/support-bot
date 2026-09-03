from contextlib import suppress

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.manager import Manager
from app.bot.utils.dev import IsDevUser
from app.bot.utils.redis import RedisStorage
from app.bot.utils.welcome import WelcomeService

router = Router()
router.message.filter(F.chat.type == "private")


class WelcomeSG(StatesGroup):
    """FSM states for the developer-only ``/welcome`` flow."""

    capturing = State()


def _service(
        redis: RedisStorage,
        postgres_session_factory: async_sessionmaker[AsyncSession],
) -> WelcomeService:
    return WelcomeService(redis, postgres_session_factory)


@router.message(Command("welcome"), IsDevUser())
async def start_welcome_capture(
        message: Message,
        manager: Manager,
        redis: RedisStorage,
        postgres_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Enter capture mode and preview the current welcome message."""
    await manager.state.set_state(WelcomeSG.capturing)
    await message.answer(manager.text_message.get("welcome_prompt"))

    stored = await _service(redis, postgres_session_factory).get()
    if stored is not None:
        with suppress(TelegramBadRequest):
            await message.bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=stored.source_chat_id,
                message_id=stored.source_message_id,
            )


@router.message(Command("cancel"), IsDevUser(), StateFilter(WelcomeSG.capturing))
async def cancel_welcome_capture(message: Message, manager: Manager) -> None:
    """Leave capture mode without changing the welcome message."""
    await manager.state.set_state(None)
    await message.answer(manager.text_message.get("welcome_cancelled"))


@router.message(Command("reset"), IsDevUser(), StateFilter(WelcomeSG.capturing))
async def reset_welcome_message(
        message: Message,
        manager: Manager,
        redis: RedisStorage,
        postgres_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Drop the custom welcome message and revert to the default text."""
    await _service(redis, postgres_session_factory).reset()
    await manager.state.set_state(None)
    await message.answer(manager.text_message.get("welcome_reset"))


@router.message(StateFilter(WelcomeSG.capturing), IsDevUser())
async def capture_welcome_message(
        message: Message,
        manager: Manager,
        redis: RedisStorage,
        postgres_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Store the developer's next message as the new welcome message."""
    await _service(redis, postgres_session_factory).set(
        source_chat_id=message.chat.id,
        source_message_id=message.message_id,
        content_type=message.content_type,
        updated_by=message.from_user.id,
    )
    await manager.state.set_state(None)
    await message.answer(manager.text_message.get("welcome_saved"))
