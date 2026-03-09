import logging
from fastmcp import FastMCP
from openai import OpenAI
from telethon import events
import json

from util.prompts import (
    MAIN_PROMPT,
    DEFINE_QOT,
    TELEGRAM_FORMATTING,
    TPL_PARTNER_PROMPT,
    TPL_TOOLS_PROMPT,
)

logger = logging.getLogger(__name__)


class TelegramLLMBot:
    """Main bot class using Telethon"""

    MAX_TOOL_CALLS = 15
    MAX_HISTORY_MESSAGES = 20

    def __init__(
        self,
        llm_api_url: str = "http://localhost:11434",
        llm_api_key: str = "",
        llm_model: str = "qwen3.5:latest",
        llm_max_tokens: int = 1024,
        mcp: FastMCP = None,
    ):
        self.llm_api_url = llm_api_url
        self.llm_api_key = llm_api_key
        self.llm_model = llm_model
        self.llm_max_tokens = llm_max_tokens
        self.mcp = mcp
        self.message_history = {}

    def _add_message_to_history(self, chat_id: int, sender_name: str, text: str):
        if chat_id not in self.message_history:
            self.message_history[chat_id] = []
        self.message_history[chat_id].append(f"{sender_name}: {text}")
        if len(self.message_history[chat_id]) > self.MAX_HISTORY_MESSAGES:
            self.message_history[chat_id].pop(0)

    async def generate_response(self, event: events.NewMessage.Event) -> str:
        """Generate response using ollama-python with MCP tools"""
        messages = []
        available_tools = await self.mcp.list_tools()
        tools = ", ".join(tool.name for tool in available_tools)
        logger.info(f"Tools: {tools}")

        sender = await event.get_sender()
        sender_name = sender.first_name if sender else "Unknown"
        chat_id = event.chat_id
        logger.info(f"Message from {sender_name} (chat: {chat_id}): {event.raw_text}")

        history_messages = self.message_history.get(int(chat_id), []).copy()

        self._add_message_to_history(int(chat_id), sender_name, event.raw_text)

        messages.append({"role": "system", "content": MAIN_PROMPT})
        messages.append(
            {
                "role": "system",
                "content": TPL_TOOLS_PROMPT.safe_substitute({"tools": tools}),
            }
        )
        messages.append(
            {
                "role": "system",
                "content": TPL_PARTNER_PROMPT.safe_substitute(
                    {"name": sender_name, "chat_id": chat_id}
                ),
            }
        )
        messages.append({"role": "system", "content": TELEGRAM_FORMATTING})
        messages.append({"role": "system", "content": DEFINE_QOT})

        if history_messages:
            messages.append(
                {
                    "role": "system",
                    "content": "Recent chat history:\n" + "\n".join(history_messages),
                }
            )

        messages.append({"role": "user", "content": f"{sender_name}: {event.raw_text}"})

        schemas = [
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

        try:
            client = OpenAI(base_url=self.llm_api_url, api_key=self.llm_api_key)

            response = client.chat.completions.create(
                model=self.llm_model,
                messages=messages,
                tools=schemas,
                tool_choice="auto",
                max_tokens=self.llm_max_tokens,
            )
            content = response.choices[0].message.content
            logger.info(f"LLM response: {content[:200] if content else '(empty)'}")

            if response is None:
                logger.error("LLM returned None response")
                return "Error: LLM did not return a response"

            if not response.choices or not response.choices[0].message:
                logger.warning("LLM returned empty content")
                return ""

            tool_call_count = 0
            while (
                response.choices[0].finish_reason == "tool_calls"
                and tool_call_count < self.MAX_TOOL_CALLS
            ):
                tool_call_count += 1
                message = response.choices[0].message
                tool_calls = message.tool_calls or []

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
                            for tc in tool_calls
                        ],
                    }
                )

                for tool_call in tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    tool_id = tool_call.id

                    logger.info(f"Tool call: {tool_name}({tool_args})")

                    try:
                        tool_result = await self.mcp.call_tool(tool_name, tool_args)
                        if hasattr(tool_result, "content"):
                            if isinstance(tool_result.content, list):
                                result_content = " ".join(
                                    item.text if hasattr(item, "text") else str(item)
                                    for item in tool_result.content
                                )
                            elif isinstance(tool_result.content, str):
                                result_content = tool_result.content
                            else:
                                result_content = str(tool_result.content)
                        else:
                            result_content = str(tool_result)
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_id,
                                "content": result_content,
                            }
                        )
                    except Exception as e:
                        logger.error(f"Error calling tool {tool_name}: {e}")
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_id,
                                "content": f"Error: {e}",
                            }
                        )

                response = client.chat.completions.create(
                    model=self.llm_model,
                    messages=messages,
                    tools=schemas,
                    tool_choice="auto",
                    max_tokens=self.llm_max_tokens,
                )
                logger.info(f"Tool response received")

            return response.choices[0].message.content or ""

        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
            return f"Error: {e}"
