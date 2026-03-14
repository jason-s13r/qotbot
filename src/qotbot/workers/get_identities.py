from qotbot.database.database import get_session
from qotbot.database.models.chat import Chat


from telethon import TelegramClient


async def get_identities(
    bot: TelegramClient, chat_id: int, bot_name: str, database_path: str
):
    bot_user = await bot.get_me()
    bot_identity = (
        f"{bot_name} ({bot_user.first_name} {bot_user.last_name}, @{bot_user.username}, user_id: {bot_user.id})"
    )
    chat_identity: str = f"(chat_id: {chat_id})"

    async with get_session(database_path) as session:
        chat = await session.get(Chat, chat_id)
        if chat:
            chat_identity = f"{chat.title} (chat_id: {chat_id})"

    return bot_identity, chat_identity
