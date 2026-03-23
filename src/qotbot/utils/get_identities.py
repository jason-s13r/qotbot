from qotbot.database.database import get_session
from qotbot.database.models.chat import Chat


from telethon import TelegramClient

from qotbot.utils.config import BOT_NAME, DATABASE_PATH


async def get_bot_identity(bot: TelegramClient):
    bot_user = await bot.get_me()
    if not bot_user:
        return BOT_NAME

    first_name = bot_user.first_name or ""
    last_name = bot_user.last_name or ""

    information = ", ".join(
        filter(
            None,
            [
                f"{first_name} {last_name}".strip(),
                f"@{bot_user.username}" if bot_user.username else "",
                f"user_id: {bot_user.id}",
            ],
        )
    )

    return f"{BOT_NAME} ({information})"


async def get_chat_identity(chat_id: int):
    async with get_session() as session:
        chat = await session.get(Chat, chat_id)

        if not chat:
            return f"(chat_id: {chat_id})"

        return f"{chat.title} (chat_id: {chat_id})"


async def get_identities(bot: TelegramClient, chat_id: int):
    bot_identity = await get_bot_identity(bot)
    chat_identity: str = await get_chat_identity(chat_id)

    return bot_identity, chat_identity
