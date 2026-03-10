import logging
from telethon import events
from sqlalchemy.orm import Session

from qotbot.database.models.user import User
from qotbot.database.models.chat import Chat, ChatMember
from qotbot.database.models.message import Message


logger = logging.getLogger(__name__)


def _create_or_update_user(session, sender, sender_id):
    user = session.get(User, sender_id)
    if not user:
        user = User(
            id=sender_id,
            username=sender.username if sender else None,
            first_name=sender.first_name if sender else None,
            last_name=sender.last_name if sender else None,
            is_bot=sender.bot if sender else False,
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


def _create_message(session, event):
    message = Message(
        id=event.message.id,
        chat_id=event.chat_id,
        sender_id=event.sender_id,
        text=event.raw_text,
        message_date=event.message.date,
        is_reply=event.message.is_reply,
        reply_to_message_id=event.message.reply_to.msg_id
        if event.message.is_reply
        else None,
    )
    session.add(message)
    return message


async def store_message_from_event(
    session: Session, event: events.NewMessage.Event
) -> None:
    logging.info(f"Storing message {event.message.id} from chat {event.chat_id}")

    sender = await event.get_sender()

    user = _create_or_update_user(session, sender, event.sender_id)
    chat = _create_or_update_chat(session, event)
    _ensure_chat_member(session, user, chat)
    _create_message(session, event)

    logging.info(f"Message {event.message.id} stored successfully")


def get_recent_messages(
    session: Session, chat_id: int, limit: int = 50
) -> list[Message]:
    logging.info(f"Retrieving last {limit} messages for chat {chat_id}")

    messages = (
        session.query(Message)
        .filter(Message.chat_id == chat_id)
        .order_by(Message.message_date.desc())
        .limit(limit)
        .all()
    )

    logging.info(f"Retrieved {len(messages)} messages for chat {chat_id}")

    return list(reversed(messages))
