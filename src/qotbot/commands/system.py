import logging
from telethon import events
from telethon.tl.functions.channels import LeaveChannelRequest

from qotbot.utils.command import Commands

logger = logging.getLogger(__name__)

system = Commands()


@system.slash("bye", system.Permissions(bot_owner=True, is_scoped=True))
async def handle_bye_event(event: events.NewMessage.Event):
    """Leave the chat."""
    try:
        input_chat = await event.get_input_chat()
        if input_chat:
            logger.info(f"Bot leaving chat_id={event.chat_id}")
            await event.client(LeaveChannelRequest(input_chat))
    except Exception as e:
        logger.error(f"Error leaving chat_id={event.chat_id}: {e}", exc_info=True)
        async with event.client.action(event.chat_id, "typing"):
            await event.respond(f"Error leaving chat: {e}")


@system.slash("disconnect", system.Permissions(bot_owner=True, is_scoped=True))
async def handle_disconnect_event(event: events.NewMessage.Event):
    """Disconnect the bot."""
    await event.client.disconnect()
