#!/usr/bin/env python3

import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
from fastmcp import FastMCP
from telethon import TelegramClient, events
from telethon.tl.functions.channels import LeaveChannelRequest

from telegram_bot import TelegramLLMBot
from tools.lolcryption import lolcryption
from tools.wolfram_alpha import wolfram_alpha
from tools.simple import simple


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
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3.5:latest")

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

            @bot.on(
                events.NewMessage(
                    incoming=True, pattern=r"(?i)^hey bot", from_users=(JASON)
                )
            )
            async def on_message(event: events.NewMessage.Event):
                mcp = FastMCP("tools")

                @mcp.tool("send_response")
                async def send_response(text: str):
                    """Send a message to a Telegram chat."""
                    await event.respond(text)
                    return ""

                @mcp.tool("send_poll")
                async def send_poll(
                    question: str, options: list[str], multiple_choice: bool = False
                ):
                    """Send a poll to the Telegram chat.

                    Args:
                        question: The poll question
                        options: List of answer options (2-10 options)
                        multiple_choice: Whether users can select multiple answers (default: False)
                    """
                    from telethon.tl.types import InputMediaPoll, Poll, PollAnswer
                    from telethon.tl.types import TextWithEntities
                    import random

                    answers = []
                    for i, opt in enumerate(options):
                        answers.append(
                            PollAnswer(TextWithEntities(opt, []), str(i + 1).encode())
                        )

                    poll = Poll(
                        id=random.randint(1000, 10000),
                        question=TextWithEntities(question, []),
                        answers=answers,
                        public_voters=True,
                        quiz=False,
                        multiple_choice=multiple_choice,
                    )
                    await event.respond(file=InputMediaPoll(poll=poll))
                    return ""

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
                    logger.info(f"Message from {event.sender_id}: {event.raw_text}")

                    await llm.generate_response(event)

            bot.loop.set_debug(True)
            await bot.run_until_disconnected()

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
