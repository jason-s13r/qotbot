from collections.abc import Sequence
from typing import Any
from fastmcp.server.providers import Provider
from fastmcp.tools import Tool
from fastmcp.resources import Resource, ResourceTemplate
from sqlalchemy.ext.asyncio import AsyncSession
from db.crud import get_user_memories, save_user_memory
from db.models import User


class MemoriesProvider(Provider):
    """Provides resources and tools related to user memories."""

    def __init__(self, db_session: AsyncSession, user: User):
        super().__init__()
        self.db_session = db_session
        self.user = user

    async def _list_tools(self) -> Sequence[Tool]:
        return [
            Tool.from_function(
                self._save_memory,
                name="save_memory",
                description="Save a persistent memory/fact about a user.",
            ),
            Tool.from_function(
                self._read_memories,
                name="read_memories",
                description="Read all saved memories for a user.",
            ),
        ]

    async def _save_memory(self, content: str) -> str:
        """Save a persistent memory/fact about a user.

        Args:
            content: The memory content to save

        Returns:
            Confirmation message
        """
        await save_user_memory(self.db_session, self.user.id, content)
        return f"Memory saved: {content}"

    async def _read_memories(self) -> str:
        """Read all saved memories for a user.

        Returns:
            Formatted list of memories or message if none exist
        """
        memories = await get_user_memories(self.db_session, self.user.id)
        if not memories:
            return "No memories saved for this user."

        memory_list = "\n".join([f"- {m.content}" for m in memories])
        return f"Memories for this user:\n{memory_list}"
