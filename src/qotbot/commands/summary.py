import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from openai import AsyncOpenAI
from telethon import events

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from qotbot.database.database import get_session
from qotbot.database.messages import get_recent_messages
from qotbot.database.models.chat import Chat
from qotbot.database.models.message import Message
from qotbot.database.models.summary import DailySummary
from qotbot.llm.summariser import Summariser
from qotbot.utils.get_identities import get_identities
from qotbot.utils.build_common_prompts import format_messages_for_prompt
from qotbot.utils.command import Commands

logger = logging.getLogger(__name__)

LLM_API_URL = os.getenv("LLM_API_URL", "http://localhost:11434")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
llmclient = AsyncOpenAI(base_url=LLM_API_URL, api_key=LLM_API_KEY)

summary = Commands()


@dataclass
class SummaryData:
    chat: Chat
    prior_summary: str
    messages: list[Message]
    transcript: str


async def _fetch_summary_data(
    session,
    chat_id: int,
    limit: int | None = None,
    since_date: datetime | None = None,
) -> SummaryData | None:
    """Fetch chat, prior summary, and messages for summarisation."""
    chat = await session.get(Chat, chat_id)

    if not chat:
        logger.warning(f"Chat {chat_id} not found in database for summary")
        return None

    prior_summary = chat.overall_summary

    if since_date:
        result = await session.execute(
            select(Message)
            .filter(
                Message.chat_id == chat_id,
                Message.message_date >= since_date,
            )
            .options(selectinload(Message.sender))
            .order_by(Message.message_date.desc())
        )
        messages = list(reversed(result.scalars().all()))
    else:
        messages = await get_recent_messages(session, chat_id, limit=limit or 1000)

    logger.info(
        f"Retrieved {len(messages)} messages from chat_id={chat_id} for summarisation"
    )
    transcript = format_messages_for_prompt(messages)

    return SummaryData(
        chat=chat,
        prior_summary=prior_summary or "",
        messages=messages,
        transcript=transcript,
    )


async def _build_summary_prompts(prior_summary: str, transcript: str) -> list[dict]:
    """Build prompts from prior summary and transcript."""
    return [
        {
            "role": "user",
            "content": f"<summary>\n{prior_summary}\n</summary>\n<transcript>{transcript}</transcript>",
        }
    ]


async def _invoke_summariser(
    client: AsyncOpenAI,
    bot_identity: str,
    chat_identity: str,
    prompts: list[dict],
    max_tokens: int = 10000,
    is_daily: bool = False,
    date: str | None = None,
) -> str | None:
    """Setup Summariser and invoke LLM."""
    summariser_instance = Summariser(
        client, bot_identity, chat_identity, is_daily=is_daily, date=date
    )
    logger.info(f"Invoking summariser LLM")
    summary = await summariser_instance.invoke(
        prompts, max_completion_tokens=max_tokens
    )
    return summary or ""


async def _save_summary(session, chat_id: int, summary: str) -> bool:
    """Save overall summary to Chat table. Returns False if chat not found."""
    chat = await session.get(Chat, chat_id)

    if not chat:
        logger.warning(f"Chat {chat_id} not found when saving summary")
        return False

    chat.overall_summary = summary
    session.add(chat)
    await session.commit()
    logger.info(f"Overall summary saved to database for chat_id={chat_id}")
    return True


async def _save_daily_summary(
    session, chat_id: int, summary: str, summary_date: datetime
) -> bool:
    """Save daily summary to DailySummary table."""
    daily_summary = DailySummary(
        chat_id=chat_id,
        summary_date=summary_date,
        summary_text=summary,
    )
    session.add(daily_summary)
    await session.commit()
    logger.info(f"Daily summary saved for chat_id={chat_id} on {summary_date.date()}")
    return True


async def _send_summary_to_telegram(
    event, summary: str, date: datetime | None = None
) -> None:
    """Send express summary and full file to Telegram."""
    if not summary:
        return

    express = re.split(r"-{4,}", summary)[0].strip("#")[:1000]
    msg = await event.reply(express)
    async with event.client.action(event.chat_id, "document"):
        filename = f"summary_{date.strftime('%Y-%m-%d')}.md" if date else "summary.md"
        file = await event.client.upload_file(
            summary.encode("utf-8"), file_name=filename
        )
        await msg.reply(file=file)


def _parse_daily_date(payload: str) -> datetime | None:
    """Parse date parameter for /daily command.

    Args:
        payload: One of:
            - YYYY-MM-DD formatted string
            - 'today' or 'yesterday'
            - Integer for N days ago

    Returns:
        datetime at 00:00 UTC for the target day, or None if invalid
    """
    payload = payload.strip().lower()

    if payload == "today":
        return datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    if payload == "yesterday":
        return (datetime.now(timezone.utc) - timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    try:
        days_ago = int(payload)
        return (datetime.now(timezone.utc) - timedelta(days=days_ago)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    except ValueError:
        pass

    try:
        date = datetime.strptime(payload, "%Y-%m-%d")
        return date.replace(tzinfo=timezone.utc)
    except ValueError:
        pass

    return None


@summary.slash("summary")
async def handle_summary_event(event: events.NewMessage.Event, payload: str):
    """Show the summary of the chat."""
    logger.info(
        f"/summary command invoked by user_id={event.sender_id} in chat_id={event.chat_id}"
    )

    bot_identity, chat_identity = await get_identities(event.client, event.chat_id)

    input_number = payload.strip()
    limit = int(input_number) if input_number.isdigit() else 1000

    async with get_session() as session:
        data = await _fetch_summary_data(session, event.chat_id, limit=limit)
        if not data:
            return

        prompts = await _build_summary_prompts(data.prior_summary, data.transcript)

        async with event.client.action(event.chat_id, "typing"):
            summary = await _invoke_summariser(
                llmclient, bot_identity, chat_identity, prompts
            )

        logger.info(
            f"Summary generated for chat_id={event.chat_id} ({len(summary) if summary else 0} characters)"
        )

        await _save_summary(session, event.chat_id, summary)

    await _send_summary_to_telegram(event, summary)


@summary.slash("daily")
async def handle_daily_event(event: events.NewMessage.Event, payload: str):
    """Show the daily summary of the chat."""
    logger.info(
        f"/daily command invoked by user_id={event.sender_id} in chat_id={event.chat_id}"
    )

    bot_identity, chat_identity = await get_identities(event.client, event.chat_id)

    since_date = (
        _parse_daily_date(payload)
        if payload.strip()
        else datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    )

    if not since_date:
        logger.warning(f"Invalid date parameter for /daily: {payload}")
        await event.reply(
            "Invalid date format. Use YYYY-MM-DD, 'today', 'yesterday', or a number."
        )
        return

    async with get_session() as session:
        data = await _fetch_summary_data(session, event.chat_id, since_date=since_date)
        if not data:
            return

        prompts = await _build_summary_prompts(data.prior_summary, data.transcript)

        async with event.client.action(event.chat_id, "typing"):
            summary = await _invoke_summariser(
                llmclient,
                bot_identity,
                chat_identity,
                prompts,
                is_daily=True,
                date=since_date.strftime("%Y-%m-%d"),
            )

        logger.info(
            f"Daily summary generated for chat_id={event.chat_id} ({len(summary) if summary else 0} characters)"
        )

        await _save_daily_summary(session, event.chat_id, summary, since_date)

    await _send_summary_to_telegram(event, summary, since_date)
