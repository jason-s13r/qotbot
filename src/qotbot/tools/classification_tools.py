import logging
from typing import Sequence

from fastmcp.server.providers import Provider
from fastmcp.tools import Tool

from qotbot.database.database import get_session
from qotbot.database.messages import mark_message_skipped, store_message_classification
from qotbot.utils.config import DATABASE_PATH
from qotbot.workers.response_worker import put_response

logger = logging.getLogger(__name__)


class ClassificationProvider(Provider):
    def __init__(self, message_id: int, chat_id: int):
        super().__init__()
        self.chat_id = chat_id
        self.message_id = message_id

    async def _list_tools(self) -> Sequence[Tool]:
        return [
            Tool.from_function(
                self._approve_message,
                name="approve_message",
                description="Approve the message.",
            ),
            Tool.from_function(
                self._reject_message,
                name="reject_message",
                description="Reject the message.",
            ),
        ]

    async def _approve_message(self, reason: str):
        logger.info(f"classification approved: {reason}")

        async with get_session(DATABASE_PATH) as session:
            await store_message_classification(
                session,
                self.message_id,
                self.chat_id,
                f"classification approved: {reason}",
                is_approved=True
            )
            await session.commit()

        logger.info(
            f"Classification approved for chat={self.chat_id}, msg={self.message_id}: {reason}"
        )

        await put_response(
            self.chat_id,
            self.message_id,
            priority=0,
        )

        return "APPROVED"

    async def _reject_message(self, reason: str):
        logger.info(
            f"Classification rejected for chat={self.chat_id}, msg={self.message_id}: {reason}"
        )
        async with get_session(DATABASE_PATH) as session:
            await store_message_classification(
                session,
                self.message_id,
                self.chat_id,
                f"classification rejected: {reason}",
                is_approved=False
            )

            await mark_message_skipped(session, self.chat_id, self.message_id, reason)
            await session.commit()

        return "REJECTED"
