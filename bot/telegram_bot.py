import asyncio
import base64
import logging
import mimetypes
from pathlib import Path
import profile
from fastmcp import Client
import ollama
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

    def __init__(self, client: TelegramClient,
                 data_path: Path,
                 ollama_url: str = "http://localhost:11434",
                 ollama_model: str = "qwen3", mcp: Client = None):

        self.conversation_manager = ConversationManager(data_path)
        self.ollama_url = ollama_url
        self.ollama_model = ollama_model

        self.mcp = mcp

        # Create Telethon client
        self.client = client

    async def get_conversation(self, event: events.NewMessage.Event, create_conversation=False):
        message = event.message

        if not message or not message.text:
            return

        chat_id = message.chat_id
        message_id = message.id
        text = message.text

        conversation = None
        conversation_id = None

        # Check if this is a reply to a tracked message
        
        conversation = self.conversation_manager.get_conversation_by_message_id(
            message.reply_to_msg_id or message.id
        )
        if conversation:
            conversation_id = conversation.conversation_id
            logger.info(f"Found existing conversation: {conversation_id}")


        # If not a reply to tracked message, check if should start new conversation
        if not conversation and create_conversation:
            conversation_id = self.conversation_manager.create_conversation(chat_id, message_id)
            conversation = self.conversation_manager.conversations[conversation_id]
            logger.info(f"Created new conversation: {conversation_id}")

        user  = await self.client.get_entity(event.sender_id)
        name = "" if user is None else f"{user.first_name} {user.last_name or ''}".strip()
        user_message = ChatMessage(
            role="user",
            content=text,
            timestamp=datetime.now(),
            telegram_message_id=message_id,
            name=name
        )
        self.conversation_manager.add_message_to_conversation(conversation_id, user_message)

        return conversation

    async def add_bot_message(self, conversation, reply, text):
        message = ChatMessage(
            role="assistant",
            content=text,
            timestamp=datetime.now(),
            telegram_message_id=reply.id,
            name="Bot"
        )
        self.conversation_manager.add_message_to_conversation(conversation.conversation_id, message)

    async def generate_response(self, conversation: Conversation, event: events.NewMessage.Event) -> str:
        """Generate response using ollama-python with MCP tools"""
        bot: TelegramClient = event.client
        messages = []
        available_tools = await self.mcp.list_tools()
        tools = ', '.join(tool.name for tool in available_tools)
        logging.info(f"Available tools: {tools}")

        latest = conversation.messages[-1]

        messages.append({"role": "system", "content": DECENSORSHIP_PROMPT})
        messages.append({"role": "system", "content": TPL_TOOLS_PROMPT.safe_substitute({"tools":tools})})
        messages.append({"role": "system", "content": TPL_PARTNER_PROMPT.safe_substitute(latest.to_dict())})
        messages.append({"role": "system", "content": TELEGRAM_FORMATTING})
        messages.append({"role": "system", "content": DEFINE_QOT})

        recent_messages = conversation.messages[-10:] if len(conversation.messages) > 10 else conversation.messages
        for msg in recent_messages:
            messages.append(msg.to_dict())
        
        schemas = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema
                }
            }
            for tool in available_tools
        ]
        try:
            client = ollama.AsyncClient(host=self.ollama_url)

            stream = await client.chat(
                model=self.ollama_model,
                messages=messages,
                tools=schemas,
                stream=True,
                think=True,
            )

            thought = None
            thought_text = ""
            duration_text = ""
            response = None
            error = None
            last_edit = datetime.now() + timedelta(seconds=-300)
            async for chunk in stream:
                if response is None:
                    response = chunk
                else:
                    if response.message.content is None:
                        response.message.content = chunk.message.content or ""
                    else:
                        response.message.content += chunk.message.content or ""
                        
                    if response.message.thinking is not None:
                        response.message.thinking = chunk.message.thinking or ""
                    else:
                        response.message.thinking += chunk.message.thinking or ""

                    if response.message.tool_calls is None:
                        response.message.tool_calls = chunk.message.tool_calls
                    else:
                        response.message.tool_calls += chunk.message.tool_calls or []

                chunk_error = chunk.get("error", None)
                if error is None:
                    error = chunk_error
                elif chunk_error is not None:
                    error += chunk.get("error", None)

                if chunk.message.thinking:
                    MAX_THOUGHT_SIZE = 1024
                    if not thought:
                        if len(thought_text) > MAX_THOUGHT_SIZE:
                            thought = await event.reply(f"Thinking...\n{thought_text[-MAX_THOUGHT_SIZE:]}\n", parse_mode='markdown')
                        else:
                            thought = await event.reply(f"Thinking...\n{thought_text}\n...", parse_mode='markdown')

                    thought_text += chunk.message.thinking
                    if last_edit is None or datetime.now() - last_edit > timedelta(seconds=5):
                        if len(thought_text) > MAX_THOUGHT_SIZE:
                            await bot.edit_message(thought, f"Thinking...\n{thought_text[-MAX_THOUGHT_SIZE:]}\n...", parse_mode='markdown')
                        else:
                            await bot.edit_message(thought, f"Thinking...\n{thought_text}\n...", parse_mode='markdown')
                        last_edit = datetime.now()

                if chunk.done:
                    response.total_duration = chunk.total_duration
                    response.prompt_eval_duration = chunk.prompt_eval_duration
                    response.eval_duration = chunk.eval_duration
                    response.load_duration = chunk.load_duration

                    total_duration = round(response.total_duration / 1_000_000_000, 4)
                    prompt_eval_duration = round(response.prompt_eval_duration / 1_000_000_000, 4)
                    eval_duration = round(response.eval_duration / 1_000_000_000, 4)
                    load_duration = round(response.load_duration / 1_000_000_000, 4)
                    logging.info(f"chunk duration: {eval_duration}, {prompt_eval_duration}, {load_duration}, {total_duration}")

                    duration_text = f"\ntotal duration: {total_duration}s"
                    # duration_text += f"\nprompt eval duration: {prompt_eval_duration}s"
                    # duration_text += f"eval duration: {eval_duration}s"
                    # duration_text += f"\nload duration: {load_duration}s"

                    if thought_text:
                        thought_text += f"\n{duration_text}"
                        if len(thought_text) > MAX_THOUGHT_SIZE:
                            await bot.edit_message(thought, f"Thinking...\n{thought_text[-MAX_THOUGHT_SIZE:]}\n...", parse_mode='markdown')
                        else:
                            await bot.edit_message(thought, f"Thinking...\n{thought_text}\n...", parse_mode='markdown')
                    break


            tool_calls = response.message.tool_calls
            call_count = 0

            content = []



            content.append(response.message.content or "")
            logging.info(f"thinking: {response.message.thinking}")
            logging.info(f"content: {response.message.content}")

            tool_data = None
            tool_text = ""

            while tool_calls is not None and call_count < self.MAX_TOOL_CALLS:
                tool_results = []
                if error is not None:
                    return f"Error: {error}", thought, thought_text, duration_text
                
                logging.info(f"tool_calls: {tool_calls}")
                
                for tool_call in tool_calls:
                    name = tool_call.function.name
                    parameters = tool_call.function.arguments
                    if isinstance(parameters, str):
                        try:
                            parameters = json.loads(parameters)
                        except json.JSONDecodeError:
                            parameters = {}

                    logging.info(f"using tool: {name}({parameters})")
                    try:
                        result = await self.mcp.call_tool(name, parameters)

                        for part in result.content:
                            logging.info(f"tool {part.type}: {part}")
                            if part.type == "text":
                                tool_text = part.text
                            elif part.data:
                                tool_data = base64.b64decode(part.data)
                                ext = mimetypes.guess_extension(part.mimeType) or "bin"
                                file = await bot.upload_file(tool_data, file_name=f"image.{ext}")
                                await bot.send_file(event.chat, caption=tool_text, file=file, reply_to=event.message.id, voice_note=part.type == "audio")
                            elif part.type == "resource":
                                if part.resource.blob:
                                    tool_data = base64.b64decode(part.resource.blob)
                                    ext = mimetypes.guess_extension(part.mimeType) or "txt"
                                    file = await bot.upload_file(tool_data, file_name=f"resource.{ext}")
                                    await bot.send_file(event.chat, file=file, caption=part.resource.uri, reply_to=event.message.id)
                                else:
                                    tool_data = part.resource.uri
                                    tool_text = part.resource.uri
                                    await event.reply(part.resource.uri)
                            elif part.type == "resource_link":
                                tool_text = part.uri
                                await event.reply(f"{part.uri}; {part.title}; {part.name}; {part.description}; {part.meta}; {part.mimeType}")

                        tool_result = {
                            "tool_call_id": tool_call.get("id", str(uuid.uuid4())),
                            "role": "tool",
                            "name": name,
                            "content": tool_text,
                        }
                        logging.error(f"tool_result({name}): {tool_result}")

                        tool_results.append(tool_result)
                    except Exception as e:
                        logging.error(f"Error calling tool {name}: {e}")
                        continue

                tool_calls = None
                call_count += 1

                messages.append(response.message)
                messages.extend(tool_results)

                logging.debug(f"response.message.content: {response.message.content}")
                response = await client.chat(
                    model=self.ollama_model,
                    messages=messages,
                    tools=schemas,
                    stream=False,
                    think=True,
                )
                
                error = response.get("error", None)
                tool_calls = response.message.tool_calls
                content.append(response.message.content or "")
                logging.info(f"thinking: {response.message.thinking}")
                logging.info(f"content: {response.message.content}")

            if error:
                return f"Error: {error}", thought, thought_text, duration_text
            if len(content) == 0:
                return tool_text or "No response", thought, thought_text, duration_text
            return "----\n".join(content) or tool_text or "No response", thought, thought_text, duration_text
        except Exception as e:
            logger.error(f"Error calling Ollama: {e}")
            return f"Error: {e}", thought, thought_text, duration_text

    