from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastmcp import FastMCP

date_tool = FastMCP("Time and Date")


@date_tool.tool
def utc_time_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@date_tool.tool
def local_time_now() -> str:
    return datetime.now().astimezone().isoformat()


@date_tool.tool
def time_now(tzname: str = "UTC") -> str:
    try:
        tz = ZoneInfo(tzname)
    except (ZoneInfoNotFoundError, KeyError):
        tz = ZoneInfo("UTC")
    return datetime.now(tz=tz).isoformat()


@date_tool.tool
def local_timezone() -> str:
    tz = datetime.now().astimezone().tzname()
    return tz if tz else "UTC"


if __name__ == "__main__":
    date_tool.run()
