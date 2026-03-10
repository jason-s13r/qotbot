import asyncio
import logging
import os
from pathlib import Path
from fastmcp import FastMCP
from telethon import TelegramClient, events

from qotbot.database import init_db, get_session, store_message_from_event
from qotbot.tools.telegram import TelegramProvider
from qotbot.tools.wolfram_alpha import wolfram_alpha
from qotbot.tools.lolcryption import lolcryption
from qotbot.tools.web_search import web_search


CLIENT_PROFILE = os.getenv("CLIENT_PROFILE", "bot")

API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

LLM_API_URL = os.getenv("LLM_API_URL", "http://localhost:11434")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_CHAT_MODEL = os.getenv("LLM_CHAT_MODEL", "qwen3.5:4b")
LLM_CLASSIFIER_MODEL = os.getenv("LLM_CLASSIFIER_MODEL", "qwen3.5:4b")

DATA_PATH = Path(os.getenv("DATA_PATH", "./data"))
PROFILE_DATA = DATA_PATH / CLIENT_PROFILE
TELEGRAM_PROFILE = PROFILE_DATA / "telegram"
DATABASE_PATH = PROFILE_DATA / "database.db"

log_file = Path(PROFILE_DATA / "logs" / "log.log")
log_file.parent.mkdir(parents=True, exist_ok=True)


logging.basicConfig(
    level=logging.ERROR,
    format="[%(asctime)s][%(levelname)s][%(name)s:%(lineno)s %(funcName)s()] %(message)s",
    handlers=[
        logging.handlers.TimedRotatingFileHandler(log_file, when="H", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def start():
    try:
        init_db(DATABASE_PATH)

        loop = asyncio.get_event_loop()
        bot = TelegramClient(TELEGRAM_PROFILE, API_ID, API_HASH, loop=loop)

        if BOT_TOKEN:
            await bot.start(bot_token=BOT_TOKEN)

        async with bot:

            @bot.on(events.NewMessage)
            async def on_new_message(event: events.NewMessage.Event):
                logging.debug(
                    f"Received new message from {event.sender_id}: {event.raw_text}"
                )

                # 1. Retrieve last 50 messages from the database for context
                
                with get_session(DATABASE_PATH) as session:
                    await store_message_from_event(session, event)


                # 3  Extract message media and prepare for use by the LLM.
                # 4. Invoke classifier llm to decide if message needs a response
                #   - Provided a system prompt instructing the classifier of their purpose.
                #   - If available, provided a summary of the chat as overall context about the chat.
                #   - Provided the last 50 messages as recent messages context.
                #   - Is provide with latest message as the target for classification.
                # 5. If so, invoke chat participant llm to give a response:
                #   - Provided a system prompt instructing the chat participant of their purpose and how to behave.
                #   - Is provided with the classification decision.
                #   - If available, provided a summary of the chat as overall context about the chat.
                #   - Provided the last 50 messages as recent messages context.
                #   - Is provided with latest message as the target for a response.
                #   - Is given tools access so that it can respond using tool calls.

                chat_tools = FastMCP("tools", providers=[TelegramProvider(event)])
                chat_tools.mount(wolfram_alpha)
                chat_tools.mount(web_search)
                chat_tools.mount(lolcryption)

                # await handle_new_message(event, tools)

            logger.info("Bot started successfully")
            bot.loop.set_debug(True)
            await bot.run_until_disconnected()

    except Exception as e:
        logger.error(e, exc_info=True)
        raise


def main():
    asyncio.run(start())


if __name__ == "__main__":
    main()
