from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, timezone

from .models import User, Chat, Message, ClaudeSession, Memory, MessageChunk


async def get_or_create_user(
    session: AsyncSession, telegram_id: int, username: str | None, first_name: str
) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()

    if not user:
        user = User(telegram_id=telegram_id, username=username, first_name=first_name)
        session.add(user)
        await session.flush()
    else:
        if user.username != username:
            user.username = username
        if user.first_name != first_name:
            user.first_name = first_name

    return user


async def get_or_create_chat(
    session: AsyncSession, telegram_id: int, title: str | None = None
) -> Chat:
    result = await session.execute(select(Chat).where(Chat.telegram_id == telegram_id))
    chat = result.scalar_one_or_none()

    if not chat:
        chat = Chat(telegram_id=telegram_id, title=title)
        session.add(chat)
        await session.flush()
    else:
        if title and chat.title != title:
            chat.title = title

    return chat


async def set_chat_throttle(
    session: AsyncSession, chat: Chat, throttle_seconds: int
) -> Chat:
    chat.throttle_seconds = throttle_seconds
    await session.flush()
    return chat


async def get_chat_by_id(session: AsyncSession, chat_id: int) -> Chat | None:
    result = await session.execute(select(Chat).where(Chat.id == chat_id))
    return result.scalar_one_or_none()


async def persist_message(
    session: AsyncSession,
    chat: Chat,
    user: User,
    text: str,
    is_bot: bool = False,
    session_ref: ClaudeSession | None = None,
    media_type: str | None = None,
    media_file_id: str | None = None,
    media_base64: str | None = None,
) -> Message:
    message = Message(
        chat_id=chat.id,
        user_id=user.id,
        text=text,
        is_bot=is_bot,
        session_id=session_ref.id if session_ref else None,
        media_type=media_type,
        media_file_id=media_file_id,
        media_base64=media_base64,
    )
    session.add(message)
    await session.flush()
    return message


async def get_active_session(
    session: AsyncSession, chat_id: int, timeout_minutes: int = 10
) -> ClaudeSession | None:
    result = await session.execute(
        select(ClaudeSession)
        .where(ClaudeSession.chat_id == chat_id)
        .where(ClaudeSession.status == "active")
        .order_by(ClaudeSession.created_at.desc())
    )
    active_session = result.scalar_one_or_none()

    if active_session:
        # Handle both naive and timezone-aware datetimes for backward compatibility
        updated_at = active_session.updated_at
        if updated_at.tzinfo is None:
            # Convert naive datetime to timezone-aware (assume UTC)
            updated_at = updated_at.replace(tzinfo=timezone.utc)

        if datetime.now(timezone.utc) - updated_at > timedelta(minutes=timeout_minutes):
            active_session.status = "closed"
            active_session.updated_at = datetime.now(timezone.utc)
            return None

    return active_session


async def create_session(
    session: AsyncSession, chat: Chat, trigger_message: Message
) -> ClaudeSession:
    new_session = ClaudeSession(
        chat_id=chat.id,
        trigger_message_id=trigger_message.id,
        status="active",
    )
    session.add(new_session)
    await session.flush()
    return new_session


async def close_session(
    session: AsyncSession, claude_session: ClaudeSession, summary: str | None = None
) -> None:
    claude_session.status = "closed"
    claude_session.summary = summary
    claude_session.updated_at = datetime.now(timezone.utc)
    await session.flush()


async def get_user_memories(session: AsyncSession, user_id: int) -> list[Memory]:
    result = await session.execute(
        select(Memory).where(Memory.user_id == user_id).order_by(Memory.created_at)
    )
    return list(result.scalars().all())


async def save_user_memory(session: AsyncSession, user_id: int, content: str) -> Memory:
    memory = Memory(user_id=user_id, content=content)
    session.add(memory)
    await session.flush()
    return memory


async def get_recent_messages(
    session: AsyncSession, chat_id: int, limit: int = 50
) -> list[Message]:
    result = await session.execute(
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_unchunked_messages_count(session: AsyncSession, chat_id: int) -> int:
    from sqlalchemy import func

    result = await session.execute(
        select(func.count(Message.id)).where(
            Message.chat_id == chat_id, Message.chunk_id.is_(None)
        )
    )
    return result.scalar() or 0


async def get_session_chunks_for_session(
    session: AsyncSession, claude_session: ClaudeSession, limit: int = 10
) -> list[MessageChunk]:
    """Get recent chunk summaries for a chat."""
    result = await session.execute(
        select(MessageChunk)
        .where(MessageChunk.chat_id == claude_session.chat_id)
        .order_by(MessageChunk.chunk_index.desc())
        .limit(limit)
    )
    chunks = list(result.scalars().all())
    return list(reversed(chunks))
