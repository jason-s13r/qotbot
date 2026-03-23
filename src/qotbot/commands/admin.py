import logging
from telethon import events

from qotbot.database.chats import set_chat_can_respond
from qotbot.database.database import get_session
from qotbot.utils.command import Commands
from qotbot.utils.config import DATABASE_PATH

logger = logging.getLogger(__name__)

admin = Commands()


@admin.slash("disable", admin.Permissions(chat_admin=True, is_scoped=True))
async def handle_disable(event: events.NewMessage.Event):
    """Disable bot responses in this chat."""
    await _toggle_can_respond(event, False)


@admin.slash("enable", admin.Permissions(chat_admin=True, is_scoped=True))
async def handle_enable(event: events.NewMessage.Event):
    """Enable bot responses in this chat."""
    await _toggle_can_respond(event, True)


async def _toggle_can_respond(event: events.NewMessage.Event, can_respond=True):
    """Enable bot responses in this chat."""
    async with get_session(DATABASE_PATH) as session:
        chat = await set_chat_can_respond(session, event, can_respond)
        async with event.client.action(event.chat_id, "typing"):
            await event.respond(
                f"Bot responding {'enabled' if chat.can_respond else 'disabled'} for this chat"
            )
