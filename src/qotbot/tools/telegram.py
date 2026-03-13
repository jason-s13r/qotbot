import logging
import random
from collections.abc import Sequence
from typing import Any
from fastmcp.server.providers import Provider
from fastmcp.tools import Tool
from telethon import events
from telethon.tl.types import InputMediaPoll, Poll, PollAnswer, TextWithEntities

from qotbot.database.database import get_session
from qotbot.database.messages import store_message

logger = logging.getLogger(__name__)


class TelegramProvider(Provider):
    """Provides resources and tools related to a telegram event."""

    def __init__(self, event: events.NewMessage.Event, DATABASE_PATH: str):
        super().__init__()
        self.event = event
        self.database_path = DATABASE_PATH

    async def _store_message(self, message):
        with get_session(self.database_path) as session:
            await store_message(session, message)

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
                description="Send a message to a Telegram chat using markdown formatting.",
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
        ]

    async def _get_sender_id(self) -> int | Any | None:
        return self.event.sender_id

    async def _get_chat_id(self) -> int | Any | None:
        return self.event.chat_id

    async def _respond(self, message: str):
        event = self.event
        async with event.client.action(event.chat_id, "typing"):
            response = await event.respond(message)
            await self._store_message(response)
            return "Message sent"

    async def _reply(self, message: str):
        event = self.event
        async with event.client.action(event.chat_id, "typing"):
            reply = await event.reply(message)
            await self._store_message(reply)
            return "Reply sent"

    async def _send_message(self, text: str):
        """Send a message to a Telegram chat using markdown formatting.

        Args:
            text: The message text (markdown format)

        Returns:
            "Message sent" on success
        """
        try:
            async with self.event.client.action(self.event.chat_id, "typing"):
                response = await self.event.respond(text, parse_mode="markdown")
                await self._store_message(response)
                return "Message sent"
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return f"Error: {e}"

    async def _send_messages(self, messages: list[str]):
        """Send multiple messages to a Telegram chat.

        Args:
            messages: List of message texts (markdown format)

        Returns:
            "{len(messages)} messages sent" on success
        """
        for text in messages:
            try:
                async with self.event.client.action(self.event.chat_id, "typing"):
                    response = await self.event.respond(text, parse_mode="markdown")
                    await self._store_message(response)
            except Exception as e:
                logger.error(f"Error sending message: {e}")
        return f"{len(messages)} messages sent"

    async def _send_poll(
        self,
        question: str,
        options: list[str],
        multiple_choice: bool = False,
    ):
        """Send a poll to the Telegram chat.

        Args:
            question: The poll question
            options: List of answer options (2-10 options)
            multiple_choice: Whether users can select multiple answers (default: False)

        Returns:
            "Poll sent" on success
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
            async with self.event.client.action(self.event.chat_id, "typing"):
                response = await self.event.client.send_message(
                    self.event.chat_id, file=InputMediaPoll(poll=poll)
                )
                await self._store_message(response)
                return "Poll sent"
        except Exception as e:
            logger.error(f"Error sending poll: {e}")
            return f"Error: {e}"
