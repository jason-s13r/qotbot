import os
import requests
from fastmcp import FastMCP

wolfram_alpha = FastMCP("Wolfram Alpha")

@wolfram_alpha.tool
def wolfram_alpha_query(query: str) -> str:
    """
    Query Wolfram Alpha and return the plaintext result.

    Args:
        query: A natural language or structured query for Wolfram Alpha.

    Returns:
        A string with the result, or an error message if no result is found.
    """
    endpoint = "https://www.wolframalpha.com/api/v1/llm-api"
    params = {
        "input": query,
        "appid": os.environ.get("WOLFRAM_APPID")
    }

    try:
        resp = requests.get(endpoint, params=params, timeout=10)
        resp.raise_for_status()
        return resp.text.strip()
    except requests.HTTPError as e:
        return f"Error from Wolfram Alpha: {e.response.text}"
    except Exception as e:
        return f"Failed to query Wolfram Alpha: {str(e)}"
    

if __name__ == "__main__":
    wolfram_alpha.run()