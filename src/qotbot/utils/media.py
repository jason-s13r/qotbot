import base64
import logging

from telethon.tl.custom import Message

logger = logging.getLogger(__name__)


async def download_media_base64(message: Message) -> str | None:
    media = message.media
    if not media:
        return None

    try:
        file_bytes = await message.download_media(bytes)
        if not file_bytes:
            return None
        return base64.b64encode(file_bytes).decode("utf-8")
    except Exception as e:
        logger.error(
            f"Error downloading media from message_id={message.id}: {e}", exc_info=True
        )
        return None
