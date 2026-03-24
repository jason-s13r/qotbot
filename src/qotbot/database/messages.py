import logging
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from telethon import events
from telethon.tl.custom import Message

from sqlalchemy.orm import selectinload

from qotbot.database.models.chat import Chat
from qotbot.database.models.message import Message
from qotbot.database.models.user import User

logger = logging.getLogger(__name__)


async def store_message_from_event(
    session: AsyncSession, event: events.NewMessage.Event
) -> Message:
    """
    Store a message from a Telegram event into the database.
    Creates a new Message record with processed=False and queue_status='pending'.

    Args:
        session: Async database session
        event: Telegram NewMessage event

    Returns:
        The created Message object
    """
    chat_id = event.chat_id
    message_id = event.message.id
    sender_id = event.sender_id

    has_image = event.photo is not None or event.sticker is not None
    has_audio = event.audio is not None or event.voice is not None

    message = Message(
        id=message_id,
        chat_id=chat_id,
        sender_id=sender_id,
        text=event.raw_text,
        message_date=event.message.date,
        is_reply=event.message.reply_to is not None,
        reply_to_message_id=(
            event.message.reply_to.reply_to_msg_id if event.message.reply_to else None
        ),
        media_file_id=None,
        has_image=has_image,
        has_audio=has_audio,
        processed=False,
        audio_transcribed=False,
        image_transcribed=False,
        classified=False,
        responded=False,
        is_approved=False,
        queue_status="pending",
    )

    session.add(message)
    logger.debug(f"Stored message message_id={message_id} in chat_id={chat_id}")
    return message


async def store_sent_message(session: AsyncSession, message, chat_id: int):
    """
    Store a message that was sent by the bot.

    Args:
        session: Async database session
        message: Telegram message object from send_message
        chat_id: The chat ID

    Returns:
        The created Message object
    """
    message_id = message.id
    sender_id = message.sender_id

    db_message = Message(
        id=message_id,
        chat_id=chat_id,
        sender_id=sender_id,
        text=message.raw_text,
        message_date=message.date,
        is_reply=message.reply_to is not None,
        reply_to_message_id=(
            message.reply_to.reply_to_msg_id if message.reply_to else None
        ),
        media_file_id=None,
        processed=True,
        audio_transcribed=False,
        image_transcribed=False,
        classified=False,
        responded=True,
        queue_status="complete",
    )

    session.add(db_message)
    logger.debug(f"Stored sent message message_id={message_id} in chat_id={chat_id}")
    return db_message


async def get_recent_messages(
    session: AsyncSession, chat_id: int, limit: int = 50, exclude_ids: list[int] = []
) -> list[Message]:
    """
    Get recent messages from a chat, ordered by message_date descending.
    Eagerly loads sender relationship to avoid lazy loading issues.

    Args:
        session: Async database session
        chat_id: The chat ID to query
        limit: Number of messages to retrieve

    Returns:
        List of Message objects
    """
    result = await session.execute(
        select(Message)
        .filter(
            Message.chat_id == chat_id,
            Message.id.not_in(exclude_ids),
        )
        .options(selectinload(Message.sender))
        .order_by(Message.message_date.desc())
        .limit(limit)
    )
    messages = result.scalars().all()
    return list(reversed(messages))


async def get_chat_summary(session: AsyncSession, chat_id: int) -> str:
    """
    Get the overall summary for a chat.

    Args:
        session: Async database session
        chat_id: The chat ID to query

    Returns:
        The chat's overall_summary string or empty string
    """
    chat = await session.get(Chat, chat_id)
    return chat.overall_summary or "" if chat else ""


async def get_chat_overall_summary(session: AsyncSession, chat_id: int) -> str:
    """
    Alias for get_chat_summary.

    Args:
        session: Async database session
        chat_id: The chat ID to query

    Returns:
        The chat's overall_summary string or empty string
    """
    return await get_chat_summary(session, chat_id)


