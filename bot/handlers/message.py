import logging
import re
from fastmcp import FastMCP
from telethon import TelegramClient, events
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import AsyncSessionLocal
from db.models import Chat
from db.crud import (
    get_or_create_user,
    get_or_create_chat,
    persist_message,
    get_active_session,
    create_session,
)
from session.classifier import classify_messages
from llm.handler import LLMHandler
from util.media import download_media_to_base64
from config import (
    TELEGRAM_BOT_OWNER,
    SESSION_TIMEOUT_MINUTES,
    BOT_NAMES,
    RESPONSE_MODE,
    RANDOM_RESPONSE_CHANCE,
)

logger = logging.getLogger(__name__)


def is_bot_mentioned(
    text: str, bot_names: list[str], bot_username: str | None = None
) -> bool:
    """Check if the bot is mentioned by name."""
    # Build patterns from configurable bot names
    names = bot_names.copy()
    if bot_username:
        names.append(bot_username.lower())

    # Remove duplicates
    names = list(set(names))

    # Create regex pattern for all names
    if names:
        pattern = r"(?i)\b(" + "|".join(re.escape(name) for name in names) + r")\b"
        if re.search(pattern, text):
            return True

    return False


def is_reply_to_bot(event: events.NewMessage.Event, bot_id: int) -> bool:
    """Check if the message is a reply to the bot."""
    if event.message.reply_to:
        return event.message.reply_to.reply_to_msg_id is not None
    return False


async def process_message_batch(
    client: TelegramClient,
    db_session: AsyncSession,
    chat: Chat,
    message_events: list[events.NewMessage.Event],
    tools: FastMCP
):
    """Process a batch of messages after debounce."""
    logger.info(
        f"Processing {len(message_events)} messages for chat {chat.telegram_id}"
    )

    if not message_events:
        logger.debug("No messages to process")
        return

    for i, event in enumerate(message_events):
        sender = await event.get_sender()
        logger.info(f"Message[{i}] from {sender.first_name}: {event.raw_text[:100]}...")

    first_event = message_events[0]
    sender = await first_event.get_sender()
    logger.info(f"First message from: {sender.first_name} (ID: {sender.id})")

    user = await get_or_create_user(
        db_session,
        sender.id,
        sender.username,
        sender.first_name or "Unknown",
    )

    # Get bot username from client
    bot_username = None
    try:
        me = await client.get_me()
        bot_username = me.username
    except Exception:
        pass

    has_explicit_trigger = any(
        is_bot_mentioned(e.raw_text, BOT_NAMES, bot_username) for e in message_events
    )
    logger.info(
        f"Explicit trigger found: {has_explicit_trigger} (bot_username={bot_username})"
    )

    # Handle response modes
    if RESPONSE_MODE == "passive" and not has_explicit_trigger:
        logger.info("Passive mode: only responding to explicit triggers")
        await db_session.commit()
        return
    elif RESPONSE_MODE == "random" and not has_explicit_trigger:
        import random

        if random.random() > RANDOM_RESPONSE_CHANCE:
            logger.info(
                f"Random mode: skipping response (chance={RANDOM_RESPONSE_CHANCE})"
            )
            await db_session.commit()
            return

    if not has_explicit_trigger:
        logger.info("Running relevance classifier")

        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from db.models import Message as DbMessage

        recent_messages_result = await db_session.execute(
            select(DbMessage)
            .options(selectinload(DbMessage.user))
            .where(DbMessage.chat_id == chat.id)
            .order_by(DbMessage.created_at.desc())
            .limit(10)
        )
        recent_db_messages = list(recent_messages_result.scalars().all())

        messages_for_classification = []
        for msg in reversed(recent_db_messages):
            media_info = None
            if msg.media_base64:
                media_info = {
                    "type": msg.media_type,
                    "base64": msg.media_base64,
                }
            messages_for_classification.append(
                {
                    "sender": msg.user.first_name if msg.user else "Unknown",
                    "text": msg.text,
                    "timestamp": msg.created_at,
                    "media": media_info,
                    "is_bot": msg.is_bot,
                }
            )

        for e in message_events:
            sender = await e.get_sender()
            media_info = None
            if e.message.media:
                media_result = await download_media_to_base64(client, e.message)
                if media_result:
                    media_type, base64_data = media_result
                    media_info = {
                        "type": media_type,
                        "base64": base64_data,
                    }
            messages_for_classification.append(
                {
                    "sender": sender.first_name or "Unknown",
                    "text": e.raw_text,
                    "timestamp": e.date,
                    "media": media_info,
                    "is_bot": False,
                }
            )

        for msg in messages_for_classification[-len(message_events) :]:
            logger.info(
                f"Classifying message from {msg['sender']}: {msg['text'][:100] if msg['text'] else '[media]'}... (media={msg['media'] is not None})"
            )
        classification = await classify_messages(messages_for_classification)

        if not classification["needs_response"]:
            logger.info(f"Classifier skipped response: {classification['reason']}")
            await db_session.commit()
            return
        else:
            logger.info(f"Classifier approved response: {classification['reason']}")
            from telethon.tl.functions.messages import SetTypingRequest
            from telethon.tl.types import SendMessageTypingAction

            await client(SetTypingRequest(chat.telegram_id, SendMessageTypingAction()))

    first_event = message_events[0]
    sender = await first_event.get_sender()
    user = await get_or_create_user(
        db_session,
        sender.id,
        sender.username,
        sender.first_name or "Unknown",
    )

    active_session = await get_active_session(
        db_session, chat.id, SESSION_TIMEOUT_MINUTES
    )

    is_continuation = False
    if not active_session:
        logger.info("No active session found, creating new session")
        first_event = message_events[0]
        media_result = await download_media_to_base64(client, first_event.message)
        media_type, media_file_id, media_base64 = None, None, None
        if media_result:
            media_type, media_base64 = media_result
            if first_event.message.media and hasattr(
                first_event.message.media, "document"
            ):
                media_file_id = str(first_event.message.media.document.id)
            elif first_event.message.media and hasattr(
                first_event.message.media, "photo"
            ):
                media_file_id = str(first_event.message.media.photo.id)
            else:
                media_file_id = None
        trigger_message = await persist_message(
            db_session,
            chat,
            user,
            first_event.raw_text or "",
            is_bot=False,
            media_type=media_type,
            media_file_id=media_file_id,
            media_base64=media_base64,
        )
        active_session = await create_session(db_session, chat, trigger_message)
        logger.info(f"Created new session {active_session.id}")
    else:
        is_continuation = True
        logger.info(f"Using existing session {active_session.id} (continuation)")

    for event in message_events:
        sender = await event.get_sender()
        msg_user = await get_or_create_user(
            db_session,
            sender.id,
            sender.username,
            sender.first_name or "Unknown",
        )
        media_result = await download_media_to_base64(client, event.message)
        media_type, media_file_id, media_base64 = None, None, None
        if media_result:
            media_type, media_base64 = media_result
            if event.message.media and hasattr(event.message.media, "document"):
                media_file_id = str(event.message.media.document.id)
            elif event.message.media and hasattr(event.message.media, "photo"):
                media_file_id = str(event.message.media.photo.id)
            else:
                media_file_id = None
        await persist_message(
            db_session,
            chat,
            msg_user,
            event.raw_text or "",
            is_bot=False,
            session_ref=active_session,
            media_type=media_type,
            media_file_id=media_file_id,
            media_base64=media_base64,
        )

    await db_session.commit()

    me = await client.get_me()
    bot_user = await get_or_create_user(
        db_session,
        me.id,
        me.username,
        me.first_name or "Bot",
    )

    handler = LLMHandler(client, db_session, chat, active_session, tools)
    await handler.handle(message_events, user, bot_user, is_continuation)

    await db_session.commit()


