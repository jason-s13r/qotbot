from dataclasses import dataclass

from openai import AsyncOpenAI
from telethon import TelegramClient

from qotbot.database.database import get_session
from qotbot.database.messages import mark_message_skipped
from qotbot.database.models.chat import Chat
from qotbot.database.rules import get_rules_by_specifier
from qotbot.llm.classifier import Classifier
from qotbot.tools.classification_tools import ClassificationProvider
from qotbot.utils.build_common_prompts import build_common_prompts
from qotbot.utils.config import DATABASE_PATH
from qotbot.utils.get_identities import get_identities
from fastmcp import FastMCP

import logging
import asyncio


@dataclass(order=True)
class ClassificationTask:
    chat_id: int
    message_id: int


logger = logging.getLogger(__name__)
classification_queue: asyncio.Queue[ClassificationTask] = asyncio.Queue()


def put_classification(chat_id: int, message_id: int):
    classification_queue.put_nowait(ClassificationTask(chat_id, message_id))
    logger.debug(f"Classification queued: chat={chat_id}, msg={message_id}")


async def _classify_message(
    chat_id: int, message_id: int, bot: TelegramClient, llmclient: AsyncOpenAI
):
    logger.info(f"Classification worker processing: chat={chat_id}, msg={message_id}")
    async with get_session() as session:
        chat = await session.get(Chat, chat_id)
        if not chat:
            logger.info(
                f"Skipping message {message_id} in chat {chat_id} - chat not found"
            )
            await mark_message_skipped(session, chat_id, message_id, "chat not found")
            await session.commit()
            return
        if not chat.can_respond:
            logger.info(
                f"Skipping message {message_id} in chat {chat_id} - responses not allowed"
            )
            await mark_message_skipped(
                session, chat_id, message_id, "responses not allowed in chat."
            )
            await session.commit()
            return

    bot_identity, chat_identity = await get_identities(bot, chat_id)

    async with get_session() as session:
        classifier_rules = await get_rules_by_specifier(session, chat_id, "classifier")
        classifier_rules_text = [rule.text for rule in classifier_rules]

        classifier = Classifier(
            llmclient, bot_identity, chat_identity, classifier_rules_text
        )
    common_prompts = await build_common_prompts(chat_id, [message_id])

    logger.info(f"Creating FastMCP and classification tools")
    classification_tools = FastMCP(
        "classifier",
        providers=[ClassificationProvider(message_id, chat_id)],
    )

    logger.info(f"Invoking classifier")
    classifier_log = await classifier.invoke(common_prompts, classification_tools)
    logger.info(
        f"Classifier result: {classifier_log[:100] if classifier_log else 'None'}"
    )


async def classification_worker(bot, llmclient):
    logger.info("worker started")

    while True:
        try:
            item = await asyncio.wait_for(classification_queue.get(), timeout=1.0)
        except asyncio.TimeoutError:
            await asyncio.sleep(0.1)
            continue

        try:
            await _classify_message(item.chat_id, item.message_id, bot, llmclient)

        except Exception as e:
            logger.error(f"Classification worker error: {e}", exc_info=True)
