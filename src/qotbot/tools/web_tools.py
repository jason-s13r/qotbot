import os
import aiohttp
from fastmcp import FastMCP

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

    api_url = f"https://wttr.in/{city}?format=4"
    timeout = aiohttp.ClientTimeout(total=10)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(api_url) as resp:
                resp.raise_for_status()
                return await resp.text()
    except aiohttp.ClientResponseError as e:
        return f"Error from weather API: {e.message}"
    except Exception as e:
        return f"Failed to get weather: {str(e)}"


@web_tools.tool
async def search_web(query: str, max_results: int = 5) -> str:
    """
    Search the web using Ollama's web search API and return relevant results.

    Args:
        query: A natural language search query.
        max_results: Maximum number of results to return (default 5, max 10).

    Returns:
        A string with search results including title, URL, and content snippets.
    """
    api_url = "https://ollama.com/api/web_search"
    api_key = os.getenv("OLLAMA_API_KEY")

    if not api_key:
        return "Error: OLLAMA_API_KEY not set. Please set this environment variable."

    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {"query": query, "max_results": min(max_results, 10)}

    timeout = aiohttp.ClientTimeout(total=15)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(api_url, json=payload, headers=headers) as resp:
                resp.raise_for_status()
                result = await resp.json()

                if "results" in result:
                    formatted = []
                    for r in result["results"]:
                        formatted.append(
                            f"**{r.get('title', 'No title')}**\nURL: {r.get('url', 'No URL')}\n{r.get('content', 'No content')}"
                        )
                    return "\n\n".join(formatted)
                else:
                    return "No results found."
    except aiohttp.ClientResponseError as e:
        return f"Error from web search: {e.message}"
    except Exception as e:
        return f"Failed to search web: {str(e)}"


if __name__ == "__main__":
    web_tools.run()
