import os
import ollama
import aiohttp
from fastmcp import FastMCP

from qotbot.utils.config import WEB_TIMEOUT

web_tools = FastMCP("Web Search")



@web_tools.tool
async def get_weather(city: str) -> str:
    """
    Simple tool to get current weather for a given city using wttr.in API.

    Args:
        city: Name of the city to get weather for.

    Returns:
        A string describing the current weather in the specified city.
    """

    api_url = f"https://wttr.in/{city}"
    timeout = aiohttp.ClientTimeout(total=WEB_TIMEOUT)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(api_url) as resp:
                resp.raise_for_status()
                return await resp.text()
    except aiohttp.ClientResponseError as e:
        return f"Error from weather API: {str(e)}"
    except Exception as e:
        return f"Failed to get weather: {str(e)}"

@web_tools.tool
async def web_fetch(url: str, max_results: int = 3) -> str:
    client = ollama.AsyncClient()
    response = await client.web_fetch(url)
    return response


@web_tools.tool
async def search_web(query: str, max_results: int = 5) -> str:
    client = ollama.AsyncClient()
    response = await client.web_search(query, max_results)
    return response


@web_tools.tool
async def wolfram_alpha_query(query: str) -> str:
    """
    Query Wolfram Alpha and return the plaintext result.

    Args:
        query: A natural language or structured query for Wolfram Alpha.

    Returns:
        A string with the result, or an error message if no result is found.
    """
    appid = os.environ.get("WOLFRAM_APPID")
    if not appid:
        return "Error: WOLFRAM_APPID not set. Please set this environment variable."

    endpoint = "https://www.wolframalpha.com/api/v1/llm-api"
    params = {"input": query, "appid": appid}

    timeout = aiohttp.ClientTimeout(total=WEB_TIMEOUT)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(endpoint, params=params) as resp:
                resp.raise_for_status()
                return await resp.text()
    except aiohttp.ClientResponseError as e:
        return f"Error from Wolfram Alpha: {str(e)}"
    except Exception as e:
        return f"Failed to query Wolfram Alpha: {str(e)}"


if __name__ == "__main__":
    web_tools.run()
