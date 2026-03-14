from qotbot.database.database import get_session
from qotbot.database.messages import store_image_description
from qotbot.llm.image_describer import ImageDescriber
from qotbot.workers.classification_worker import put_classification
from telethon import TelegramClient
import logging
import asyncio
import time

from qotbot.workers.get_identities import get_identities
from qotbot.workers.PriorityItem import PriorityItem

logger = logging.getLogger(__name__)

image_queue: asyncio.PriorityQueue[PriorityItem] = asyncio.PriorityQueue()


async def put_image(
    chat_id: int,
    message_id: int,
    base64_data: str,
    priority: int = 0,
):
    item = {
        "chat_id": chat_id,
        "message_id": message_id,
        "base64_data": base64_data,
    }
    await image_queue.put(PriorityItem(priority, time.time(), item))
    logger.debug(f"Image queued: chat={chat_id}, msg={message_id}")


async def image_worker(
    database_path: str,
    bot: TelegramClient,
    llmclient,
    model: str,
    bot_name: str,
):
    logger.info("Image worker started")
    while True:
        try:
            priority_item = await asyncio.wait_for(image_queue.get(), timeout=1.0)
        except asyncio.TimeoutError:
            await asyncio.sleep(0.1)
            continue

        item = priority_item.item
        chat_id = item["chat_id"]
        message_id = item["message_id"]
        base64_data = item["base64_data"]

        try:
            logger.info(f"Processing image {message_id} in chat {chat_id}")

            bot_identity, chat_identity = await get_identities(
                bot, chat_id, bot_name, database_path
            )
            image_describer = ImageDescriber(
                llmclient, model, bot_identity, chat_identity
            )

            prompts = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_data}"
                            },
                        }
                    ],
                }
            ]

            description = await image_describer.invoke(prompts)
            if not description:
                description = "No description generated"

            async with get_session(database_path) as session:
                await store_image_description(session, message_id, chat_id, description)
                await session.commit()

            logger.info(f"Image description stored for message {message_id}")

            await put_classification(chat_id, message_id, priority_item.priority)

        except Exception as e:
            logger.error(f"Image worker error: {e}", exc_info=True)
            await put_image(
                chat_id,
                message_id,
                base64_data,
                priority_item.priority + 1,
            )
            logger.info(f"Re-queued image {message_id} with increased priority")
