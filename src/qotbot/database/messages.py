import logging
from telethon import events
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from qotbot.database.models.user import User
from qotbot.database.models.chat import Chat, ChatMember
from qotbot.database.models.message import Message
from qotbot.database.models.summary import DailySummary


logger = logging.getLogger(__name__)


def _create_or_update_user(session, sender, sender_id):
    user = session.get(User, sender_id)
    if not user:
        from telethon.tl.types import User as TelegramUser

        if isinstance(sender, TelegramUser):
            user = User(
                id=sender_id,
                username=sender.username if sender else None,
                first_name=sender.first_name if sender else None,
                last_name=sender.last_name if sender else None,
                is_bot=sender.bot if sender else False,
            )
        else:
            user = User(
                id=sender_id,
                username=None,
                first_name=None,
                last_name=None,
                is_bot=False,
            )
        session.add(user)
        logger.info(f"Created user {sender_id}")
    return user


def _create_or_update_chat(session, event):
    chat = session.get(Chat, event.chat_id)
    if not chat:
        chat_type = (
            "private" if event.is_private else "group" if event.is_group else "channel"
        )
        chat = Chat(
            id=event.chat_id,
            title=getattr(event.chat, "title", None),
            chat_type=chat_type,
            username=getattr(event.chat, "username", None),
        )
        session.add(chat)
        logger.info(f"Created chat {event.chat_id}")
    return chat


def _ensure_chat_member(session, user, chat):
    chat_member = (
        session.query(ChatMember).filter_by(user_id=user.id, chat_id=chat.id).first()
    )
    if not chat_member:
        chat_member = ChatMember(user_id=user.id, chat_id=chat.id)
        session.add(chat_member)
    return chat_member


def _create_message_from_event(session, event):
    media = event.message.media
    media_file_id = None
    media_type = None

    if media:
        media_type = type(media).__name__.lower()
        if hasattr(media, "photo") and media.photo:
            media_file_id = str(media.photo.id)
        elif hasattr(media, "document") and media.document:
            media_file_id = str(media.document.id)

    message = Message(
        id=event.message.id,
        chat_id=event.chat_id,
        sender_id=event.sender_id,
        text=event.raw_text,
        message_date=event.message.date,
        is_reply=event.message.is_reply,
        reply_to_message_id=event.message.reply_to.reply_to_msg_id
        if event.message.is_reply
        else None,
        media_file_id=media_file_id,
        media_type=media_type if media else None,
        image_description=None,
    )
    session.add(message)
    return message


def _create_message(session, message):
    media = message.media
    media_file_id = None
    media_type = None

    if media:
        media_type = type(media).__name__.lower()
        if hasattr(media, "photo") and media.photo:
            media_file_id = str(media.photo.id)
        elif hasattr(media, "document") and media.document:
            media_file_id = str(media.document.id)

    entity = Message(
        id=message.id,
        chat_id=message.chat_id,
        sender_id=message.sender_id,
        text=message.raw_text,
        message_date=message.date,
        is_reply=message.is_reply,
        reply_to_message_id=message.reply_to.reply_to_msg_id
        if message.is_reply
        else None,
        media_file_id=media_file_id,
        media_type=media_type if media else None,
        image_description=None,
    )
    session.add(entity)
    return entity


async def store_message_from_event(
    session: Session, event: events.NewMessage.Event
) -> None:
    logging.info(f"Storing message {event.message.id} from chat {event.chat_id}")

    sender = await event.get_sender()

    user = _create_or_update_user(session, sender, event.sender_id)
    chat = _create_or_update_chat(session, event)
    _create_message_from_event(session, event)

    logging.info(f"Message {event.message.id} stored successfully")


async def store_message(session: Session, message):
    logging.info(f"Storing message {message.id} from chat {message.chat_id}")
    _create_message(session, message)
    logging.info(f"Message {message.id} stored successfully")


def get_recent_messages(
    session: Session, chat_id: int, limit: int = 50
) -> list[Message]:
    logging.info(f"Retrieving last {limit} messages for chat {chat_id}")

    results = (
        session.query(Message)
        .filter(Message.chat_id == chat_id)
        .order_by(Message.message_date.desc())
        .limit(limit)
        .all()
    )

    logging.info(f"Retrieved {len(results)} messages for chat {chat_id}")

    return list(reversed(results))


def get_sender_name(user: User | None) -> str:
    if user is None:
        return "Unknown User"

    if user.first_name and user.last_name:
        return f"{user.first_name} {user.last_name}"

    if user.first_name:
        return user.first_name

    if user.username:
        return f"@{user.username}"

    return f"User {user.id}"


def get_chat_summary(session: Session, chat_id: int) -> DailySummary | None:
    logging.info(f"Retrieving latest summary for chat {chat_id}")

    summary = (
        session.query(DailySummary)
        .filter(DailySummary.chat_id == chat_id)
        .order_by(DailySummary.summary_date.desc())
        .first()
    )

    if summary:
        logging.info(f"Found summary from {summary.summary_date}")
    else:
        logging.info(f"No summary found for chat {chat_id}")

    return summary


def get_chat_overall_summary(session: Session, chat_id: int) -> str | None:
    logging.info(f"Retrieving overall summary for chat {chat_id}")

    chat = session.get(Chat, chat_id)

    if chat:
        logging.info(f"Found overall summary for chat {chat_id}")
        return chat.overall_summary
    else:
        logging.info(f"Chat {chat_id} not found")
        return None


def get_chat(session: Session, chat_id: int) -> Chat | None:
    logging.info(f"Retrieving chat {chat_id}")
    chat = session.get(Chat, chat_id)
    if chat:
        logging.info(f"Found chat {chat_id}")
    else:
        logging.info(f"Chat {chat_id} not found")
    return chat


def store_image_description(
    session: Session, message_id: int, chat_id: int, description: str
) -> None:
    logging.info(
        f"Storing image description for message {message_id} in chat {chat_id}"
    )
    message = session.get(Message, message_id)
    if message:
        message.image_description = description
        logging.info(f"Image description stored for message {message_id}")
    else:
        logging.warning(
            f"Message {message_id} not found, cannot store image description"
        )
