from telethon import TelegramClient

from qotbot.database.database import get_session
from qotbot.utils.config import (
    MAX_BATCH_SIZE,
    RESPONSE_WAIT_TIME,
)
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
from qotbot.utils.build_common_prompts import build_common_prompts
from qotbot.utils.get_identities import get_identities
from fastmcp.server.transforms import ResourcesAsTools
from openai import AsyncOpenAI

from fastmcp import FastMCP

import logging
import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select


logger = logging.getLogger(__name__)


async def response_worker(bot: TelegramClient, llmclient: AsyncOpenAI):
    logger.info("Response worker started")

    previous_chat_id = None

    while True:
        start_time = datetime.now()
        try:
            # logger.debug(f"Fetching next chat_id for response (previous_chat_id={previous_chat_id})")
            chat_id = await _fetch_batch_chat_id(previous_chat_id)
            if chat_id is None:
                chat_id = await _fetch_batch_chat_id(None)

            if chat_id is None:
                # logger.debug("No chat_id found for response, waiting")
                previous_chat_id = None
                await asyncio.sleep(2)
                continue

            logger.info(f"Selected chat_id={chat_id} for response generation")
            await _create_response_for_chat(chat_id, bot, llmclient)
            previous_chat_id = chat_id

        except Exception as e:
            logger.error(
                f"Response worker error: chat_id={chat_id}, error={e}", exc_info=True
            )

        await asyncio.sleep(2)

        elapsed_time = (datetime.now() - start_time).total_seconds()
        wait_time = max(0, RESPONSE_WAIT_TIME - elapsed_time)

        logger.debug(f"Response worker cycle complete, sleeping for {wait_time}s")
        await asyncio.sleep(wait_time)


async def _fetch_batch_chat_id(previous_chat_id: int | None) -> int | None:
    fifteen_minutes_ago = datetime.now(timezone.utc) - timedelta(minutes=15)
    async with get_session() as session:
        result = await session.execute(
            select(Message.chat_id)
            .join(Chat, Chat.id == Message.chat_id)
            .filter(
                Message.responded == False,
                Message.is_approved == True,
                Message.message_date >= fifteen_minutes_ago,
                Message.chat_id != previous_chat_id,
                Chat.can_respond == True,
            )
            .order_by(Message.message_date.asc())
        )
        chat_id = result.scalars().first()

        return chat_id


async def _fetch_batch_messages_ids(chat_id: int) -> list[int] | None:
    fifteen_minutes_ago = datetime.now(timezone.utc) - timedelta(minutes=15)
    async with get_session() as session:
        chat = await session.get(Chat, chat_id)
        if not chat:
            logger.warning(f"Chat {chat_id} not found, skipping response")
            return None
        if not chat.can_respond:
            logger.info(f"Chat {chat_id} has can_respond=False, skipping")
            return None

        result = await session.execute(
            select(Message.id)
            .join(Chat, Chat.id == Message.chat_id)
            .filter(
                Message.chat_id == chat_id,
                Message.responded == False,
                Message.is_approved == True,
                Message.message_date >= fifteen_minutes_ago,
                Chat.can_respond == True,
            )
            .order_by(Message.message_date.asc())
            .limit(MAX_BATCH_SIZE)
        )
        message_ids = result.scalars().all()
        return message_ids


async def _create_response_for_chat(
    chat_id: int, bot: TelegramClient, llmclient: AsyncOpenAI
):
    message_ids = await _fetch_batch_messages_ids(chat_id)

    if not message_ids:
        logger.debug(f"No candidate messages found in chat {chat_id}")
        return

    logger.info(
        f"Found {len(message_ids)} approved messages for response in chat {chat_id}"
    )

    bot_identity, chat_identity = await get_identities(bot, chat_id)

    async with get_session() as session:
        chatter_rules = await get_rules_by_specifier(session, chat_id, "chatter")
        chatter_rules_text = [rule.text for rule in chatter_rules]

        chatter = Chatter(llmclient, bot_identity, chat_identity, chatter_rules_text)

    common_prompts = await build_common_prompts(chat_id, message_ids)

    logger.debug(f"Building context prompts for chat {chat_id}")
    logger.debug(f"Prompt context: {common_prompts[-1]['content'][:200]}...")

    telegram_provider = TelegramProvider(bot, chat_id)
    chat_tools = FastMCP("tools", providers=[telegram_provider])
    chat_tools.mount(log_tools)
    chat_tools.mount(web_tools)
    chat_tools.mount(lolcryption)
    chat_tools.mount(date_tool)
    chat_tools.mount(todo_tools)
    chat_tools.add_transform(ResourcesAsTools(chat_tools))

    logger.info(f"Invoking Chatter for chat {chat_id}, messages {message_ids}")
    chatter_logs = await chatter.invoke(common_prompts, chat_tools)

    logger.debug(
        f"Chatter completed, logs: {chatter_logs[:100] if chatter_logs else 'None'}"
    )

    async with get_session() as session:
        for msg_id in message_ids:
            await mark_message_responded(session, chat_id, msg_id)
        await session.commit()

    logger.info(f"Marked messages {message_ids} in chat {chat_id} as responded")
