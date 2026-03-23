import logging
from datetime import datetime, timedelta, timezone
from fastmcp import FastMCP
from sqlalchemy import select, func

from qotbot.database.database import get_log_session
from qotbot.database.models.log import Log

logger = logging.getLogger(__name__)

log_tools = FastMCP("logs")


@log_tools.tool
async def search_logs(
    query: str,
    limit: int = 10,
    level: str | None = None,
) -> str:
    """Search logs by message text."""
    async with get_log_session() as session:
        stmt = select(Log)
        stmt = stmt.where(Log.message.like(f"%{query}%"))
        if level:
            stmt = stmt.where(Log.level == level)
        stmt = stmt.order_by(Log.timestamp.desc()).limit(limit)

        result = await session.execute(stmt)
        logs = result.scalars().all()

        if not logs:
            return "No matching log entries found."

        formatted = [
            f"[{log.timestamp}] [{log.level}] {log.logger}: {log.message}"
            for log in logs
        ]

        return "\n".join(formatted)


@log_tools.tool
async def get_recent_logs(
    minutes: int = 30,
    limit: int = 20,
    level: str | None = None,
) -> str:
    """Get recent logs from the last N minutes."""
    since = datetime.now(timezone.utc) - timedelta(minutes=minutes)

    async with get_log_session() as session:
        stmt = select(Log)
        stmt = stmt.where(Log.timestamp >= since)
        if level:
            stmt = stmt.where(Log.level == level)
        stmt = stmt.order_by(Log.timestamp.desc()).limit(limit)

        result = await session.execute(stmt)
        logs = result.scalars().all()

        if not logs:
            return f"No log entries found in the last {minutes} minutes."

        formatted = [
            f"[{log.timestamp}] [{log.level}] {log.logger}: {log.message}"
            for log in logs
        ]

        return "\n".join(formatted)


@log_tools.tool
async def count_logs_by_level() -> str:
    """Count log entries grouped by level."""
    async with get_log_session() as session:
        stmt = select(Log.level, func.count(Log.id).label("count")).group_by(Log.level)
        stmt = stmt.order_by(func.count(Log.id).desc())

        result = await session.execute(stmt)
        rows = result.all()

        if not rows:
            return "No log entries found."

        formatted = [f"{row[0]}: {row[1]}" for row in rows]
        return "\n".join(formatted)
