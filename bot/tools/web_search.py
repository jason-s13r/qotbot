import os
import requests
from fastmcp import FastMCP

web_search = FastMCP("Web Search")


@web_search.tool
def search_web(query: str, max_results: int = 5) -> str:
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

    try:
        resp = requests.post(api_url, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        result = resp.json()

        if "results" in result:
            formatted = []
            for r in result["results"]:
                formatted.append(
                    f"**{r.get('title', 'No title')}**\nURL: {r.get('url', 'No URL')}\n{r.get('content', 'No content')}"
                )
            return "\n\n".join(formatted)
        else:
            return "No results found."
    except requests.HTTPError as e:
        return f"Error from web search: {e.response.text}"
    except Exception as e:
        return f"Failed to search web: {str(e)}"


if __name__ == "__main__":
    web_search.run()
