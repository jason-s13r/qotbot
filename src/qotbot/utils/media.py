import base64
import logging

from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
from telethon.tl.custom import Message

logger = logging.getLogger(__name__)


async def download_media_base64(
    message: Message,
) -> tuple[str | None, str | None]:
    """Download image or sticker from a Telegram message and convert to base64.

    Args:
        message: The Telegram message object

    Returns:
        Tuple of (mime_type, base64_data) or (None, None) if no image/sticker
    """
    media = message.media
    if not media:
        return None, None

    try:
        file_bytes = await message.download_media(bytes)
        if not file_bytes:
            return None, None
        mime_type = _get_mime_type(media)
        base64_encoded = base64.b64encode(file_bytes).decode("utf-8")
        return mime_type, base64_encoded
    except Exception as e:
        logger.error(f"Error downloading media: {e}")
        return None, None


def _get_mime_type(media) -> str:
    """Get the actual MIME type from the media object."""
    if isinstance(media, MessageMediaDocument) and media.document:
        return getattr(media.document, "mime_type", "image/jpeg")
    elif isinstance(media, MessageMediaPhoto):
        return "image/jpeg"
    return "image/jpeg"
