import logging
import os
from openai import AsyncOpenAI
from telethon import events

from qotbot.database.database import get_session
from qotbot.database.messages import get_recent_messages
from qotbot.database.models.chat import Chat
from qotbot.database.models.message import Message
from qotbot.llm.summariser import Summariser
from qotbot.utils.get_identities import get_identities
from qotbot.utils.build_common_prompts import format_messages_for_prompt
from qotbot.utils.command import Commands
from qotbot.utils.config import DATABASE_PATH

logger = logging.getLogger(__name__)

LLM_API_URL = os.getenv("LLM_API_URL", "http://localhost:11434")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
llmclient = AsyncOpenAI(base_url=LLM_API_URL, api_key=LLM_API_KEY)

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


@commands.slash("summary")
async def handle_summary_event(event: events.NewMessage.Event, payload: str):
    """Show the summary of the chat."""
    logger.info(
        f"/summary command invoked by user_id={event.sender_id} in chat_id={event.chat_id}"
    )

    bot_identity, chat_identity = await get_identities(event.client, event.chat_id)
    prompts = []

    async with get_session() as session:
        chat = await session.get(Chat, event.chat_id)

        if not chat:
            logger.warning(f"Chat {event.chat_id} not found in database for /summary")
            return

        prior_summary = chat.overall_summary

        input_number = payload.strip()
        limit = int(input_number) if input_number.isdigit() else 1000

        messages = await get_recent_messages(session, event.chat_id, limit=limit)
        logger.info(
            f"Retrieved {len(messages)} messages from chat_id={event.chat_id} for summarisation"
        )
        transcript = format_messages_for_prompt(messages)

        prompts = [
            {
                "role": "user",
                "content": f"<summary>\n{prior_summary}\n</summary>\n<transcript>{transcript}</transcript>",
            }
        ]

    summariser_instance = Summariser(llmclient, bot_identity, chat_identity)
    logger.info(f"Invoking summariser LLM for chat_id={event.chat_id}")

    summary: str = ""
    async with event.client.action(event.chat_id, "typing"):
        summary = await summariser_instance.invoke(prompts, max_completion_tokens=10000)
        summary = summary or ""

    logger.info(
        f"Summary generated for chat_id={event.chat_id} ({len(summary) if summary else 0} characters)"
    )

    async with get_session() as session:
        chat = await session.get(Chat, event.chat_id)

        if not chat:
            logger.warning(f"Chat {event.chat_id} not found when saving summary")
            return

        chat.overall_summary = summary or ""
        session.add(chat)
        logger.info(f"Summary saved to database for chat_id={event.chat_id}")

    if not summary:
        return

    express = summary.split("----")[0].strip("#")[:1000]
    msg = await event.reply(express)
    async with event.client.action(event.chat_id, "document"):
        file = await event.client.upload_file(
            summary.encode("utf-8"), file_name="summary.md"
        )
        await msg.reply(file=file)
