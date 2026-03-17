import asyncio
import json
import logging
from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from openai import AsyncOpenAI
from typing import Any

logger = logging.getLogger(__name__)


def _extract_tool_result_text(result: ToolResult) -> str:
    """
    Extract text string from FastMCP ToolResult for LLM tool response format.

    Priority order:
    1. structured_content['result'] if available (clean data format)
    2. First TextContent.text from content list
    3. Fallback to string representation

    Future extensibility: Can add ImageContent, AudioContent handling here.
    """
    if result.structured_content:
        if "result" in result.structured_content:
            return str(result.structured_content["result"])

    if result.content:
        first_block = result.content[0]
        if hasattr(first_block, "text"):
            return first_block.text
        return str(first_block)

    return str(result) if result is not None else "EMPTY_RESULT"


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
            return {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": "NO_TOOLS_AVAILABLE",
            }

        name = tool_call.function.name
        args = json.loads(tool_call.function.arguments)

        try:
            result = await tools.call_tool(name, args)
            logger.info(
                "Tool Call: [%s] %s args: %s\nRESULT: %s",
                tool_call.id,
                name,
                str(args)[:200],
                str(result)[:200],
            )
            content_text = _extract_tool_result_text(result)
            return {"role": "tool", "tool_call_id": tool_call.id, "content": content_text}
        except Exception as e:
            logger.error(
                "Tool Error: [%s] %s args: %s - %s",
                tool_call.id,
                name,
                args,
                e,
                exc_info=True,
            )
            return {"role": "tool", "tool_call_id": tool_call.id, "content": f"ERROR: {str(e)}"}
        

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
            logger.warning("No response from LLM")
            return "EMPTY"

        message = response.choices[0].message

        if not message.tool_calls:
            logger.info("LLM response: (no tools) %s", message.content)
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
        max_iterations: int | None = 5
    ) -> str | None:
        schemas = await self._tool_schema(tools) if tools else []
        messages = self._system + prompts

        result = None
        iter = 0
        while result is None and (iter < max_iterations or max_iterations is None):
            iter += 1
            result = await self._invoke(messages, tools, schemas, max_completion_tokens)

        return result
