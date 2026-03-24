import logging
from telethon import events
from sqlalchemy.ext.asyncio import AsyncSession

from qotbot.database.models.chat import Chat


logger = logging.getLogger(__name__)


async def create_or_update_chat_from_event(
    session: AsyncSession, event: events.NewMessage.Event
) -> Chat:
    """
    Create or update a Chat record from the event.

    Args:
        session: Database session
        event: Telegram event containing chat info

    Returns:
        The Chat record (new or updated)
    """
    chat_id = event.chat_id

    chat = await session.get(Chat, chat_id)
    if not chat:
        chat_type = (
            "private" if event.is_private else "group" if event.is_group else "channel"
        )
        chat = Chat(
            id=chat_id,
            title=getattr(event.chat, "title", None),
            chat_type=chat_type,
            username=getattr(event.chat, "username", None),
            can_respond=False,
        )
        session.add(chat)
        logger.info(f"Created chat record for chat_id={chat_id}")
    else:
        chat.title = event.chat.title
        chat.username = event.chat.username
        logger.debug(f"Updated chat record for chat_id={chat_id}")

    return chat


async def set_chat_can_respond(
    session: AsyncSession, event: events.NewMessage.Event, can_respond: bool
) -> Chat:
    """
    Create or update a Chat record with the can_respond permission.

    If the chat doesn't exist, creates a new record with can_respond set.
    If the chat exists, updates the can_respond field.

    Args:
        session: Database session
        event: Telegram event containing chat info
        can_respond: Whether the bot can respond in this chat

    Returns:
        The Chat record (new or updated)
    """
    chat_id = event.chat_id

    chat = await session.get(Chat, chat_id)
    if not chat:
        chat_type = (
            "private" if event.is_private else "group" if event.is_group else "channel"
        )
        chat = Chat(
            id=chat_id,
            title=getattr(event.chat, "title", None),
            chat_type=chat_type,
            username=getattr(event.chat, "username", None),
            can_respond=can_respond,
        )
        session.add(chat)
        logger.info(
            f"Created chat record for chat_id={chat_id} with can_respond={can_respond}"
        )
    else:
        chat.can_respond = can_respond
        logger.info(f"Updated chat_id={chat_id} can_respond={can_respond}")

    return chat
