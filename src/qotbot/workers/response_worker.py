import os

from qotbot.database.database import get_session
from qotbot.database.messages import mark_message_responded
from qotbot.database.models.chat import Chat
from qotbot.database.models.message import Message
from qotbot.llm.chatter import Chatter
from qotbot.tools.date_tools import date_tool
from qotbot.tools.lolcryption import lolcryption
from qotbot.tools.telegram import TelegramProvider
from qotbot.tools.web_tools import web_tools
from qotbot.workers.build_common_prompts import build_common_prompts
from qotbot.workers.get_identities import get_identities

from fastmcp import FastMCP

import logging
import asyncio
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from qotbot.workers.PriorityItem import PriorityItem

logger = logging.getLogger(__name__)

response_queue: asyncio.PriorityQueue[PriorityItem] = asyncio.PriorityQueue()

MAX_BATCH_SIZE = os.getenv("MAX_BATCH_SIZE", 5)


async def put_response(
    chat_id: int,
    message_id: int,
    priority: int = 0,
):
    item = {
        "chat_id": chat_id,
        "message_id": message_id,
    }
    await response_queue.put(PriorityItem(priority, time.time(), item))
    logger.debug(f"Response queued: chat={chat_id}, msg={message_id}")


async def response_worker(
    database_path: str,
    bot,
    llmclient,
    model: str,
    bot_name: str,
):
    logger.info("Response worker started")

    while True:
        await asyncio.sleep(10)
        try:
            priority_item = await asyncio.wait_for(response_queue.get(), timeout=2.0)
        except asyncio.TimeoutError:
            await asyncio.sleep(1)
            continue

        item = priority_item.item
        chat_id = item["chat_id"]
        message_id = item["message_id"]

        try:
            async with get_session(database_path) as session:
                one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)

                result = await session.execute(
                    select(Message.id)
                    .filter(
                        Message.chat_id == chat_id,
                        Message.responded == False,
                        Message.is_approved == True,
                        Message.message_date >= one_hour_ago,
                    )
                    .order_by(Message.message_date.asc())
                    .limit(MAX_BATCH_SIZE)
                )
                message_ids = result.scalars().all()

                if not message_ids:
                    logger.info(f"No candidate messages found in chat {chat_id}")
                    continue

                logger.info(
                    f"Found {len(message_ids)} messages ready for response in chat {chat_id}"
                )

                chat = await session.get(Chat, chat_id)
                if not chat:
                    logger.info(f"Chat {chat_id} not found")
                    continue
                if not chat.can_respond:
                    logger.info(f"Chat {chat_id} does not allow responses")
                    continue

            bot_identity, chat_identity = await get_identities(
                bot, chat_id, bot_name, database_path
            )
            chatter = Chatter(llmclient, model, bot_identity, chat_identity)

            common_prompts = await build_common_prompts(database_path, chat_id, message_ids)


            telegram_provider = TelegramProvider(bot, chat_id, database_path)
            chat_tools = FastMCP("tools", providers=[telegram_provider])
            chat_tools.mount(web_tools)
            chat_tools.mount(lolcryption)
            chat_tools.mount(date_tool)

            logger.info(common_prompts[-1]["content"])
            logger.info(f"Invoking Chatter for messages {message_ids}")
            chatter_logs = await chatter.invoke(common_prompts, chat_tools)

            logger.info(
                f"Chatter logs: {chatter_logs[:100] if chatter_logs else 'None'}"
            )

            async with get_session(database_path) as session:
                for msg_id in message_ids:
                    await mark_message_responded(session, chat_id, msg_id)
                await session.commit()

            logger.info(f"Marked messages {message_ids} as responded")

        except Exception as e:
            logger.error(f"Response worker error: {e}", exc_info=True)
            await put_response(chat_id, message_id, priority_item.priority + 1)
            logger.info(f"Re-queued response {message_id} with increased priority")