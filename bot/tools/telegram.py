import logging
import random
from collections.abc import Sequence
from typing import Any
from fastmcp.server.providers import Provider
from fastmcp.tools import Tool
from telethon import events
from telethon.tl.types import InputMediaPoll, Poll, PollAnswer, TextWithEntities

logger = logging.getLogger(__name__)


class TelegramProvider(Provider):
    """Provides resources and tools related to a telegram event."""

    def __init__(self, event: events.NewMessage.Event):
        super().__init__()
        self.event = event

    async def _list_tools(self) -> Sequence[Tool]:
        return [
            Tool.from_function(
                self._get_sender_id,
                name="get_sender_id",
                description="Get the sender_id.",
            ),
            Tool.from_function(
                self._get_chat_id, name="get_chat_id", description="Get the chat_id."
            ),
            Tool.from_function(
                self._respond,
                name="respond",
                description="Send a response in the chat.",
            ),
            Tool.from_function(
                self._reply, name="reply", description="Send a reply in the chat."
            ),
            Tool.from_function(
                self._send_message,
                name="send_message",
                description="Send a message to a Telegram chat using MarkdownV2 formatting.",
            ),
            Tool.from_function(
                self._send_messages,
                name="send_messages",
                description="Send multiple messages to a Telegram chat.",
            ),
            Tool.from_function(
                self._send_poll,
                name="send_poll",
                description="Send a poll to the Telegram chat.",
            ),
            Tool.from_function(
                self._stop_turn,
                name="stop_turn",
                description="End the current turn. This tool MUST be called when you are done responding.",
            ),
        ]

    async def _get_sender_id(self) -> int | Any | None:
        return self.event.sender_id

    async def _get_chat_id(self) -> int | Any | None:
        return self.event.chat_id

    async def _respond(self, message: str):
        event = self.event
        await event.respond(message)

    async def _reply(self, message: str):
        event = self.event
        await event.reply(message)

    async def _send_message(self, text: str):
        """Send a message to a Telegram chat using markdown formatting.

        Args:
            text: The message text (markdown format)

        Returns:
            Empty string on success
        """
        try:
            await self.event.respond(text, parse_mode="markdown")
            return ""
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return f"Error: {e}"

    async def _send_messages(self, messages: list[str]):
        """Send multiple messages to a Telegram chat.

        Args:
            messages: List of message texts (markdown format)

        Returns:
            Empty string on success
        """
        for text in messages:
            try:
                await self.event.respond(text, parse_mode="markdown")
            except Exception as e:
                logger.error(f"Error sending message: {e}")
        return ""

    async def _send_poll(
        self,
        question: str,
        options: list[str],
        chat_id: int,
        multiple_choice: bool = False,
    ):
        """Send a poll to the Telegram chat.

        Args:
            question: The poll question
            options: List of answer options (2-10 options)
            chat_id: The Telegram chat ID to send to
            multiple_choice: Whether users can select multiple answers (default: False)

        Returns:
            Empty string on success
        """
        try:
            answers = []
            for i, opt in enumerate(options):
                answers.append(
                    PollAnswer(TextWithEntities(opt, []), str(i + 1).encode())
                )

            poll = Poll(
                id=random.randint(1000, 10000),
                question=TextWithEntities(question, []),
                answers=answers,
                public_voters=True,
                quiz=False,
                multiple_choice=multiple_choice,
            )
            await self.event.respond(file=InputMediaPoll(poll=poll))
            return ""
        except Exception as e:
            logger.error(f"Error sending poll: {e}")
            return f"Error: {e}"

    async def _stop_turn(self, chat_id: int):
        """End the current turn. This tool MUST be called when you are done responding.

        Args:
            chat_id: The Telegram chat ID

        Returns:
            Empty string
        """
        return ""


# bot = TelegramClient("bot", "api_id", "api_hash")
# @bot.on(events.NewMessage(incoming=True, pattern=r"^(?!/)"))
# async def on_new_message(event: events.NewMessage.Event):
#     mcp = FastMCP("tools", providers=[TelegramProvider(event)])
