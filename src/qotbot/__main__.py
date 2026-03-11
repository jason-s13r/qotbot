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
)

from qotbot.llm.client import invoke_llm
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

CLASSIFIER_PROMPT = f"""You are a relevance classifier for a group chat AI assistant.
Determine if the AI should respond to the recent messages.

Respond with a JSON object in the following format:
{{"needs_response": true/false, "reason": "brief explanation"}}

TOOL USAGE (CRITICAL):
- You MUST use the invoke_response tool when a response is needed.

Consider:
- The AI is named {BOT_NAME} and is an active participant in the chat.
- Is the AI being addressed directly?
- Is there a question directed at the AI?
- Is the AI's input valuable to this conversation?
- Or is this a side conversation the AI should skip?
- If images/stickers are included, analyze their content for relevance
- Consider the conversation context and flow
- The AI should not respond to every message, only when it has something valuable to contribute
"""


CHAT_SYSTEM_PROMPT = f"""You're {BOT_NAME}, an active participant in a group chat with friends.

CRITICAL: Messages in <chat_history> have ALREADY been seen and addressed by you.
Do NOT re-respond to, repeat, or re-address anything in chat history.
ONLY respond to the messages in <new_messages>.

- Keep it chill and conversational, matching the energy of the chat
- Be genuinely helpful when they need info, but don't be overly formal
- TEXT LIKE A HUMAN: Send multiple rapid-fire messages naturally
- BREAK thoughts into natural message chunks instead of one long response
- Do not mention that you are an AI
- Do not ask follow up questions unless REALLY needed

TOOL USAGE (CRITICAL):
- You MUST use the send_messages tool to send ALL messages to the chat
- Your response will ONLY be sent to the chat if you use the send_messages tool
- When you are finished, respond with DONE.
"""

TELEGRAM_FORMATTING = """
You are a participant in a Telegram chat group that outputs messages using MarkdownV2 formatting.
All responses must follow Telegram MarkdownV2 rules exactly.
Key rules:

1. **Bold** - use **text**
2. __Italics__ - use __text__
3. ~~Strikethrough~~ - use ~~text~~
4. `Inline monospace` - use `text`
5. Code blocks - use ```language\\ncode\\n```
6. [Inline links](URL) - use [text](url)
7. ||spoiler|| - use ||text||
8. > quotes - use > text

Rules for generating messages:
- Do not use # headings, telegram does not support this.
- Write naturally - do NOT add backslash escapes, the system handles escaping automatically.
- For code blocks, use triple backticks with optional language specifier.
- Ensure links are properly formatted as [text](URL) with valid URL.
- Do not output any HTML or unsupported Markdown.

Your goal: produce messages that, when sent in Telegram using MarkdownV2, display exactly as intended.
"""

async def start():
    try:
        init_db(DATABASE_PATH)

        loop = asyncio.get_event_loop()
        bot = TelegramClient(TELEGRAM_PROFILE, API_ID, API_HASH, loop=loop)

        if BOT_TOKEN:
            await bot.start(bot_token=BOT_TOKEN)

        async with bot:

            @bot.on(events.NewMessage)
            async def on_new_message(event: events.NewMessage.Event):
                logging.info(
                    f"Received new message from {event.sender_id}: {event.raw_text}"
                )

                recent_messages_text: str = ""
                overall_summary: str = ""

                with get_session(DATABASE_PATH) as session:
                    recent_messages = get_recent_messages(
                        session, event.chat_id, limit=50
                    )
                    logger.debug(
                        f"Retrieved {len(recent_messages)} recent messages for context"
                    )

                    await store_message_from_event(session, event)
                    overall_summary = get_chat_overall_summary(session, event.chat_id)

                    recent_messages_text = "\n".join([f"<message sender_id={msg.sender_id} sender_name=>{msg.text}</message>: " for msg in recent_messages])

                current_messages_text = "\n".join([f"<message sender_id={msg.sender_id} sender_name=>{msg.raw_text}</message>" for msg in [event]])

                common_prompts = []
                common_prompts.append({"role":"system", "content": f"<chat description>\n{overall_summary}\n</chat description>"})
                common_prompts.append({"role":"system", "content": f"<chat history>\n{recent_messages_text}\n</chat history>"})
                common_prompts.append({"role":"user", "content": f"<new messages>\n{current_messages_text}\n</new messages>"})

                # 3  Extract message media and prepare for use by the LLM.

                classifier_tools = FastMCP("classifier_tools")
                chat_tools = FastMCP("tools", providers=[TelegramProvider(event)])
                chat_tools.mount(wolfram_alpha)
                chat_tools.mount(web_search)
                chat_tools.mount(lolcryption)                

                @classifier_tools.tool
                async def invoke_response(classification_decision: str):
                    logger.info(f"classification decision: {classification_decision}")

                    chat = AsyncOpenAI(base_url=LLM_API_URL, api_key=LLM_API_KEY)
                    chat_prompts = []
                    chat_prompts.append({"role": "system", "content": CHAT_SYSTEM_PROMPT})
                    chat_prompts.append({"role": "system", "content": TELEGRAM_FORMATTING})
                    
                    chat_prompts.extend(common_prompts)
                    classifier_prompts.append({"role":"system", "content": f"<classification decision>\n{classification_decision}\n</classification decision>"})
                    classifier_prompts.extend(common_prompts)
                    
                    chat_result = await invoke_llm(chat, LLM_CHAT_MODEL, chat_prompts, chat_tools)
                    logger.info(f"chat result: {chat_result}")

                    return "ok"

                classifier = AsyncOpenAI(base_url=LLM_API_URL, api_key=LLM_API_KEY)
                classifier_prompts = []

                classifier_prompts.append({"role":"system", "content": CLASSIFIER_PROMPT})
                classifier_prompts.extend(common_prompts)
                classification_result = await invoke_llm(classifier, LLM_CLASSIFIER_MODEL, classifier_prompts, classifier_tools)
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
