from datetime import datetime, timezone
from fastmcp import FastMCP

date_tool = FastMCP("Time and Date")


@date_tool.tool
def time_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@date_tool.tool
def local_timezone() -> str:
    return datetime.now().astimezone().tzname()


if __name__ == "__main__":
    date_tool.run()
