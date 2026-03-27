import logging
from telethon import events

from qotbot.database.database import get_session
from qotbot.database.models.message import Message
from qotbot.utils.command import Commands

logger = logging.getLogger(__name__)

commands = Commands()


def _build_internal_message_link(chat_id: int, message_id: int) -> str | None:
    """Build an internal Telegram message link for supergroups/channels."""
    chat = str(chat_id)
    if not chat.startswith("-100"):
        return None
    cid = chat[4:]
    return f"https://t.me/c/{cid}/{message_id}"


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

                if len(message.audio_transcription) < 1000:
                    await event.reply(
                        f"Audio transcription: {message.audio_transcription}"
                    )
                else:
                    transcript = message.audio_transcription.encode("utf-8")
                    file = await event.client.upload_file(
                        transcript, file_name="audio_transcript.txt"
                    )
                    await event.reply(file=file)

            if message.image_description:
                logger.info(f"Sending image description for message_id={msg_id}")
                if len(message.image_description) < 1000:
                    await event.reply(f"Image description: {message.image_description}")
                else:
                    transcript = message.image_description.encode("utf-8")
                    file = await event.client.upload_file(
                        transcript, file_name="image_description.txt"
                    )
                    await event.reply(file=file)


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


@commands.slash("info", permissions=Commands.Permissions(must_reply=True))
async def handle_info_event(event: events.NewMessage.Event):
    """Show stored info for a bot message."""
    async with get_session() as session:
        logger.debug(f"/info command invoked by user_id={event.sender_id}")

        reply = await event.get_reply_message()
        if not reply:
            logger.debug("No replied message found, ignoring /info command")
            return

        msg_id = reply.id
        logger.debug(f"Looking up message_id={msg_id} in chat_id={event.chat_id}")

        message = await session.get(Message, (event.chat_id, msg_id))
        if not message:
            logger.warning(f"Message {msg_id} not found in database for /info")
            await event.reply("I could not find stored info for that message yet.")
            return

        lines = [
            "**Message info**",
            # f"- message_id: `{message.id}`",
            # f"- chat_id: `{message.chat_id}`",
            # f"- sender_id: `{message.sender_id}`",
            # f"- message_date: `{message.message_date.isoformat()}`",
            # f"- created_at: `{message.created_at.isoformat()}`",
            # f"- text_length: `{len(message.text) if message.text else 0}`",
            # f"- is_reply: `{message.is_reply}`",
            # f"- reply_to_message_id: `{message.reply_to_message_id}`",
            # f"- has_image: `{message.has_image}`",
            # f"- has_audio: `{message.has_audio}`",
            # f"- image_transcribed: `{message.image_transcribed}`",
            # f"- audio_transcribed: `{message.audio_transcribed}`",
            # f"- queue_status: `{message.queue_status}`",
            # f"- processed: `{message.processed}`",
            # f"- responded: `{message.responded}`",
        ]

        message_link = _build_internal_message_link(message.chat_id, message.id)
        if message_link:
            lines.append(f"- message_link: [open]({message_link})")

        if message.trace_message_id is not None:
            lines.append(f"- trace_message_id: `{message.trace_message_id}`")
            trace_link = _build_internal_message_link(
                message.chat_id, message.trace_message_id
            )
            if trace_link:
                lines.append(f"- trace_link: [trace]({trace_link})")
        else:
            lines.append("- trace_message_id: `None`")

        await event.reply("\n".join(lines), parse_mode="markdown")
