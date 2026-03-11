import json
import logging
from fastmcp import FastMCP
from openai import AsyncOpenAI
from typing import Any

logger = logging.getLogger(__name__)

async def invoke_llm(
    client: AsyncOpenAI,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | FastMCP | None = None,
    max_tokens: int = 1024,
) -> str | None:
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

    while True:
        response = await client.chat.completions.create(
            max_tokens=max_tokens,
            model=model,
            messages=messages,
            tool_choice="auto",
            tools=schemas,
        )

        if response is None:
            return "No response given."

        message = response.choices[0].message

        if not message.tool_calls:
            return message.content or ""

        messages.append(message)

        for tool_call in message.tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)

            result = await tools.call_tool(function_name, function_args)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )
