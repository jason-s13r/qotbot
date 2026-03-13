import asyncio
import logging
import os
from pathlib import Path
from fastmcp import FastMCP
from openai import AsyncOpenAI
from telethon import TelegramClient, events
import tempfile
import os

from qotbot.database import (
    init_db,
    get_session,
    store_message_from_event,
    get_recent_messages,
    get_chat_overall_summary,
    get_sender_name,
    store_image_description,
    store_audio_transcription,
    create_or_update_bot_user,
    set_chat_can_respond,
)

from qotbot.database.messages import get_chat, store_message_classification
from qotbot.database.models.message import Message
from qotbot.database.models.user import User
from qotbot.llm.chatter import Chatter
from qotbot.llm.classifier import Classifier
from qotbot.llm.summariser import Summariser
from qotbot.tools.telegram import TelegramProvider
from qotbot.tools.wolfram_alpha import wolfram_alpha
from qotbot.tools.lolcryption import lolcryption
from qotbot.tools.web_search import web_search
from qotbot.utils.media import download_media_base64
from qotbot.utils.whisper import WhisperService


CLIENT_PROFILE = os.getenv("CLIENT_PROFILE", "bot")
BOT_NAME = os.getenv("BOT_NAME", "qotbot")

API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

LLM_API_URL = os.getenv("LLM_API_URL", "http://localhost:11434")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_CHAT_MODEL = os.getenv("LLM_CHAT_MODEL", "qwen3.5:4b")
LLM_CLASSIFIER_MODEL = os.getenv("LLM_CLASSIFIER_MODEL", "qwen3.5:4b")

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "turbo")
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", None)

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
# logger.setLevel(logging.INFO)

whisper_service: WhisperService | None = None


async def start():
    try:
        logger.info("Initialising database:")
        init_db(DATABASE_PATH)

        logger.info("Connecting to Telegram:")

        loop = asyncio.get_event_loop()
        bot = TelegramClient(TELEGRAM_PROFILE, API_ID, API_HASH, loop=loop)
        llmclient = AsyncOpenAI(base_url=LLM_API_URL, api_key=LLM_API_KEY)

        if BOT_TOKEN:
            await bot.start(bot_token=BOT_TOKEN)

        async with bot:
            with get_session(DATABASE_PATH) as session:
                await create_or_update_bot_user(session, bot)

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
                    async with event.client.action(event.chat_id, "typing"):
                        await event.respond(f"Error leaving chat: {e}")

            @bot.on(
                events.NewMessage(
                    pattern=r"(?i)^/(enable|disable)$", from_users=TELEGRAM_BOT_OWNER
                )
            )
            async def handle_permit_responses(event: events.NewMessage.Event):
                can_respond = event.raw_text.lower() == "/enable"

                with get_session(DATABASE_PATH) as session:
                    chat = await set_chat_can_respond(session, event, can_respond)
                    async with event.client.action(event.chat_id, "typing"):
                        await event.respond(
                            f"Bot responding {'enabled' if chat.can_respond else 'disabled'} for this chat"
                        )

            @bot.on(events.NewMessage(pattern=r"(?i)^/transcript$"))
            async def handle_show_transcript(event: events.NewMessage.Event):
                logger.info(f"/transcript command received from {event.sender_id}")
                if not event.reply_to:
                    logger.info("No reply_to found, ignoring")
                    return

                async with event.client.action(event.chat_id, "typing"):
                    msg_id = event.reply_to.reply_to_msg_id
                    logger.info(
                        f"Looking up message id {msg_id} in chat {event.chat_id}"
                    )

                    with get_session(DATABASE_PATH) as session:
                        message = session.get(Message, (event.chat_id, msg_id))

                        if not message:
                            logger.warning(f"Message {msg_id} not found in database")
                            return

                        if message.audio_transcription:
                            logger.info(
                                f"Sending audio transcription for message {msg_id}"
                            )
                            await event.reply(
                                f"Audio transcription: {message.audio_transcription}"
                            )

                        if message.image_description:
                            logger.info(
                                f"Sending image description for message {msg_id}"
                            )
                            await event.reply(
                                f"Image description: {message.image_description}"
                            )

            @bot.on(events.NewMessage(pattern=r"(?i)^/classification$"))
            async def handle_show_classification(event: events.NewMessage.Event):
                logger.info(f"/classification command received from {event.sender_id}")
                if not event.reply_to:
                    logger.info("No reply_to found, ignoring")
                    return

                async with event.client.action(event.chat_id, "typing"):
                    msg_id = event.reply_to.reply_to_msg_id
                    logger.info(
                        f"Looking up message id {msg_id} in chat {event.chat_id}"
                    )

                    with get_session(DATABASE_PATH) as session:
                        message = session.get(Message, (event.chat_id, msg_id))

                        if not message:
                            logger.warning(f"Message {msg_id} not found in database")
                            return

                        if message.classification_reason:
                            logger.info(
                                f"Sending classification reason for message {msg_id}"
                            )
                            await event.reply(
                                f"Classification reason: {message.classification_reason}"
                            )

            @bot.on(events.NewMessage(pattern=r"(?i)^/summary$"))
            async def handle_generate_summary(event: events.NewMessage.Event):
                async with event.client.action(event.chat_id, "typing"):
                    logger.info(
                        f"/summary command received from {event.sender_id} in chat {event.chat_id}"
                    )
                    bot_user = await bot.get_me()
                    bot_identity = f"{BOT_NAME} ({bot_user.first_name} {bot_user.last_name}, @{bot_user.username})"

                    prior_summary: str = ""
                    transcript: str = ""

                    with get_session(DATABASE_PATH) as session:
                        chat = get_chat(session, event.chat_id)

                        if not chat:
                            logger.warning(
                                f"Chat {event.chat_id} not found in database"
                            )
                            return

                        prior_summary = chat.overall_summary
                        chat_identity = f"{chat.title} ({chat.id})"
                        messages = get_recent_messages(
                            session, event.chat_id, limit=1000
                        )
                        logger.info(
                            f"Retrieved {len(messages)} messages for summary generation"
                        )

                        transcript = "\n".join(
                            [
                                f"<message sender_id={msg.sender_id} sender_name={get_sender_name(msg.sender)}>"
                                f"{msg.text}"
                                f"{f' [Image: {msg.image_description}]' if msg.image_description else ''}"
                                f"{f' [Audio: {msg.audio_transcription}]' if msg.audio_transcription else ''}"
                                f"</message>"
                                for msg in messages
                            ]
                        )
                        logger.info(f"Transcript length: {len(transcript)} characters")

                    summariser = Summariser(
                        llmclient, LLM_CHAT_MODEL, bot_identity, chat_identity
                    )
                    logger.info("Invoking summariser LLM")

                    prompts = [
                        {
                            "role": "user",
                            "content": f"<summary>\n{prior_summary}\n</summary>\n<transcript>{transcript}</transcript>",
                        }
                    ]

                    summary = (
                        await summariser.invoke(prompts, max_completion_tokens=10000)
                        or ""
                    )
                    logger.info(
                        f"Summary generated ({len(summary) if summary else 0} characters)"
                    )

                    with get_session(DATABASE_PATH) as session:
                        chat = get_chat(session, event.chat_id)

                        if not chat:
                            logger.warning(
                                f"Chat {event.chat_id} not found when saving summary"
                            )
                            return

                        chat.overall_summary = summary or ""
                        session.add(chat)
                        logger.info("Summary saved to database")

                    if summary:
                        with tempfile.NamedTemporaryFile(
                            mode="w", suffix=".md", delete=False
                        ) as f:
                            f.write(summary)
                            temp_path = f.name

                        try:
                            express = summary.split("----")[0].strip("#")[:1000]
                            msg = await event.reply(express)
                            async with event.client.action(event.chat_id, "document"):
                                file = await event.client.upload_file(
                                    temp_path, file_name="summary.md"
                                )
                                await msg.reply(file=file)
                        finally:
                            os.unlink(temp_path)

            @bot.on(events.NewMessage)
            async def handle_message(event: events.NewMessage.Event):
                global whisper_service

                if event.raw_text.startswith("/"):
                    return

                logging.info(
                    f"Received new message from {event.sender_id}: {event.raw_text}"
                )

                chat_id = event.chat_id
                recent_messages_text: str = ""
                overall_summary: str = ""
                sender_name: str = ""
                image_base64: str | None = None

                chat_identity: str = f"(chat_id: {event.chat_id})"

                with get_session(DATABASE_PATH) as session:
                    chat = get_chat(session, chat_id)
                    if not chat or not chat.can_respond:
                        await store_message_from_event(session, event)
                        return

                    chat_identity = f"{chat.title} ({chat_id})"

                    recent_messages = get_recent_messages(
                        session, event.chat_id, limit=50
                    )
                    logger.debug(
                        f"Retrieved {len(recent_messages)} recent messages for context"
                    )

                    await store_message_from_event(session, event)
                    session.flush()
                    overall_summary = get_chat_overall_summary(session, event.chat_id)

                    recent_messages_text = "\n".join(
                        [
                            f"<message sender_id={msg.sender_id} sender_name={get_sender_name(msg.sender)}>"
                            f"{msg.text}"
                            f"{f' [Image: {msg.image_description}]' if msg.image_description else ''}"
                            f"{f' [Audio: {msg.audio_transcription}]' if msg.audio_transcription else ''}"
                            f"</message>"
                            for msg in recent_messages
                        ]
                    )

                    sender_name = get_sender_name(session.get(User, event.sender_id))

                transcription: str = ""
                if event.message.audio or event.message.voice:
                    try:
                        if not whisper_service:
                            whisper_service = WhisperService(WHISPER_MODEL)
                        audio_bytes = await event.message.download_media(bytes)
                        if audio_bytes:
                            transcription = await whisper_service.transcribe(
                                audio_bytes, language=WHISPER_LANGUAGE
                            )
                            with get_session(DATABASE_PATH) as session:
                                store_audio_transcription(
                                    session,
                                    event.message.id,
                                    event.chat_id,
                                    transcription,
                                )
                            logger.info(f"Audio transcribed: {transcription[:50]}...")
                    except Exception as e:
                        logger.error(
                            f"Whisper transcription failed: {e}", exc_info=True
                        )

                mime_type, image_base64 = await download_media_base64(event.message)
                has_image = image_base64 is not None

                transcript = f"[Audio: {transcription}]\n" if transcription else ""
                message_text = event.raw_text or event.text or ''
                message_content = f"<new_messages>\n<message sender_id={event.sender_id} sender_name={sender_name}>\n{message_text}\n{transcript}</message>\n</new_messages>"

                if has_image:
                    caption = "(photo without caption)"
                    if event.sticker:
                       caption = "(sticker without caption)"

                    message_text = event.raw_text or event.text or caption
                    message_content = [
                        {
                            "type": "text",
                            "text": f"<new_messages>\n<message sender_id={event.sender_id} sender_name={sender_name}>\n{message_text}\n{transcript}</message>\n</new_messages>",
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_base64}"
                            },
                        },
                    ]

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
                        "content": message_content,
                    }
                )

                bot_user = await bot.get_me()
                bot_identity = f"{BOT_NAME} ({bot_user.first_name} {bot_user.last_name}, @{bot_user.username})"

                chat_tools = FastMCP(
                    "tools", providers=[TelegramProvider(event, DATABASE_PATH)]
                )
                chat_tools.mount(wolfram_alpha)
                chat_tools.mount(web_search)
                chat_tools.mount(lolcryption)

                classifier_tools = FastMCP("classifier_tools")

                @classifier_tools.tool
                async def describe_image(description: str):
                    """Store a description of the image seen in the message."""
                    with get_session(DATABASE_PATH) as session:
                        store_image_description(
                            session, event.message.id, event.chat_id, description
                        )
                    return "Image description stored"

                @classifier_tools.tool
                async def approve_message(reason: str):
                    logger.info(f"classification approved: {reason}")

                    with get_session(DATABASE_PATH) as session:
                        store_message_classification(
                            session,
                            event.message.id,
                            event.chat_id,
                            f"classification approved: {reason}",
                        )                            

                    chatter = Chatter(
                        llmclient,
                        LLM_CHAT_MODEL,
                        bot_identity,
                        chat_identity,
                    )

                    async with event.client.action(event.chat_id, "typing"):
                        chat_result = await chatter.invoke(
                            common_prompts,
                            chat_tools,
                        )
                        logger.info(f"chat result: {chat_result}")

                        if chat_result is None:
                            return "APPROVED"
                        if chat_result == "EMPTY":
                            return "APPROVED"
                        return chat_result

                @classifier_tools.tool
                async def reject_message(reason: str):
                    logger.info(f"classification rejected: {reason}")
                    with get_session(DATABASE_PATH) as session:
                        store_message_classification(
                            session,
                            event.message.id,
                            event.chat_id,
                            f"classification rejected: {reason}",
                        )

                    return "REJECTED"

                classifier = Classifier(
                    llmclient,
                    LLM_CLASSIFIER_MODEL,
                    bot_identity,
                    chat_identity,
                )

                classification_result = await classifier.invoke(
                    common_prompts,
                    classifier_tools,
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
