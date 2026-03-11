import asyncio
import json
import logging
import os
from pathlib import Path
from fastmcp import FastMCP
from openai import AsyncOpenAI
from telethon import TelegramClient, events

from qotbot.database import (
    init_db,
    get_session,
    store_message_from_event,
    get_recent_messages,
    get_chat_overall_summary,
    get_sender_name,
    create_or_update_bot_user,
)

from qotbot.database.models.user import User
from qotbot.llm.chatter import Chatter
from qotbot.llm.classifier import Classifier
from qotbot.tools.telegram import TelegramProvider
from qotbot.tools.wolfram_alpha import wolfram_alpha
from qotbot.tools.lolcryption import lolcryption
from qotbot.tools.web_search import web_search


CLIENT_PROFILE = os.getenv("CLIENT_PROFILE", "bot")
BOT_NAME = os.getenv("BOT_NAME", "qotbot")

API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

LLM_API_URL = os.getenv("LLM_API_URL", "http://localhost:11434")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_CHAT_MODEL = os.getenv("LLM_CHAT_MODEL", "qwen3.5:4b")
LLM_CLASSIFIER_MODEL = os.getenv("LLM_CLASSIFIER_MODEL", "qwen3.5:4b")

TELEGRAM_BOT_OWNER = int(os.getenv("TELEGRAM_BOT_OWNER", "0"))

DATA_PATH = Path(os.getenv("DATA_PATH", "./data"))
PROFILE_DATA = DATA_PATH / CLIENT_PROFILE
TELEGRAM_PROFILE = PROFILE_DATA / "telegram"
DATABASE_PATH = PROFILE_DATA / "database.db"

log_file = Path(PROFILE_DATA / "logs" / "log.log")
log_file.parent.mkdir(parents=True, exist_ok=True)


logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s][%(levelname)s][%(name)s:%(lineno)s %(funcName)s()] %(message)s",
    handlers=[
        logging.handlers.TimedRotatingFileHandler(log_file, when="H", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


async def start():
    try:
        init_db(DATABASE_PATH)

        loop = asyncio.get_event_loop()
        bot = TelegramClient(TELEGRAM_PROFILE, API_ID, API_HASH, loop=loop)

        if BOT_TOKEN:
            await bot.start(bot_token=BOT_TOKEN)

        with get_session(DATABASE_PATH) as session:
            await create_or_update_bot_user(session, bot)

        async with bot:

            @bot.on(
                events.NewMessage(pattern=r"(?i)^/bye$", from_users=TELEGRAM_BOT_OWNER)
            )
            async def handle_bye(event: events.NewMessage.Event):
                """Leave the chat."""
                from telethon.tl.functions.channels import LeaveChannelRequest

                try:
                    input_chat = await event.get_input_chat()
                    if input_chat:
                        await bot(LeaveChannelRequest(input_chat))
                except Exception as e:
                    logger.error(f"Error leaving chat: {e}", exc_info=True)
                    await event.respond(f"Error leaving chat: {e}")

            @bot.on(events.NewMessage)
            async def handle_message(event: events.NewMessage.Event):
                logging.info(
                    f"Received new message from {event.sender_id}: {event.raw_text}"
                )

                chat_id = event.chat_id
                recent_messages_text: str = ""
                overall_summary: str = ""
                sender_name: str = ""

                # 1. Extract message media and prepare for use by the LLM.

                with get_session(DATABASE_PATH) as session:
                    recent_messages = get_recent_messages(
                        session, event.chat_id, limit=50
                    )
                    logger.debug(
                        f"Retrieved {len(recent_messages)} recent messages for context"
                    )

                    await store_message_from_event(session, event)
                    overall_summary = get_chat_overall_summary(session, event.chat_id)

                    recent_messages_text = "\n".join(
                        [
                            f"<message sender_id={msg.sender_id} sender_name={get_sender_name(msg.sender)}>{msg.text}</message>"
                            for msg in recent_messages
                        ]
                    )

                    sender_name = get_sender_name(session.get(User, event.sender_id))

                current_messages_text = f"<message sender_id={event.sender_id} sender_name={sender_name}>{event.raw_text}</message>"

                common_prompts = []
                common_prompts.append(
                    {
                        "role": "assistant",
                        "content": f"<chat_summary>\n{overall_summary}\n</chat_summary>",
                    }
                )
                common_prompts.append(
                    {
                        "role": "assistant",
                        "content": f"<chat_history>\n{recent_messages_text}\n</chat_history>",
                    }
                )
                common_prompts.append(
                    {
                        "role": "user",
                        "content": f"<new_messages>\n{current_messages_text}\n</new_messages>",
                    }
                )

                chat_tools = FastMCP(
                    "tools", providers=[TelegramProvider(event, DATABASE_PATH)]
                )
                chat_tools.mount(wolfram_alpha)
                chat_tools.mount(web_search)
                chat_tools.mount(lolcryption)

                classifier_tools = FastMCP("classifier_tools")

                @classifier_tools.tool
                async def approve_message(reason: str):
                    logger.info(f"classification approved: {reason}")

                    chatter = Chatter(
                        AsyncOpenAI(base_url=LLM_API_URL, api_key=LLM_API_KEY),
                        LLM_CHAT_MODEL,
                        BOT_NAME,
                        chat_id,
                    )

                    chat_result = await chatter.invoke(common_prompts, chat_tools)
                    logger.info(f"chat result: {chat_result}")

                    return "APPROVED" if chat_result == "EMPTY" else chat_result

                @classifier_tools.tool
                async def reject_message(reason: str):
                    logger.info(f"classification rejected: {reason}")
                    return "REJECTED"

                classifier = Classifier(
                    AsyncOpenAI(base_url=LLM_API_URL, api_key=LLM_API_KEY),
                    LLM_CLASSIFIER_MODEL,
                    BOT_NAME,
                )

                classification_result = await classifier.invoke(
                    common_prompts, classifier_tools
                )
                logger.info(f"classification_result: {classification_result}")

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
