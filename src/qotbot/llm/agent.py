import asyncio
import json
import logging
from fastmcp import FastMCP
from openai import AsyncOpenAI
from typing import Any

logger = logging.getLogger(__name__)


class Agent:
    def __init__(self, client: AsyncOpenAI, model: str, system: list[dict[str, Any]]):
        self._client = client
        self._model = model
        self._system = system

    async def _tool_schema(self, tools: FastMCP):
        available_tools = await tools.list_tools()
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
        return schemas

    async def _call_tool(self, tool_call, tools: FastMCP | None = None):
        if tools is None:
            return {"role": "tool", "tool_call_id": tool_call.id, "content": "NO_TOOLS_AVAILABLE"}
        
        name = tool_call.function.name
        args = json.loads(tool_call.function.arguments)

        result = await tools.call_tool(name, args)

        return {"role": "tool", "tool_call_id": tool_call.id, "content": result}

    async def _invoke(
        self,
        messages: list[dict[str, Any]],
        tools: FastMCP | None = None,
        schemas: list[dict[str, Any]] = None,
        max_completion_tokens: int | None = None,
    ):
        response = await self._client.chat.completions.create(
            max_completion_tokens=max_completion_tokens,
            model=self._model,
            messages=messages,
            tool_choice="auto",
            tools=schemas,
        )

        if response is None:
            return "EMPTY"

        message = response.choices[0].message

        if not message.tool_calls:
            return message.content or "EMPTY"

        messages.append(message)

        calls = [self._call_tool(tool_call, tools) for tool_call in message.tool_calls]
        results = await asyncio.gather(*calls)

        messages.extend(results)

        return None

    async def invoke(
        self,
        prompts: list[dict[str, Any]],
        tools: FastMCP | None = None,
        max_completion_tokens: int | None = 1024,
    ) -> str | None:
        schemas = await self._tool_schema(tools) if tools else []
        messages = self._system + prompts

        result = None
        while result is None:
            result = await self._invoke(messages, tools, schemas, max_completion_tokens)

        return result
