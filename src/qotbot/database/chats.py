import logging
from telethon import events
from sqlalchemy.orm import Session

from qotbot.database.models.chat import Chat


logger = logging.getLogger(__name__)


async def set_chat_can_respond(
    session: Session, event: events.NewMessage.Event, can_respond: bool
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

    chat = session.get(Chat, chat_id)
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
        logger.info(f"Created chat {chat_id} with can_respond={can_respond}")
    else:
        chat.can_respond = can_respond
        logger.info(f"Updated chat {chat_id} can_respond={can_respond}")

    return chat
