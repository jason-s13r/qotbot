import asyncio
import logging
import os
import tempfile

from datetime import datetime, timezone

from openai import AsyncOpenAI
from telethon import TelegramClient, events
from telethon.tl.functions.channels import LeaveChannelRequest

from qotbot.database import (
    init_db,
    get_session,
    store_message_from_event,
    get_recent_messages,
    create_or_update_bot_user,
    create_or_update_user_from_event,
    set_chat_can_respond,
    create_or_update_chat_from_event,
)
from qotbot.database.models.chat import Chat
from qotbot.database.models.message import Message
from qotbot.llm.summariser import Summariser
from qotbot.utils.build_common_prompts import format_messages_for_prompt
from qotbot.utils.config import DATA_PATH, DATABASE_PATH, LOG_PATH, TELEGRAM_BOT_OWNER
from qotbot.utils.get_identities import get_identities
from qotbot.utils.media import download_media_base64
from qotbot.workers.audio_worker import audio_worker, put_audio
from qotbot.workers.classification_worker import (
    classification_worker,
    put_classification,
)
from qotbot.workers.image_worker import image_worker, put_image
from qotbot.workers.response_worker import response_worker


API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

LLM_API_URL = os.getenv("LLM_API_URL", "http://localhost:11434")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")

DATA_PATH.mkdir(parents=True, exist_ok=True)
LOG_PATH.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s][%(levelname)s][%(name)s:%(lineno)s %(funcName)s()] %(message)s",
    handlers=[
        logging.handlers.TimedRotatingFileHandler(LOG_PATH / "log.log", when="H", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


async def start():
    try:
        logger.info("Initialising database:")
        await init_db(DATABASE_PATH)

        logger.info("Connecting to Telegram:")

        loop = asyncio.get_event_loop()
        bot = TelegramClient(DATA_PATH / "telegram", API_ID, API_HASH, loop=loop)
        llmclient = AsyncOpenAI(base_url=LLM_API_URL, api_key=LLM_API_KEY)

        if BOT_TOKEN:
            await bot.start(bot_token=BOT_TOKEN)

        async with bot:
            async with get_session(DATABASE_PATH) as session:
                await create_or_update_bot_user(session, bot)

            @bot.on(
                events.NewMessage(pattern=r"(?i)^/bye$", from_users=TELEGRAM_BOT_OWNER)
            )
            async def handle_bye_event(event: events.NewMessage.Event):
                """Leave the chat."""
                try:
                    input_chat = await event.get_input_chat()
                    if input_chat:
                        await bot(LeaveChannelRequest(input_chat))
                except Exception as e:
                    logger.error(f"Error leaving chat: {e}", exc_info=True)
                    async with event.client.action(event.chat_id, "typing"):
                        await event.respond(f"Error leaving chat: {e}")

            @bot.on(
                events.NewMessage(
                    pattern=r"(?i)^/(enable|disable)$", from_users=TELEGRAM_BOT_OWNER
                )
            )
            async def handle_permit_event(event: events.NewMessage.Event):
                async with get_session(DATABASE_PATH) as session:
                    can_respond = event.raw_text.lower() == "/enable"

                    chat = await set_chat_can_respond(session, event, can_respond)
                    async with event.client.action(event.chat_id, "typing"):
                        await event.respond(
                            f"Bot responding {'enabled' if chat.can_respond else 'disabled'} for this chat"
                        )

            @bot.on(events.NewMessage(pattern=r"(?i)^/transcript$"))
            async def handle_transcript_event(event: events.NewMessage.Event):
                async with get_session(DATABASE_PATH) as session:
                    logger.info(f"/transcript command received from {event.sender_id}")
                    if not event.reply_to:
                        logger.info("No reply_to found, ignoring")
                        return

                    async with event.client.action(event.chat_id, "typing"):
                        msg_id = event.reply_to.reply_to_msg_id
                        logger.info(
                            f"Looking up message id {msg_id} in chat {event.chat_id}"
                        )

                        message = await session.get(Message, (event.chat_id, msg_id))

                        if not message:
                            logger.warning(f"Message {msg_id} not found in database")
                            return

                        if message.audio_transcription:
                            logger.info(
                                f"Sending audio transcription for message {msg_id}"
                            )
                            await event.reply(
                                f"Audio transcription: {message.audio_transcription}"
                            )

                        if message.image_description:
                            logger.info(
                                f"Sending image description for message {msg_id}"
                            )
                            await event.reply(
                                f"Image description: {message.image_description}"
                            )

            @bot.on(events.NewMessage(pattern=r"(?i)^/classification$"))
            async def handle_classification_event(event: events.NewMessage.Event):
                async with get_session(DATABASE_PATH) as session:
                    logger.info(
                        f"/classification command received from {event.sender_id}"
                    )
                    if not event.reply_to:
                        logger.info("No reply_to found, ignoring")
                        return

                    async with event.client.action(event.chat_id, "typing"):
                        msg_id = event.reply_to.reply_to_msg_id
                        logger.info(
                            f"Looking up message id {msg_id} in chat {event.chat_id}"
                        )

                        message = await session.get(Message, (event.chat_id, msg_id))

                        if not message:
                            logger.warning(f"Message {msg_id} not found in database")
                            return

                        if message.classification_reason:
                            logger.info(
                                f"Sending classification reason for message {msg_id}"
                            )
                            await event.reply(message.classification_reason)

            @bot.on(events.NewMessage(pattern=r"(?i)^/summary$"))
            async def handle_summary_event(event: events.NewMessage.Event):
                logger.info(
                    f"/summary command received from {event.sender_id} in chat {event.chat_id}"
                )
                
                bot_identity, chat_identity = await get_identities(bot, event.chat_id)
                prompts = []

                async with get_session(DATABASE_PATH) as session:
                    chat = await session.get(Chat, event.chat_id)

                    if not chat:
                        logger.warning(f"Chat {event.chat_id} not found in database")
                        return

                    prior_summary = chat.overall_summary

                    messages = await get_recent_messages(session, event.chat_id, limit=1000)
                    logger.info(f"Summarising {len(messages)} messages from chat {event.chat_id}")
                    transcript = format_messages_for_prompt(messages)

                    prompts = [
                        {
                            "role": "user",
                            "content": f"<summary>\n{prior_summary}\n</summary>\n<transcript>{transcript}</transcript>",
                        }
                    ]

                summariser_instance = Summariser(llmclient, bot_identity, chat_identity)
                logger.info("Invoking summariser LLM")

                summary: str = ""
                async with event.client.action(event.chat_id, "typing"):
                    summary = await summariser_instance.invoke(
                        prompts, max_completion_tokens=10000
                    )
                    summary = summary or ""

                logger.info(
                    f"Summary generated ({len(summary) if summary else 0} characters)"
                )

                async with get_session(DATABASE_PATH) as session:
                    chat = await session.get(Chat, event.chat_id)

                    if not chat:
                        logger.warning(
                            f"Chat {event.chat_id} not found when saving summary"
                        )
                        return

                    chat.overall_summary = summary or ""
                    session.add(chat)
                    logger.info("Summary saved to database")

                if summary:
                    with tempfile.NamedTemporaryFile(
                        mode="w", suffix=".md", delete=False
                    ) as f:
                        f.write(summary)
                        temp_path = f.name

                    try:
                        express = summary.split("----")[0].strip("#")[:1000]
                        msg = await event.reply(express)
                        async with event.client.action(event.chat_id, "document"):
                            file = await event.client.upload_file(
                                temp_path, file_name="summary.md"
                            )
                            await msg.reply(file=file)
                    finally:
                        os.unlink(temp_path)

            @bot.on(events.NewMessage)
            async def handle_incoming_event(event: events.NewMessage.Event):
                if event.raw_text.startswith("/"):
                    return

                logger.info(
                    f"NEW MESSAGE: chat_id={event.chat_id}, message_id={event.id}, sender_id={event.sender_id}: {event.raw_text}"
                )

                async with get_session(DATABASE_PATH) as session:
                    await create_or_update_chat_from_event(session, event)
                    await create_or_update_user_from_event(session, event)
                    await store_message_from_event(session, event)
                    await session.commit()

                chat_id = event.chat_id
                message_id = event.message.id

                has_image = event.photo is not None or event.sticker is not None
                has_audio = event.audio is not None or event.voice is not None

                message_age_minutes = (
                    datetime.now(timezone.utc) - event.message.date
                ).total_seconds() / 60

                if has_audio:
                    try:
                        audio_bytes = await event.message.download_media(bytes)
                        if audio_bytes:
                            await put_audio(
                                chat_id, message_id, audio_bytes, message_age_minutes
                            )
                            logger.info(f"Audio queued for transcription: {message_id}")
                    except Exception as e:
                        logger.error(f"Audio queue failed: {e}", exc_info=True)

                if has_image:
                    try:
                        image_base64 = await download_media_base64(event.message)
                        await put_image(
                            chat_id, message_id, image_base64, message_age_minutes
                        )
                        logger.info(f"Image queued for description: {message_id}")
                    except Exception as e:
                        logger.error(f"Image queue failed: {e}", exc_info=True)

                if not has_audio and not has_image:
                    await put_classification(chat_id, message_id, message_age_minutes)
                    logger.info(f"Message queued for classification: {message_id}")

            logger.info("Bot started successfully")
            bot.loop.set_debug(True)

            asyncio.create_task(image_worker(bot, llmclient))
            asyncio.create_task(audio_worker())
            asyncio.create_task(classification_worker(bot, llmclient))
            asyncio.create_task(response_worker(bot, llmclient))

            await bot.run_until_disconnected()

    except Exception as e:
        logger.error(e, exc_info=True)
        raise


def main():
    asyncio.run(start())


if __name__ == "__main__":
    main()
