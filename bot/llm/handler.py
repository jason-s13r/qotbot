import logging
import json
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from telethon import TelegramClient, events
from fastmcp import FastMCP

from config import LLM_API_URL, LLM_API_KEY, get_chat_model
from db.models import Chat, User, ClaudeSession
from db.crud import persist_message
from session.prompt import build_session_prompt
from tools.memories import MemoriesProvider


logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You're {BOT_NAMES[0]}, an active participant in a group chat with friends.

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
- NEVER output text directly - ALWAYS call send_messages with your message text
- You MUST call stop_turn when you are done responding
- Your response will ONLY be sent to the chat if you use the send_messages tool
- ALWAYS call send_messages BEFORE calling stop_turn - stop_turn must be the LAST tool call
- If you call stop_turn before send_messages, your messages will NOT be sent
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


class LLMHandler:
    MAX_TOOL_CALLS = 15

    def __init__(
        self,
        client: TelegramClient,
        db_session: AsyncSession,
        chat: Chat,
        claude_session: ClaudeSession,
        tools: FastMCP,
    ):
        self.client = client
        self.db_session = db_session
        self.chat = chat
        self.claude_session = claude_session
        self.user = None
        self.bot_user = None
        self.tools = tools

    async def handle(
        self,
        events: list[events.NewMessage.Event],
        user: User,
        bot_user: User,
        is_continuation: bool = False,
    ):
        """Handle the LLM conversation loop."""
        self.user = user
        self.bot_user = bot_user

        tools = FastMCP("tools", providers=[MemoriesProvider(self.db_session, user)])
        tools.mount(self.tools)

        available_tools = await tools.list_tools()
        tool_schemas = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.parameters,
                },
            }
            for tool in available_tools
        ]

        from sqlalchemy import select
        from db.models import Message as DbMessage

        messages_result = await self.db_session.execute(
            select(DbMessage)
            .where(DbMessage.session_id == self.claude_session.id)
            .order_by(DbMessage.created_at.desc())
            .limit(20)
            .options(selectinload(DbMessage.user))
        )
        recent_db_messages = list(messages_result.scalars().all())

        logger.info(f"Loaded {len(recent_db_messages)} recent messages from database")
        for msg in reversed(recent_db_messages[-5:]):
            logger.debug(f"  DB Message [{msg.id}]: {msg.text[:100]}...")

        prompt = await build_session_prompt(
            self.db_session, self.claude_session, recent_db_messages, is_continuation
        )

        logger.info(f"Built session prompt ({len(prompt)} chars)")
        logger.debug(f"Prompt preview: {prompt[:500]}...")

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": TELEGRAM_FORMATTING},
        ]

        prompt_content = [{"type": "text", "text": prompt}]
        for msg in recent_db_messages:
            if msg.media_base64:
                prompt_content.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{msg.media_base64}"
                        },
                    }
                )
                prompt_content.append(
                    {
                        "type": "text",
                        "text": f"[Previous {msg.media_type} from {msg.user.first_name}]",
                    }
                )

        messages.append({"role": "user", "content": prompt_content})

        logger.info(f"Initialized {len(messages)} message context for LLM")
        for i, msg in enumerate(messages):
            logger.info(
                f"Message[{i}] role={msg['role']}, content={msg['content'][:200]}..."
            )

        client = AsyncOpenAI(base_url=LLM_API_URL, api_key=LLM_API_KEY)
        tool_call_count = 0

        logger.info(f"Starting LLM conversation loop with {len(messages)} messages")
        logger.info(f"System prompt: {SYSTEM_PROMPT[:200]}...")

        while tool_call_count < self.MAX_TOOL_CALLS:
            tool_call_count += 1
            logger.info(
                f"=== LLM iteration {tool_call_count}/{self.MAX_TOOL_CALLS} ==="
            )

            logger.debug(f"Sending request to LLM API: {LLM_API_URL}")
            logger.debug(
                f"Messages context: {len(messages)} messages, {sum(len(m.get('content', '')) for m in messages)} chars total"
            )

            response = await client.chat.completions.create(
                model=get_chat_model(),
                messages=messages,
                tools=tool_schemas,
                tool_choice="auto",
                max_tokens=1024,
            )

            message = response.choices[0].message
            logger.info(
                f"LLM response: finish_reason={response.choices[0].finish_reason}"
            )
            if message.content:
                logger.info(f"LLM thinking: {message.content[:200]}...")
            if message.tool_calls:
                logger.info(f"LLM tool calls: {len(message.tool_calls)} tools")
                for tc in message.tool_calls:
                    logger.info(
                        f"  - {tc.function.name}({tc.function.arguments[:100]}...)"
                    )

            if not response.choices[0].finish_reason == "tool_calls":
                logger.info("LLM finished without tool calls, exiting loop")
                break

            messages.append(
                {
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in message.tool_calls or []
                    ],
                }
            )

            stop_turn_called = False
            for tool_call in message.tool_calls or []:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                tool_id = tool_call.id

                logger.info(f"=== Executing tool: {tool_name} ===")
                logger.info(f"Tool arguments: {json.dumps(tool_args, indent=2)}")

                try:
                    logger.debug(f"Calling tool: {tool_name}")
                    tool_result = await tools.call_tool(tool_name, tool_args)
                    result_content = self._extract_tool_result(tool_result)
                    logger.info(f"Tool {tool_name} completed successfully")
                    logger.debug(
                        f"Tool result: {result_content[:200] if result_content else 'empty'}"
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_id,
                            "content": result_content,
                        }
                    )
                    if tool_name == "stop_turn":
                        logger.info(
                            "stop_turn called, will end LLM loop after all tools complete"
                        )
                        stop_turn_called = True
                except Exception as e:
                    logger.error(f"Error calling tool {tool_name}: {e}", exc_info=True)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_id,
                            "content": f"Error: {e}",
                        }
                    )

            if stop_turn_called:
                logger.info("stop_turn was called, ending LLM loop")
                break

        logger.info("=== LLM conversation loop completed ===")
        logger.info("Committing database changes")
        await self.db_session.commit()
        logger.info("Database changes committed successfully")

        await self.db_session.commit()

    def _extract_tool_result(self, tool_result) -> str:
        """Extract text content from tool result."""
        if hasattr(tool_result, "content"):
            if isinstance(tool_result.content, list):
                return " ".join(
                    item.text if hasattr(item, "text") else str(item)
                    for item in tool_result.content
                )
            elif isinstance(tool_result.content, str):
                return tool_result.content
            else:
                return str(tool_result.content)
        else:
            return str(tool_result)
