import logging
from telethon import TelegramClient
from sqlalchemy.orm import Session

from qotbot.database.models.user import User


logger = logging.getLogger(__name__)


async def create_or_update_bot_user(session: Session, bot: TelegramClient) -> User:
    """
    Fetch the bot's own user info via get_me() and create or update the User record.
    """
    me = await bot.get_me()

    user = session.get(User, me.id)
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
