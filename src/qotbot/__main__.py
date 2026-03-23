import asyncio
import logging
import os

from datetime import datetime, timezone

from openai import AsyncOpenAI
from telethon import TelegramClient, events

from qotbot.database import (
    init_db,
    get_session,
    store_message_from_event,
    create_or_update_bot_user,
    create_or_update_user_from_event,
    create_or_update_chat_from_event,
)
from qotbot.utils.command import Commands
from qotbot.utils.config import (
    DATA_PATH,
    DATABASE_PATH,
    LOG_PATH,
    MAX_TRANSCRIPT_DURATION,
)
from qotbot.utils.media import download_media_base64
from qotbot.workers.audio_worker import audio_worker, put_audio
from qotbot.workers.classification_worker import (
    classification_worker,
    put_classification,
)
from qotbot.workers.image_worker import image_worker, put_image
from qotbot.workers.response_worker import response_worker
from qotbot.commands.system import system
from qotbot.commands.admin import admin
from qotbot.commands.commands import commands
from qotbot.commands.rules import rules


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
        logging.handlers.TimedRotatingFileHandler(
            LOG_PATH / "log.log", when="H", encoding="utf-8"
        ),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


async def start():
    logger.info("Initialising database:")
    await init_db(DATABASE_PATH)

    logger.info("Connecting to Telegram:")

    loop = asyncio.get_event_loop()
    bot = TelegramClient(DATA_PATH / "telegram", API_ID, API_HASH, loop=loop)
    llmclient = AsyncOpenAI(base_url=LLM_API_URL, api_key=LLM_API_KEY)

    if BOT_TOKEN:
        await bot.start(bot_token=BOT_TOKEN)

    async with bot:
        cmd = Commands()

        @cmd.slash("help")
        async def handle_help(event: events.NewMessage.Event, payload: str = None):
            """Show this help message."""
            async with event.client.action(event.chat_id, "typing"):
                message = await cmd.build_help_message()
                await event.respond(message)

        await cmd.use(commands).use(system).use(admin).use(rules).register(bot)

        async with get_session(DATABASE_PATH) as session:
            await create_or_update_bot_user(session, bot)

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
            has_video = event.video_note is not None or event.video is not None

            message_age_minutes = (
                datetime.now(timezone.utc) - event.message.date
            ).total_seconds() / 60

            if has_audio or has_video:
                if event.file.duration > MAX_TRANSCRIPT_DURATION:
                    logger.warning(
                        f"File duration {event.file.duration} exceeds max transcript duration, skipping transcription for message {message_id}"
                    )
                    has_audio = False
                    has_video = False

            if has_audio or has_video:
                try:
                    media_bytes = await event.message.download_media(bytes)
                    if media_bytes:
                        put_audio(chat_id, message_id, media_bytes, ext=event.file.ext)
                        logger.info(f"Audio queued for transcription: {message_id}")
                except Exception as e:
                    logger.error(f"Audio queue failed: {e}", exc_info=True)

            if has_image:
                try:
                    image_base64 = await download_media_base64(event.message)
                    put_image(chat_id, message_id, image_base64)
                    logger.info(f"Image queued for description: {message_id}")
                except Exception as e:
                    logger.error(f"Image queue failed: {e}", exc_info=True)

            if not has_audio and not has_image and not has_video:
                put_classification(chat_id, message_id)
                logger.info(f"Message queued for classification: {message_id}")

        logger.info("Bot started successfully")
        bot.loop.set_debug(True)

        asyncio.create_task(image_worker(bot, llmclient))
        asyncio.create_task(audio_worker())
        asyncio.create_task(classification_worker(bot, llmclient))
        asyncio.create_task(response_worker(bot, llmclient))

        await bot.run_until_disconnected()


def main():
    asyncio.run(start())


if __name__ == "__main__":
    main()
