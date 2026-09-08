from contextlib import suppress
from typing import Any, Dict

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    ForceReply,
    User,
)
from aiogram.types.base import (
    UNSET_DISABLE_WEB_PAGE_PREVIEW,
    UNSET_PARSE_MODE,
)

from app.bot.utils.texts import TextMessage
from app.config import Config

MESSAGE_EDIT_ERRORS = [
    "message can't be edited",
    "message is not modified",
    "message to edit not found",
    # The stored window turned out to be a non-text message; nothing to blank.
    "there is no text in the message to edit",
]
MESSAGE_DELETE_ERRORS = [
    "message can't be deleted",
    "message to delete not found",
]


class Manager:
    """
    Manager class for handling bot-related operations and messaging.
    """

    def __init__(self, emoji: str, data: Dict[str, Any], language_code: str) -> None:
        """
        Initialize the Manager instance.

        :param emoji: The emoji string.
        :param data: Additional data.
        :param language_code: The language code for localization.
        """
        self.bot: Bot = data.get("bot")
        self.state: FSMContext = data.get("state")
        self.user: User = data.get("event_from_user")

        self.config: Config = data.get("config")
        self.text_message = TextMessage(language_code)

        self.__emoji = emoji
        self.__data = data

    @property
    def middleware_data(self) -> Dict[str, Any]:
        """
        Get middleware data.

        :return: Middleware data.
        """
        return self.__data

    async def get_old_message_id(self) -> int:
        """
        Get the old message ID stored in the FSM context.

        :return: The old message ID.
        """
        data = await self.state.get_data()
        return data.get("message_id", -1)

    async def send_message(
            self,
            text: str,
            parse_mode: str | None = UNSET_PARSE_MODE,
            disable_web_page_preview: bool | None = UNSET_DISABLE_WEB_PAGE_PREVIEW,
            disable_notification: bool | None = None,
            reply_markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | ReplyKeyboardRemove | ForceReply | None = None,
            register_window: bool = True,
    ) -> None:
        """
        Send a message using the bot.

        :param text: The text of the message.
        :param parse_mode: The parse mode of the message.
        :param disable_web_page_preview: Disable web page preview.
        :param disable_notification: Disable notification.
        :param reply_markup: The reply markup.
        :param register_window: When ``True`` the sent message becomes the
            replaceable window (the previous one is removed and this id is
            stored). When ``False`` the previous window is still cleared but
            this message is left untouched by later window transitions.

        :return: None.
        """
        message = await self.bot.send_message(
            text=text,
            chat_id=self.user.id,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview,
            disable_notification=disable_notification,
            reply_markup=reply_markup,
        )
        await self.delete_previous_message()
        await self.state.update_data(
            message_id=message.message_id if register_window else None
        )

    async def send_copied_message(
            self,
            from_chat_id: int,
            message_id: int,
            reply_markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | ReplyKeyboardRemove | ForceReply | None = None,
            register_window: bool = True,
    ) -> None:
        """
        Copy an existing message into the current user's chat.

        Mirrors :meth:`send_message` bookkeeping: the previous window message is
        removed and, when ``register_window`` is ``True``, the new message id is
        stored in the FSM context. Pass ``register_window=False`` for content
        that should stay in the chat untouched (e.g. the welcome message).

        :param from_chat_id: Chat that holds the source message.
        :param message_id: Identifier of the source message.
        :param reply_markup: The reply markup.
        :param register_window: Whether the copied message becomes the
            replaceable window.
        :return: None.
        """
        message_id_ = await self.bot.copy_message(
            chat_id=self.user.id,
            from_chat_id=from_chat_id,
            message_id=message_id,
            reply_markup=reply_markup,
        )
        await self.delete_previous_message()
        await self.state.update_data(
            message_id=message_id_.message_id if register_window else None
        )

    @staticmethod
    async def delete_message(message: Message) -> None:
        """
        Delete a message using the bot.

        :param message: The message to be deleted.
        """
        with suppress(TelegramBadRequest):
            await message.delete()

    async def delete_previous_message(self) -> None | Message:
        """
        Delete the previous window message.

        Attempts to delete the message identified by the stored message ID. If deletion is not possible (e.g. the
        message is too old to delete for everyone), it falls back to editing it down to a placeholder __emoji so a
        stale interactive screen is neutralised. Window messages are always sent as text, so the edit fallback always
        applies; content that is not a window (see ``send_message``/``send_copied_message`` ``register_window``) never
        reaches this method.

        :return: The edited Message object or None if no previous message was found.

        :raise TelegramBadRequest: If there is an issue with deleting or editing the previous message.
        """
        message_id = await self.get_old_message_id()
        if not message_id: return  # noqa:E701

        try:
            await self.bot.delete_message(
                message_id=message_id,
                chat_id=self.user.id,
            )
        except TelegramBadRequest as ex:
            if any(e in ex.message for e in MESSAGE_DELETE_ERRORS):
                try:
                    return await self.bot.edit_message_text(
                        message_id=message_id,
                        chat_id=self.user.id,
                        text=self.__emoji,
                    )
                except TelegramBadRequest as ex:
                    if not any(e in ex.message for e in MESSAGE_EDIT_ERRORS):
                        raise ex
