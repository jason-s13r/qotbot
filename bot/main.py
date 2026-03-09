#!/usr/bin/env python3

import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
from fastmcp import Client, FastMCP
from telethon import TelegramClient, events
from telethon.tl.functions.channels import LeaveChannelRequest

from telegram_bot import TelegramLLMBot
from tools.lolcryption import lolcryption
from tools.wolfram_alpha import wolfram_alpha
from tools.simple import simple
from util.combined_mcp import CombinedTools



JASON = 172033414


logging.basicConfig(
    format="[%(asctime)s][%(levelname)s][%(name)s:%(lineno)s %(funcName)s()] %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

parser = argparse.ArgumentParser()
parser.add_argument("-p", "--profile", help="Telegram profile name", default="bot")
args = parser.parse_args()

CLIENT_PROFILE = args.profile
API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
LLM_API_URL = os.getenv("LLM_API_URL", "http://localhost:3000")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3.5:0.8b")

DATA_PATH = Path(os.getenv("DATA_PATH", "./data"))


telegram_session_file: Path = DATA_PATH / CLIENT_PROFILE


async def main():
    try:
        loop = asyncio.get_event_loop()
        bot = TelegramClient(telegram_session_file, API_ID, API_HASH, loop=loop)
        
        if CLIENT_PROFILE == "bot" and BOT_TOKEN:
            await bot.start(bot_token=BOT_TOKEN)

        async with bot:
            @bot.on(
                events.NewMessage(
                    incoming=True, pattern=r"(?i)^/bye", from_users=(JASON)
                )
            )
            async def leave(event: events.NewMessage.Event):
                await bot(LeaveChannelRequest(event.chat_id))

            @bot.on(events.NewMessage(incoming=True, pattern=r"(?i)^hey bot", from_users=(JASON)))
            async def on_message(event: events.NewMessage.Event):
                mcp = FastMCP("tools")

                @mcp.tool
                def send_message(chat_id: int, text: str):
                    """Send a message to a Telegram chat."""
                    loop = asyncio.get_event_loop()
                    loop.create_task(bot.send_message(chat_id, text))
                    return f"Message sent to chat_id={chat_id}"

                mcp.mount(simple)
                mcp.mount(lolcryption)
                mcp.mount(wolfram_alpha)

                llm = TelegramLLMBot(
                    mcp=mcp,
                    llm_api_url=LLM_API_URL,
                    llm_api_key=LLM_API_KEY,
                    llm_model=LLM_MODEL,
                )
                async with event.client.action(event.chat_id, "typing"):
                    logger.debug(f"Received message: {event.raw_text} from {event.sender_id}")
                    print(f"Received message: {event.raw_text} from {event.sender_id}")

                    await llm.generate_response(event)


            bot.loop.set_debug(True)
            await bot.run_until_disconnected()

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
