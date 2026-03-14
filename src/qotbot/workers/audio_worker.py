from qotbot.database.database import get_session
from qotbot.database.messages import store_audio_transcription
from qotbot.utils.whisper import WhisperService
from qotbot.workers.classification_worker import put_classification
import logging
import asyncio
import time

from qotbot.workers.PriorityItem import PriorityItem

logger = logging.getLogger(__name__)

audio_queue: asyncio.PriorityQueue[PriorityItem] = asyncio.PriorityQueue()

whisper_service: WhisperService | None = None


async def put_audio(
    chat_id: int,
    message_id: int,
    audio_bytes: bytes,
    priority: int = 0,
):
    item = {
        "chat_id": chat_id,
        "message_id": message_id,
        "audio_bytes": audio_bytes,
    }
    await audio_queue.put(PriorityItem(priority, time.time(), item))
    logger.debug(f"Audio queued: chat={chat_id}, msg={message_id}")


async def audio_worker(
    database_path: str,
    whisper_language: str | None = None,
    whisper_model: str = "turbo",
):
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
        audio_bytes = item["audio_bytes"]

        try:
            logger.info(f"Processing audio {message_id} in chat {chat_id}")

            if not whisper_service:
                whisper_service = WhisperService(whisper_model)

            transcription = await whisper_service.transcribe(
                audio_bytes, language=whisper_language
            )

            if not transcription:
                transcription = "No transcription generated"

            async with get_session(database_path) as session:
                await store_audio_transcription(
                    session, message_id, chat_id, transcription
                )
                await session.commit()

            logger.info(f"Audio transcription stored for message {message_id}")

            await put_classification(chat_id, message_id, priority_item.priority)

        except Exception as e:
            logger.error(f"Audio worker error: {e}", exc_info=True)
            await put_audio(
                chat_id,
                message_id,
                audio_bytes,
                priority_item.priority + 1,
            )
            logger.info(f"Re-queued audio {message_id} with increased priority")
