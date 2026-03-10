#!/usr/bin/env python3

import asyncio
import logging
import os
from pathlib import Path
import sys
from fastmcp import FastMCP
from telethon import TelegramClient, events

from tools.telegram import TelegramProvider
from tools.wolfram_alpha import wolfram_alpha
from tools.lolcryption import lolcryption
from tools.web_search import web_search

# Add bot directory to path for imports when running as script
bot_dir = Path(__file__).parent
if str(bot_dir) not in sys.path:
    sys.path.insert(0, str(bot_dir))

from config import (
    TELEGRAM_API_ID as API_ID,
    TELEGRAM_API_HASH as API_HASH,
    TELEGRAM_BOT_TOKEN as BOT_TOKEN,
    DATA_PATH,
)

CLIENT_PROFILE = os.getenv("TELEGRAM_PROFILE", "bot")
from db.database import init_db
from handlers.message import handle_new_message
from handlers.commands import register_command_handlers

log_file = Path("data/logs/bot.log")
log_file.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s][%(levelname)s][%(name)s:%(lineno)s %(funcName)s()] %(message)s",
    handlers=[logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

logging.getLogger("asyncio").setLevel(logging.ERROR)

telegram_session_file: Path = DATA_PATH / CLIENT_PROFILE


async def main():
    try:
        loop = asyncio.get_event_loop()
        bot = TelegramClient(telegram_session_file, API_ID, API_HASH, loop=loop)

        if CLIENT_PROFILE == "bot" and BOT_TOKEN:
            await bot.start(bot_token=BOT_TOKEN)

        async with bot:
            await init_db()

            register_command_handlers(bot)

            @bot.on(events.NewMessage(incoming=True, pattern=r"^(?!/)"))
            async def on_new_message(event: events.NewMessage.Event):
                logging.info(
                    f"Received new message from {event.sender_id}: {event.raw_text}"
                )
                tools = FastMCP("tools", providers=[TelegramProvider(event)])
                tools.mount(wolfram_alpha)
                tools.mount(web_search)
                tools.mount(lolcryption)

                await handle_new_message(event, tools)

            logger.info("Bot started successfully")
            bot.loop.set_debug(True)
            await bot.run_until_disconnected()

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
