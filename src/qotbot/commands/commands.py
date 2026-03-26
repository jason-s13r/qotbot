import logging
from telethon import events

from qotbot.database.database import get_session
from qotbot.database.models.message import Message
from qotbot.utils.command import Commands

logger = logging.getLogger(__name__)

commands = Commands()


@commands.slash("transcript")
async def handle_transcript_event(event: events.NewMessage.Event):
    """Show the transcript of a message."""
    async with get_session() as session:
        logger.debug(f"/transcript command invoked by user_id={event.sender_id}")
        if not event.reply_to:
            logger.debug("No reply_to found, ignoring /transcript command")
            return

        async with event.client.action(event.chat_id, "typing"):
            msg_id = event.reply_to.reply_to_msg_id
            logger.debug(f"Looking up message_id={msg_id} in chat_id={event.chat_id}")

            message = await session.get(Message, (event.chat_id, msg_id))

            if not message:
                logger.warning(
                    f"Message {msg_id} not found in database for /transcript"
                )
                return

            if message.audio_transcription:
                logger.info(f"Sending audio transcription for message_id={msg_id}")
                await event.reply(f"Audio transcription: {message.audio_transcription}")

            if message.image_description:
                logger.info(f"Sending image description for message_id={msg_id}")
                await event.reply(f"Image description: {message.image_description}")


@commands.slash("classification")
async def handle_classification_event(event: events.NewMessage.Event):
    """Show the classification reason of a message."""
    async with get_session() as session:
        logger.debug(f"/classification command invoked by user_id={event.sender_id}")
        if not event.reply_to:
            logger.debug("No reply_to found, ignoring /classification command")
            return

        async with event.client.action(event.chat_id, "typing"):
            msg_id = event.reply_to.reply_to_msg_id
            logger.debug(f"Looking up message_id={msg_id} in chat_id={event.chat_id}")

            message = await session.get(Message, (event.chat_id, msg_id))

            if not message:
                logger.warning(
                    f"Message {msg_id} not found in database for /classification"
                )
                return

            if message.classification_reason:
                logger.info(f"Sending classification reason for message_id={msg_id}")
                await event.reply(message.classification_reason)
