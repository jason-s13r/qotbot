#!/usr/bin/env python3

import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
from fastmcp import Client
from telegram_bot import TelegramLLMBot
from telethon import TelegramClient, events
from telethon.tl.functions.channels import LeaveChannelRequest

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
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3")

DATA_PATH = Path(os.getenv("DATA_PATH", "./data"))


telegram_session_file: Path = DATA_PATH / CLIENT_PROFILE


async def main():
    try:
        mcpConfig = None
        with open(DATA_PATH / "mcp.json", "r") as file:
            mcpConfig = json.load(file)
            print(f"mcpConfig={mcpConfig}")
        remote_tools = Client(mcpConfig)

        mcp = CombinedTools(simple, lolcryption, wolfram_alpha, remote_tools)

        loop = asyncio.get_event_loop()
        bot = TelegramClient(telegram_session_file, API_ID, API_HASH, loop=loop)
        
        if CLIENT_PROFILE == "bot" and BOT_TOKEN:
            await bot.start(bot_token=BOT_TOKEN)

        async with bot, mcp:
            llm = TelegramLLMBot(
                client=bot,
                data_path=DATA_PATH,
                mcp=mcp,
                ollama_url=OLLAMA_URL,
                ollama_model=OLLAMA_MODEL,
            )

            @bot.on(
                events.NewMessage(
                    incoming=True, pattern=r"(?i)^/bye", from_users=(JASON)
                )
            )
            async def leave(event: events.NewMessage.Event):
                await bot(LeaveChannelRequest(event.chat_id))

            @bot.on(events.NewMessage(incoming=True, pattern=r"(?i)^Hey bot"))
            async def hey_bot(event: events.NewMessage.Event):
                await llm.get_conversation(event, True)

            @bot.on(events.NewMessage(incoming=True))
            async def on_message(event: events.NewMessage.Event):
                conversation = await llm.get_conversation(event)
                if not conversation:
                    return

                async with event.client.action(event.chat_id, "typing"):
                    reply_id = None
                    thought_file = None
                    text_file = None
                    text = None
                    thought_id = None
                    thought_text = None
                    duration_text = None
                    MAX_TEXT_SIZE = 3072
                    try:
                        text, thought_id, thought_text, duration_text = (
                            await llm.generate_response(conversation, event)
                        )
                        if len(text) > MAX_TEXT_SIZE:
                            reply_id = await event.reply(
                                text[:MAX_TEXT_SIZE]
                                + "\n<truncated>\n\n"
                                + duration_text,
                                parse_mode="markdown",
                            )
                        else:
                            reply_id = await event.reply(
                                text + "\n\n" + duration_text, parse_mode="markdown"
                            )

                        await llm.add_bot_message(conversation, reply_id, text)

                    except Exception as e:
                        logger.error(f"Error: {e}")
                        await event.reply(f"Error: {e}", parse_mode="markdown")

                    try:
                        files = []
                        if thought_text:
                            thought_file = await bot.upload_file(thought_text.encode('utf-8'), file_name="thoughts.txt")
                            files.append(thought_file)

                        if len(text) > MAX_TEXT_SIZE:
                            text_file = await bot.upload_file(
                                text.encode("utf-8"), file_name="response.txt"
                            )
                            files.append(text_file)

                        if thought_id:
                            await bot.delete_messages(event.chat_id, thought_id)

                        if len(files) > 0:
                            await bot.send_message(
                                event.chat,
                                file=files,
                                reply_to=reply_id,
                                parse_mode="markdown",
                            )

                    except Exception as e:
                        logger.error(f"Error: {e}")

            bot.loop.set_debug(True)
            await bot.run_until_disconnected()

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