def get_sender_name(user: User | None) -> str:
    """
    Get a human-readable name for a user.

    Args:
        user: User object or None

    Returns:
        Display name string
    """
    if not user:
        return "Unknown"
    if user.first_name and user.last_name:
        return f"{user.first_name} {user.last_name}"
    if user.first_name:
        return user.first_name
    if user.username:
        return user.username
    return f"User {user.id}"


async def store_image_description(
    session: AsyncSession, message_id: int, chat_id: int, description: str
):
    """
    Store an image description for a message.
    Sets image_transcribed=True and queue_status='classifying'.

    Args:
        session: Async database session
        message_id: The message ID
        chat_id: The chat ID
        description: The image description text
    """
    message = await session.get(Message, (chat_id, message_id))
    if message:
        message.image_description = description
        message.image_transcribed = True
        message.queue_status = "classifying"
        logger.info(f"Stored image description for message_id={message_id}")
    else:
        logger.warning(
            f"Message not found for image description: message_id={message_id}, chat_id={chat_id}"
        )


async def get_messages_ready_for_response(
    session: AsyncSession, limit: int = 3
) -> list[Message]:
    """
    Get messages that are approved and ready for response generation.
    Filters for messages within last 30 minutes that:
    - have not been responded to
    - have been approved for response
    - either have no image or have image description
    - either have no audio or have audio transcription

    Args:
        session: Async database session
        limit: Maximum number of messages to retrieve

    Returns:
        List of Message objects ready for response
    """
    from datetime import datetime, timedelta

    thirty_min_ago = datetime.utcnow() - timedelta(minutes=30)

    result = await session.execute(
        select(Message)
        .filter(
            Message.responded == False,
            Message.is_approved == True,
            Message.message_date >= thirty_min_ago,
        )
        .filter(
            (Message.has_image == False) | (Message.image_transcribed == True),
            (Message.has_audio == False) | (Message.audio_transcribed == True),
        )
        .order_by(Message.message_date.asc())
        .limit(limit)
    )
    return result.scalars().all()


async def store_audio_transcription(
    session: AsyncSession, message_id: int, chat_id: int, transcription: str
):
    """
    Store an audio transcription for a message.
    Sets audio_transcribed=True and queue_status='classifying'.

    Args:
        session: Async database session
        message_id: The message ID
        chat_id: The chat ID
        transcription: The transcribed text
    """
    message = await session.get(Message, (chat_id, message_id))
    if message:
        message.audio_transcription = transcription
        message.audio_transcribed = True
        message.queue_status = "classifying"
        logger.info(f"Stored audio transcription for message_id={message_id}")
    else:
        logger.warning(
            f"Message not found for audio transcription: message_id={message_id}, chat_id={chat_id}"
        )


async def store_message_classification(
    session: AsyncSession, message_id: int, chat_id: int, reason: str, is_approved: bool
):
    """
    Store a classification reason for a message.
    Sets classified=True and updates queue_status based on approval.

    Args:
        session: Async database session
        message_id: The message ID
        chat_id: The chat ID
        reason: The classification reason
        is_approved: Whether the message is approved
    """
    message = await session.get(Message, (chat_id, message_id))
    if message:
        message.classification_reason = reason
        message.classified = True
        message.is_approved = is_approved
        message.queue_status = "responding" if is_approved else "skipped"
        logger.info(
            f"Stored classification for message_id={message_id}: {reason[:50]}..."
        )
    else:
        logger.warning(
            f"Message not found for classification: message_id={message_id}, chat_id={chat_id}"
        )


async def get_unprocessed_messages(
    session: AsyncSession, limit: int = 100
) -> list[Message]:
    """
    Get messages that are pending processing, ordered by age.

    Args:
        session: Async database session
        limit: Maximum number of messages to retrieve

    Returns:
        List of Message objects with processed=False
    """
    result = await session.execute(
        select(Message)
        .filter(Message.processed == False)
        .order_by(Message.message_date.asc())
        .limit(limit)
    )
    return result.scalars().all()


