import logging
from fastmcp import Client, FastMCP
from anthropic import Anthropic
from telethon import TelegramClient, events
import json
import uuid
from datetime import datetime, timedelta

from util.prompts import DECENSORSHIP_PROMPT, DEFINE_QOT, TELEGRAM_FORMATTING, TPL_PARTNER_PROMPT, TPL_TOOLS_PROMPT
from models.conversation import Conversation
from conversation_manager import ConversationManager
from models.chat_message import ChatMessage

logger = logging.getLogger(__name__)


class TelegramLLMBot:
    """Main bot class using Telethon"""

    MAX_TOOL_CALLS = 5

    def __init__(self,
                 llm_api_url: str = "http://localhost:11434",
                 llm_api_key: str = "",
                 llm_model: str = "qwen3.5:0.8b", 
                 llm_max_tokens: int = 1024,
                 mcp: FastMCP = None):

        self.llm_api_url = llm_api_url
        self.llm_api_key = llm_api_key
        self.llm_model = llm_model
        self.llm_max_tokens = llm_max_tokens
        self.mcp = mcp

    async def generate_response(self, event: events.NewMessage.Event) -> str:
        """Generate response using ollama-python with MCP tools"""
        messages = []
        available_tools = await self.mcp.list_tools()
        tools = ', '.join(tool.name for tool in available_tools)
        logging.info(f"Available tools: {tools}")

        latest = {"name": "Jean", "chat_id": event.chat_id}

        messages.append({"role": "system", "content": DECENSORSHIP_PROMPT})
        messages.append({"role": "system", "content": TPL_TOOLS_PROMPT.safe_substitute({"tools":tools})})
        messages.append({"role": "system", "content": TPL_PARTNER_PROMPT.safe_substitute(latest)})
        messages.append({"role": "system", "content": TELEGRAM_FORMATTING})
        messages.append({"role": "system", "content": DEFINE_QOT})
        messages.append({"role": "user", "content": event.raw_text})

        schemas = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.parameters
                }
            }
            for tool in available_tools
        ]
        print(schemas)
        try:
            client = Anthropic(
                base_url=self.llm_api_url, 
                api_key=self.llm_api_key
            )


            response = client.messages.create(
                max_tokens=self.llm_max_tokens,
                model=self.llm_model,
                messages=messages,
                tools=schemas,
                thinking=False,
            )
            print(response)
            logging.info(f"content: {response}")

        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
            return f"Error: {e}"

    