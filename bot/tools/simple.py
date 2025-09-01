from datetime import datetime
from fastmcp import FastMCP

simple = FastMCP("Simple")

@simple.tool
def get_current_time() -> str:
    """Get's the current time."""
    
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

@simple.tool
def greet(name: str) -> str:
    """Greets the user by name and asks if they know what Qot means."""

    return f"Hello, {name}, do you know what Qot means?"


if __name__ == "__main__":
    simple.run()