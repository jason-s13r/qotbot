from qotbot.database.database import get_session
from qotbot.database.messages import mark_message_skipped, store_message_classification
from qotbot.database.models.chat import Chat
from qotbot.llm.classifier import Classifier
from qotbot.tools.classification_tools import ClassificationProvider
from qotbot.workers.build_common_prompts import build_common_prompts
from qotbot.workers.get_identities import get_identities
from fastmcp import FastMCP

import logging
import asyncio
import time

from qotbot.workers.PriorityItem import PriorityItem

logger = logging.getLogger(__name__)

classification_queue: asyncio.PriorityQueue[PriorityItem] = asyncio.PriorityQueue()


async def put_classification(
    chat_id: int,
    message_id: int,
    priority: int = 0,
):
    item = {
        "chat_id": chat_id,
        "message_id": message_id,
    }
    await classification_queue.put(PriorityItem(priority, time.time(), item))
    logger.debug(f"Classification queued: chat={chat_id}, msg={message_id}")


async def classification_worker(
    database_path: str,
    bot,
    llmclient,
    model: str,
    bot_name: str,
):
    logger.info("Classification worker started")

    while True:
        try:
            priority_item = await asyncio.wait_for(
                classification_queue.get(), timeout=1.0
            )
        except asyncio.TimeoutError:
            await asyncio.sleep(0.1)
            continue

        logger.info(
            f"Classification worker processing: chat={priority_item.item['chat_id']}, msg={priority_item.item['message_id']}"
        )
        item = priority_item.item
        chat_id = item["chat_id"]
        message_id = item["message_id"]

        try:
            async with get_session(database_path) as session:
                chat = await session.get(Chat, chat_id)
                if not chat:
                    logger.info(
                        f"Skipping message {message_id} in chat {chat_id} - chat not found"
                    )
                    continue
                if not chat.can_respond:
                    logger.info(
                        f"Skipping message {message_id} in chat {chat_id} - responses not allowed"
                    )
                    await mark_message_skipped(
                        session, chat_id, message_id, "responses not allowed in chat."
                    )
                    await session.commit()
                    continue

            bot_identity, chat_identity = await get_identities(
                bot, chat_id, bot_name, database_path
            )
            classifier = Classifier(llmclient, model, bot_identity, chat_identity)
            common_prompts = await build_common_prompts(database_path, chat_id, [message_id])

            logger.info(f"Creating FastMCP and classification tools")
            classification_tools = FastMCP(
                "classifier",
                providers=[ClassificationProvider(message_id, chat_id, database_path)],
            )

            logger.info(f"Invoking classifier")
            classifier_log = await classifier.invoke(common_prompts, classification_tools)
            logger.info(f"Classifier result: {classifier_log[:100] if classifier_log else 'None'}")

        except Exception as e:
            logger.error(f"Classification worker error: {e}", exc_info=True)
            await put_classification(chat_id, message_id, priority_item.priority + 1)
            logger.info(
                f"Re-queued classification {message_id} with increased priority"
            )
