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
            logger.debug(
                "Tool call [%s]: %s(args=%s) -> %s",
                tool_call.id,
                name,
                str(args)[:200],
                str(result)[:200],
            )
            content_text = _extract_tool_result_text(result)
            return {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "tool_name": name,
                "content": content_text,
            }
        except Exception as e:
            logger.error(
                "Tool execution error [%s]: %s(args=%s) - %s",
                tool_call.id,
                name,
                args,
                e,
                exc_info=True,
            )
            return {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "tool_name": name,
                "content": f"ERROR: {str(e)}",
            }

    def _filter_tool_schemas(
        self,
        schemas: list[dict[str, Any]],
        tool_call_counts: dict[str, int],
        tool_call_limits: dict[str, int] | None,
    ) -> list[dict[str, Any]]:
        if not tool_call_limits:
            return schemas

        filtered: list[dict[str, Any]] = []
        for schema in schemas:
            function = schema.get("function", {})
            name = function.get("name")
            if not name:
                filtered.append(schema)
                continue

            limit = tool_call_limits.get(name)
            if limit is None:
                filtered.append(schema)
                continue

            if tool_call_counts.get(name, 0) < limit:
                filtered.append(schema)

        return filtered

    def _update_tool_call_counts(
        self, changes: list[dict[str, Any]], tool_call_counts: dict[str, int]
    ):
        for change in changes:
            if isinstance(change, dict):
                role = change.get("role")
                name = change.get("tool_name")
            else:
                role = getattr(change, "role", None)
                name = getattr(change, "tool_name", None)

            if role != "tool":
                continue
            if not name:
                continue
            tool_call_counts[name] = tool_call_counts.get(name, 0) + 1

    async def _invoke(
        self,
        prompts: list[dict[str, Any]],
        tools: FastMCP | None = None,
        schemas: list[dict[str, Any]] = None,
        max_completion_tokens: int | None = None,
    ) -> tuple[str | None, list[dict[str, Any]]]:
        messages: list[dict[str, Any]] = []
        response = await self._client.chat.completions.create(
            max_completion_tokens=max_completion_tokens,
            model=self._model,
            messages=prompts,
            tool_choice="auto",
            tools=schemas,
        )

        if response is None:
            logger.warning("LLM returned no response")
            return "EMPTY", messages

        message = response.choices[0].message

        if not message.tool_calls:
            logger.debug("LLM response (no tool calls): %s", message.content)
            return message.content or "EMPTY", messages

        messages.append(message)

        calls = [self._call_tool(tool_call, tools) for tool_call in message.tool_calls]
        results = await asyncio.gather(*calls)

        messages.extend(results)

        return None, messages

    async def invoke(
        self,
        prompts: list[dict[str, Any]],
        tools: FastMCP | None = None,
        max_completion_tokens: int | None = 1024,
        max_iterations: int | None = 5,
        tool_call_limits: dict[str, int] | None = None,
    ) -> str | None:
        schemas = await self._tool_schema(tools) if tools else []
        messages = self._system + prompts
        tool_call_counts: dict[str, int] = {}

        logger.debug(
            f"Starting LLM invocation with {len(prompts)} prompts, max_iterations={max_iterations}"
        )

        result = None
        iter = 0
        while result is None and (iter < max_iterations or max_iterations is None):
            iter += 1
            logger.debug(f"LLM iteration {iter}/{max_iterations}")
            iteration_schemas = self._filter_tool_schemas(
                schemas, tool_call_counts, tool_call_limits
            )
            result, changes = await self._invoke(
                messages, tools, iteration_schemas, max_completion_tokens
            )
            self._update_tool_call_counts(changes, tool_call_counts)
            messages.extend(changes)

        logger.debug(f"LLM invocation complete after {iter} iterations")
        return result
