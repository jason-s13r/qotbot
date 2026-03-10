import logging
import os
import tempfile
from telethon import TelegramClient
from telethon.tl.types import (
    Message,
    MessageMediaPhoto,
    MessageMediaDocument,
    DocumentAttributeSticker,
)

logger = logging.getLogger(__name__)


async def download_media_to_base64(
    client: TelegramClient,
    message: Message,
) -> tuple[str, str] | None:
    """
    Download media from a Telegram message and return as base64.

    Returns:
        tuple of (media_type, base64_data) or None if no media found
        media_type is one of: 'photo', 'sticker', 'document'
    """
    if not message.media:
        return None

    try:
        if isinstance(message.media, MessageMediaPhoto):
            logger.debug("Downloading photo")
            file_path = await _download_media(client, message)
            if file_path:
                base64_data = _file_to_base64(file_path)
                os.remove(file_path)
                return ("photo", base64_data)

        elif isinstance(message.media, MessageMediaDocument):
            doc = message.media.document
            if not doc:
                return None

            is_sticker = any(
                isinstance(attr, DocumentAttributeSticker) for attr in doc.attributes
            )

            if is_sticker:
                logger.debug("Downloading sticker")
                file_path = await _download_media(client, message)
                if file_path:
                    base64_data = _file_to_base64(file_path)
                    os.remove(file_path)
                    return ("sticker", base64_data)
            else:
                logger.debug(f"Skipping document (mime_type={doc.mime_type})")
                return None

        return None

    except Exception as e:
        logger.error(f"Error downloading media: {e}", exc_info=True)
        return None


async def _download_media(
    client: TelegramClient,
    message: Message,
) -> str | None:
    """Download media to a temporary file and return the path."""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            file_path = tmp.name

        await client.download_media(message, file=file_path)
        logger.debug(f"Media downloaded to {file_path}")
        return file_path

    except Exception as e:
        logger.error(f"Error saving media to temp file: {e}", exc_info=True)
        try:
            if "file_path" in locals() and os.path.exists(file_path):
                os.remove(file_path)
        except:
            pass
        return None


def _file_to_base64(file_path: str) -> str:
    """Convert a file to base64 string."""
    import base64

    with open(file_path, "rb") as f:
        file_data = f.read()
        base64_data = base64.b64encode(file_data).decode("utf-8")
        return base64_data
