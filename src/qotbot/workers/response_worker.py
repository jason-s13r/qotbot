from dataclasses import dataclass

from openai import AsyncOpenAI
from telethon import TelegramClient

from qotbot.database.database import get_session
from qotbot.database.messages import mark_message_responded
from qotbot.database.models.chat import Chat
from qotbot.database.models.message import Message
from qotbot.database.rules import get_rules_by_specifier
from qotbot.llm.chatter import Chatter
from qotbot.tools.date_tools import date_tool
from qotbot.tools.lolcryption import lolcryption
from qotbot.tools.logs_tools import log_tools
from qotbot.tools.todo_tools import todo_tools
from qotbot.tools.telegram import TelegramProvider
from qotbot.tools.web_tools import web_tools
from qotbot.tools.woolworths import woolworths_tools
from qotbot.utils.build_common_prompts import build_common_prompts
from qotbot.utils.get_identities import get_identities
from fastmcp.server.transforms import ResourcesAsTools
from fastmcp import FastMCP

import logging
import asyncio


@dataclass(order=True)
class ResponseTask:
    chat_id: int
    message_id: int


logger = logging.getLogger(__name__)
response_queue: asyncio.Queue[ResponseTask] = asyncio.Queue()


def put_response(chat_id: int, message_id: int):
    response_queue.put_nowait(ResponseTask(chat_id, message_id))
    logger.debug(f"Response task queued: chat_id={chat_id}, message_id={message_id}")


async def _process_response(
    chat_id: int, message_id: int, bot: TelegramClient, llmclient: AsyncOpenAI
):
    logger.debug(f"Processing response for chat_id={chat_id}, message_id={message_id}")
    async with get_session() as session:
        chat = await session.get(Chat, chat_id)
        if not chat:
            logger.warning(
                f"Chat {chat_id} not found, skipping response for message {message_id}"
            )
            return
        if not chat.can_respond:
            logger.info(
                f"Chat {chat_id} has can_respond=False, skipping response for message {message_id}"
            )
            return

    bot_identity, chat_identity = await get_identities(bot, chat_id)

    async with get_session() as session:
        chatter_rules = await get_rules_by_specifier(session, chat_id, "chatter")
        chatter_rules_text = [rule.text for rule in chatter_rules]

        chatter = Chatter(llmclient, bot_identity, chat_identity, chatter_rules_text)

    common_prompts = await build_common_prompts(chat_id, [message_id])

    logger.debug(f"Building context prompts for chat {chat_id}")
    logger.debug(f"Prompt context: {common_prompts[-1]['content'][:200]}...")

    telegram_provider = TelegramProvider(bot, chat_id, message_id)
    chat_tools = FastMCP("tools", providers=[telegram_provider])
    chat_tools.mount(log_tools)
    chat_tools.mount(web_tools)
    chat_tools.mount(lolcryption)
    chat_tools.mount(date_tool)
    chat_tools.mount(todo_tools)
    chat_tools.mount(woolworths_tools)
    chat_tools.add_transform(ResourcesAsTools(chat_tools))

    logger.info(f"Invoking Chatter for chat {chat_id}, message {message_id}")
    # tool_call_limits={"send_message": 3},
    chatter_logs = await chatter.invoke(
        common_prompts,
        chat_tools,
    )

    logger.debug(
        f"Chatter completed, logs: {chatter_logs[:100] if chatter_logs else 'None'}"
    )

    async with get_session() as session:
        await mark_message_responded(session, chat_id, message_id)
        await session.commit()

    logger.info(f"Marked message {message_id} in chat {chat_id} as responded")


async def response_worker(bot: TelegramClient, llmclient: AsyncOpenAI):
    logger.info("Response worker started")

    while True:
        try:
            item = await asyncio.wait_for(response_queue.get(), timeout=1.0)
            logger.debug(
                f"Dequeued response task: chat_id={item.chat_id}, message_id={item.message_id}"
            )

            await _process_response(item.chat_id, item.message_id, bot, llmclient)

        except asyncio.TimeoutError:
            await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Response worker error: {e}", exc_info=True)
