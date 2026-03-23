from dataclasses import dataclass

from qotbot.database.database import get_session
from qotbot.database.messages import store_image_description
from qotbot.llm.image_describer import ImageDescriber
from qotbot.utils.config import DATABASE_PATH
from qotbot.workers.classification_worker import put_classification
from telethon import TelegramClient
import logging
import asyncio

from qotbot.utils.get_identities import get_identities

logger = logging.getLogger(__name__)


@dataclass(order=True)
class ImageTask:
    chat_id: int
    message_id: int
    image_data: str


image_queue: asyncio.Queue[ImageTask] = asyncio.Queue()


def put_image(
    chat_id: int,
    message_id: int,
    image_data: str,
):
    image_queue.put_nowait(ImageTask(chat_id, message_id, image_data))
    logger.debug(f"Image queued: chat={chat_id}, msg={message_id}")


async def image_worker(bot: TelegramClient, llmclient):
    logger.info("worker started")
    while True:
        try:
            item = await asyncio.wait_for(image_queue.get(), timeout=1.0)
        except asyncio.TimeoutError:
            await asyncio.sleep(0.1)
            continue

        chat_id = item.chat_id
        message_id = item.message_id
        image_data = item.image_data

        try:
            logger.info(f"Processing image {message_id} in chat {chat_id}")

            bot_identity, chat_identity = await get_identities(bot, chat_id)
            image_describer = ImageDescriber(llmclient, bot_identity, chat_identity)

            prompts = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}"
                            },
                        }
                    ],
                }
            ]

            description = await image_describer.invoke(prompts)
            if not description:
                description = "No description generated"

            async with get_session() as session:
                await store_image_description(session, message_id, chat_id, description)
                await session.commit()

            logger.info(f"Image description stored for message {message_id}")

            put_classification(chat_id, message_id)

        except Exception as e:
            logger.error(f"Image worker error: {e}", exc_info=True)
