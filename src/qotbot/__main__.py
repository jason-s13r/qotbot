import asyncio
import logging
import os

from openai import AsyncOpenAI
from telethon import TelegramClient, events
from telethon.tl import types as tl_types

from qotbot.database import (
    init_db,
    get_session,
    store_message_from_event,
    store_message_poll_results,
    create_or_update_bot_user,
    create_or_update_user_from_event,
    create_or_update_chat_from_event,
)
from qotbot.utils.command import Commands
from qotbot.utils.config import (
    DATA_PATH,
    DATABASE_PATH,
    LOGS_DB_PATH,
    LOG_PATH,
    MAX_TRANSCRIPT_DURATION,
)
from qotbot.utils.sqlite_handler import SQLiteHandler
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
from qotbot.commands.summary import summary


API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

LLM_API_URL = os.getenv("LLM_API_URL", "http://localhost:11434")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")

DATA_PATH.mkdir(parents=True, exist_ok=True)
LOG_PATH.mkdir(parents=True, exist_ok=True)
LOGS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s][%(levelname)s][%(name)s:%(lineno)s %(funcName)s()] %(message)s",
    handlers=[
        logging.handlers.TimedRotatingFileHandler(
            LOG_PATH / "log.log", when="H", encoding="utf-8"
        ),
        logging.StreamHandler(),
    ],
)

logging.getLogger('telethon').setLevel(logging.INFO)
logging.getLogger('aiosqlite').setLevel(logging.INFO)
logging.getLogger('httpcore').setLevel(logging.INFO)
logging.getLogger('aiohttp').setLevel(logging.INFO)
logging.getLogger('sqlalchemy').setLevel(logging.WARNING)
logging.getLogger('asyncio').setLevel(logging.INFO)
logging.getLogger('cryptg').setLevel(logging.INFO)
logging.getLogger('fastmcp').setLevel(logging.INFO)
logging.getLogger('openai').setLevel(logging.INFO)
logging.getLogger('ollama').setLevel(logging.INFO)
logging.getLogger('greenlet').setLevel(logging.INFO)
# logging.getLogger('ffmpeg').setLevel(logging.INFO)
# logging.getLogger('faster_whisper').setLevel(logging.INFO)


logger = logging.getLogger(__name__)


async def start():
    loop = asyncio.get_event_loop()
    logger.info("Initialising main database")
    await init_db(DATABASE_PATH)
    logger.info("Initialising logs database")
    await init_db(LOGS_DB_PATH)
    logger.addHandler(SQLiteHandler())

    logger.info("Connecting to Telegram")

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

        await (
            cmd.use(commands)
            .use(system)
            .use(admin)
            .use(rules)
            .use(summary)
            .register(bot)
        )

        async with get_session() as session:
            await create_or_update_bot_user(session, bot)

        logger.info("Registering message event handler")

        @bot.on(events.NewMessage)
        async def handle_incoming_event(event: events.NewMessage.Event):
            if event.raw_text.startswith("/"):
                return

            logger.info(
                f"New message: chat_id={event.chat_id}, message_id={event.id}, sender_id={event.sender_id}"
            )

            async with get_session() as session:
                await create_or_update_chat_from_event(session, event)
                await create_or_update_user_from_event(session, event)
                await store_message_from_event(session, event)
                await session.commit()

            chat_id = event.chat_id
            message_id = event.message.id

            has_image = event.photo is not None or event.sticker is not None
            has_audio = event.audio is not None or event.voice is not None
            has_video = event.video_note is not None or event.video is not None

            if has_audio or has_video:
                if event.file.duration > MAX_TRANSCRIPT_DURATION:
                    logger.warning(
                        f"File duration {event.file.duration}s exceeds max ({MAX_TRANSCRIPT_DURATION}s), skipping transcription for message_id={message_id}"
                    )
                    has_audio = False
                    has_video = False

            if has_audio or has_video:
                try:
                    media_bytes = await event.message.download_media(bytes)
                    if media_bytes:
                        put_audio(chat_id, message_id, media_bytes, ext=event.file.ext)
                        logger.info(f"Audio task queued for message_id={message_id}")
                except Exception as e:
                    logger.error(
                        f"Failed to queue audio for message_id={message_id}: {e}",
                        exc_info=True,
                    )

            if has_image:
                try:
                    image_base64 = await download_media_base64(event.message)
                    put_image(chat_id, message_id, image_base64)
                    logger.info(f"Image task queued for message_id={message_id}")
                except Exception as e:
                    logger.error(
                        f"Failed to queue image for message_id={message_id}: {e}",
                        exc_info=True,
                    )

            if not has_audio and not has_image and not has_video:
                put_classification(chat_id, message_id)
                logger.debug(f"Classification task queued for message_id={message_id}")

        @bot.on(events.Raw)
        async def handle_raw_update(update):
            if not isinstance(update, tl_types.UpdateMessagePoll):
                return

            poll_id = update.poll_id
            poll_data = update.poll.to_dict() if update.poll else None
            results_data = update.results.to_dict() if update.results else None

            async with get_session() as session:
                updated = await store_message_poll_results(
                    session,
                    poll_id=poll_id,
                    poll_data=poll_data,
                    results_data=results_data,
                )
                if updated:
                    await session.commit()

        logger.info("Bot started successfully")
        bot.loop.set_debug(True)

        logger.info("Starting worker tasks")
        asyncio.create_task(image_worker(bot, llmclient))
        asyncio.create_task(audio_worker())
        asyncio.create_task(classification_worker(bot, llmclient))
        asyncio.create_task(response_worker(bot, llmclient))

        await bot.run_until_disconnected()


def main():
    asyncio.run(start())


if __name__ == "__main__":
    main()
