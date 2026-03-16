from qotbot.database.database import get_session
from qotbot.database.messages import store_audio_transcription
from qotbot.utils.config import DATABASE_PATH
from qotbot.utils.whisper import WhisperService
from qotbot.workers.classification_worker import put_classification
import logging
import asyncio
import time

from qotbot.workers.models.PriorityItem import PriorityItem

logger = logging.getLogger(__name__)

audio_queue: asyncio.PriorityQueue[PriorityItem] = asyncio.PriorityQueue()
whisper_service: WhisperService | None = None


async def put_audio(
    chat_id: int,
    message_id: int,
    media_bytes: bytes,
    priority: int = 0,
    ext: str | None = None,
):
    item = {
        "chat_id": chat_id,
        "message_id": message_id,
        "media_bytes": media_bytes,
        "ext": ext,
    }
    await audio_queue.put(PriorityItem(priority, time.time(), item))
    logger.debug(
        f"Audio queued: chat={chat_id}, msg={message_id}, ext={ext}"
    )


async def audio_worker():
    global whisper_service
    logger.info("Audio worker started")
    while True:
        try:
            priority_item = await asyncio.wait_for(audio_queue.get(), timeout=1.0)
        except asyncio.TimeoutError:
            await asyncio.sleep(0.1)
            continue

        item = priority_item.item
        chat_id = item["chat_id"]
        message_id = item["message_id"]
        media_bytes = item["media_bytes"]
        ext = item.get("ext", None)

        try:
            logger.info(
                f"Processing audio {message_id} in chat {chat_id} (ext={ext})"
            )

            if not whisper_service:
                whisper_service = WhisperService()

            transcription = await whisper_service.transcribe(media_bytes, ext)

            if not transcription:
                transcription = "No transcription generated"

            async with get_session(DATABASE_PATH) as session:
                await store_audio_transcription(
                    session, message_id, chat_id, transcription
                )
                await session.commit()

            logger.info(f"Audio transcription stored for message {message_id}")

            await put_classification(chat_id, message_id, priority_item.priority)

        except Exception as e:
            logger.error(f"Audio worker error: {e}", exc_info=True)