async def get_message_age_minutes(
    session: AsyncSession, chat_id: int, message_id: int
) -> float:
    """
    Calculate the age of a message in minutes.

    Args:
        session: Async database session
        chat_id: The chat ID
        message_id: The message ID

    Returns:
        Age in minutes as float, or None if message not found
    """
    message = await session.get(Message, (chat_id, message_id))
    if not message:
        return None

    now = datetime.utcnow()
    age = now - message.message_date
    return age.total_seconds() / 60


async def get_pending_audio_messages(
    session: AsyncSession, limit: int = 50
) -> list[Message]:
    """
    Get messages with audio that need transcription.

    Args:
        session: Async database session
        limit: Maximum number of messages to retrieve

    Returns:
        List of Message objects with audio and audio_transcribed=False
    """
    result = await session.execute(
        select(Message)
        .filter(
            Message.audio_transcribed == False,
            Message.has_audio == True,
        )
        .order_by(Message.message_date.asc())
        .limit(limit)
    )
    return result.scalars().all()


async def get_pending_image_messages(
    session: AsyncSession, limit: int = 50
) -> list[Message]:
    """
    Get messages with images that need description.

    Args:
        session: Async database session
        limit: Maximum number of messages to retrieve

    Returns:
        List of Message objects with image and image_transcribed=False
    """
    result = await session.execute(
        select(Message)
        .filter(
            Message.image_transcribed == False,
            Message.has_image == True,
        )
        .order_by(Message.message_date.asc())
        .limit(limit)
    )
    return result.scalars().all()


async def get_pending_classification_messages(
    session: AsyncSession, limit: int = 50
) -> list[Message]:
    """
    Get messages that are ready for classification.

    Args:
        session: Async database session
        limit: Maximum number of messages to retrieve

    Returns:
        List of Message objects ready for classification
    """
    result = await session.execute(
        select(Message)
        .filter(
            Message.classified == False,
            Message.queue_status == "classifying",
        )
        .order_by(Message.message_date.asc())
        .limit(limit)
    )
    return result.scalars().all()


async def get_pending_response_messages(
    session: AsyncSession, limit: int = 50
) -> list[Message]:
    """
    Get messages that are approved and ready for response generation.

    Args:
        session: Async database session
        limit: Maximum number of messages to retrieve

    Returns:
        List of Message objects ready for response
    """
    result = await session.execute(
        select(Message)
        .filter(
            Message.responded == False,
            Message.queue_status == "responding",
        )
        .order_by(Message.message_date.asc())
        .limit(limit)
    )
    return result.scalars().all()


async def mark_message_skipped(
    session: AsyncSession,
    chat_id: int,
    message_id: int,
    reason: str,
):
    """
    Mark a message as skipped with a reason.

    Args:
        session: Async database session
        chat_id: The chat ID
        message_id: The message ID
        reason: The skip reason
    """
    message = await session.get(Message, (chat_id, message_id))
    if message:
        message.skip_reason = reason
        message.queue_status = "skipped"
        logger.info(f"Marked message_id={message_id} as skipped: {reason}")
    else:
        logger.warning(
            f"Message not found for skip marking: message_id={message_id}, chat_id={chat_id}"
        )


async def mark_message_responded(
    session: AsyncSession,
    chat_id: int,
    message_id: int,
):
    """
    Mark a message as responded.

    Args:
        session: Async database session
        chat_id: The chat ID
        message_id: The message ID
    """
    message = await session.get(Message, (chat_id, message_id))
    if message:
        message.responded = True
        message.queue_status = "complete"
        logger.info(f"Marked message_id={message_id} as responded")
    else:
        logger.warning(
            f"Message not found for response marking: message_id={message_id}, chat_id={chat_id}"
        )
