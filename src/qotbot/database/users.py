import logging
from telethon import TelegramClient, events
from sqlalchemy.ext.asyncio import AsyncSession

from qotbot.database.models.user import User


logger = logging.getLogger(__name__)


async def create_or_update_bot_user(session: AsyncSession, bot: TelegramClient) -> User:
    """
    Fetch the bot's own user info via get_me() and create or update the User record.
    """
    me = await bot.get_me()

    user = await session.get(User, me.id)
    if not user:
        user = User(
            id=me.id,
            username=me.username,
            first_name=me.first_name,
            last_name=me.last_name,
            is_bot=me.bot,
        )
        session.add(user)
        logger.info(f"Created bot user {me.id}")
    else:
        user.username = me.username
        user.first_name = me.first_name
        user.last_name = me.last_name
        user.is_bot = me.bot
        logger.info(f"Updated bot user {me.id}")

    return user


async def create_or_update_user_from_event(
    session: AsyncSession, event: events.NewMessage.Event
) -> User:
    """
    Create or update a User record from the event sender.
    """
    sender = await event.get_sender()
    if not sender:
        logger.warning(f"No sender found for event {event.id}")
        return None

    user = await session.get(User, sender.id)
    if not user:
        user = User(
            id=sender.id,
            username=getattr(sender, "username", None),
            first_name=getattr(sender, "first_name", None),
            last_name=getattr(sender, "last_name", None),
            is_bot=getattr(sender, "bot", False),
        )
        session.add(user)
        logger.info(f"Created user {sender.id}")
    else:
        user.username = getattr(sender, "username", user.username)
        user.first_name = getattr(sender, "first_name", user.first_name)
        user.last_name = getattr(sender, "last_name", user.last_name)
        user.is_bot = getattr(sender, "bot", user.is_bot)
        logger.info(f"Updated user {sender.id}")

    return user