async def process_message_batch_async(
    chat_id: int,
    client: TelegramClient,
    message_events: list[events.NewMessage.Event],
    tools: FastMCP,
):
    """Process a batch of messages with a new db session."""
    async with AsyncSessionLocal() as db_session:
        try:
            from db.crud import get_chat_by_id

            chat = await get_chat_by_id(db_session, chat_id)
            if not chat:
                logger.error(f"Chat {chat_id} not found")
                return
            await process_message_batch(client, db_session, chat, message_events, tools)
        except Exception as e:
            logger.error(f"Error in process_message_batch_async: {e}", exc_info=True)
            await db_session.rollback()


async def handle_new_message(event: events.NewMessage.Event, tools: FastMCP):
    """Main message handler."""
    async with AsyncSessionLocal() as db_session:
        try:
            from db.crud import get_chat_by_id, get_or_create_user

            sender = await event.get_sender()
            logger.info(
                f"Processing message from {sender.first_name} (ID: {sender.id})"
            )

            user = await get_or_create_user(
                db_session,
                sender.id,
                sender.username,
                sender.first_name or "Unknown",
            )

            chat = await get_or_create_chat(db_session, event.chat_id, event.chat.title)

            me = await event.client.get_me()
            bot_id = me.id

            if RESPONSE_MODE == "mention":
                bot_username = me.username
                if not is_bot_mentioned(event.raw_text, BOT_NAMES, bot_username):
                    logger.debug("Bot not mentioned, ignoring")
                    return

            if RESPONSE_MODE == "random":
                import random

                if random.random() > RANDOM_RESPONSE_CHANCE:
                    logger.debug("Random chance failed, ignoring message")
                    return

            if event.is_reply and is_reply_to_bot(event, bot_id):
                logger.debug("Message is a reply to the bot")

            client = event.client
            chat_id = chat.id
            await process_message_batch_async(chat_id, client, [event], tools)

        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            await db_session.rollback()
