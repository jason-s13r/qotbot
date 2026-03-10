from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from db.models import Message, ClaudeSession
from config import HISTORY_WINDOW
from db.crud import (
    get_recent_messages as crud_get_recent,
    get_session_chunks_for_session,
)


async def build_session_prompt(
    session: AsyncSession,
    claude_session: ClaudeSession,
    new_messages: list[Message],
    is_continuation: bool = False,
) -> str:
    """
    Build the prompt for the LLM based on session state.

    For first prompt:
    - System prompt
    - Session intro
    - Last 5 closed session summaries
    - Last 10 chunk summaries
    - Recent unchunked messages (pre-session)
    - New messages

    For continuation:
    - System prompt
    - Chunks spanning session lifetime
    - Pre-session context (unchunked non-session messages)
    - Session history (unchunked session messages already addressed)
    - New messages
    """
    if not is_continuation:
        return await _build_first_prompt(session, claude_session, new_messages)
    else:
        return await _build_continuation_prompt(session, claude_session, new_messages)


async def _build_first_prompt(
    session: AsyncSession,
    claude_session: ClaudeSession,
    new_messages: list[Message],
) -> str:
    """Build the first prompt for a new session."""
    parts = []

    closed_sessions_result = await session.execute(
        select(ClaudeSession)
        .where(ClaudeSession.chat_id == claude_session.chat_id)
        .where(ClaudeSession.status == "closed")
        .where(ClaudeSession.summary.isnot(None))
        .order_by(ClaudeSession.updated_at.desc())
        .limit(5)
    )
    closed_sessions = list(closed_sessions_result.scalars().all())

    if closed_sessions:
        parts.append("<previous_sessions>")
        for cs in reversed(closed_sessions):
            parts.append(f"Session summary: {cs.summary}")
        parts.append("</previous_sessions>")

    chunks = await get_session_chunks_for_session(session, claude_session, limit=10)

    if chunks:
        parts.append("<chat_history>")
        for chunk in reversed(chunks):
            parts.append(f"[History] {chunk.summary}")
        parts.append("</chat_history>")

    recent_messages = await crud_get_recent(
        session, claude_session.chat_id, limit=HISTORY_WINDOW
    )
    session_message_ids = set()
    for m in recent_messages:
        if m.session_id and m.session_id != claude_session.id:
            session_message_ids.add(m.id)

    recent_non_session = [m for m in recent_messages if m.id not in session_message_ids]

    if recent_non_session:
        parts.append("<recent_context>")
        for msg in recent_non_session[-10:]:
            parts.append(f"[{msg.created_at.strftime('%H:%M:%S')}] {msg.text}")
            if msg.media_type:
                parts.append(f"  [{msg.user.first_name} sent a {msg.media_type}]")
        parts.append("</recent_context>")

    parts.append("<new_messages>")
    for msg in new_messages:
        sender = msg.user.first_name if msg.user else "Unknown"
        parts.append(f"[{msg.created_at.strftime('%H:%M:%S')}] {sender}: {msg.text}")
        if msg.media_type:
            parts.append(f"  [{sender} sent a {msg.media_type}]")
    parts.append("</new_messages>")

    return "\n".join(parts)


async def _build_continuation_prompt(
    session: AsyncSession,
    claude_session: ClaudeSession,
    new_messages: list[Message],
) -> str:
    """Build a continuation prompt for an active session."""
    parts = []

    chunks = await get_session_chunks_for_session(session, claude_session)

    if chunks:
        parts.append("<chat_history>")
        for chunk in chunks:
            parts.append(f"[History] {chunk.summary}")
        parts.append("</chat_history>")

    session_messages_result = await session.execute(
        select(Message)
        .where(Message.session_id == claude_session.id)
        .where(Message.id.notin_([m.id for m in new_messages]))
        .order_by(Message.created_at.asc())
        .options(selectinload(Message.user))
    )
    session_history = list(session_messages_result.scalars().all())

    if session_history:
        parts.append("<session_history>")
        for msg in session_history[-20:]:
            sender = msg.user.first_name if msg.user else "Bot"
            parts.append(
                f"[{msg.created_at.strftime('%H:%M:%S')}] {sender}: {msg.text}"
            )
            if msg.media_type:
                parts.append(f"  [{sender} sent a {msg.media_type}]")
        parts.append("</session_history>")

    parts.append("<new_messages>")
    for msg in new_messages:
        sender = msg.user.first_name if msg.user else "Unknown"
        parts.append(f"[{msg.created_at.strftime('%H:%M:%S')}] {sender}: {msg.text}")
        if msg.media_type:
            parts.append(f"  [{sender} sent a {msg.media_type}]")
    parts.append("</new_messages>")

    return "\n".join(parts)


async def get_recent_messages(
    session: AsyncSession, chat_id: int, limit: int = 50
) -> list[Message]:
    """Get recent messages for a chat."""
    return await crud_get_recent(session, chat_id, limit)
