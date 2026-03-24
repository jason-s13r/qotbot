from dataclasses import dataclass

from qotbot.database.database import get_session
from qotbot.database.messages import store_audio_transcription
from qotbot.utils.config import DATABASE_PATH
from qotbot.utils.whisper import WhisperService
from qotbot.workers.classification_worker import put_classification
import logging
import asyncio


@dataclass(order=True)
class AudioTask:
    chat_id: int
    message_id: int
    media_data: bytes
    ext: str | None = None


logger = logging.getLogger(__name__)
audio_queue: asyncio.Queue[AudioTask] = asyncio.Queue()
whisper_service: WhisperService | None = None


def put_audio(
    chat_id: int,
    message_id: int,
    media_data: bytes,
    ext: str | None = None,
):
    audio_queue.put_nowait(AudioTask(chat_id, message_id, media_data, ext))
    logger.debug(
        f"Audio task queued: chat_id={chat_id}, message_id={message_id}, ext={ext}"
    )


async def _process_audio_item(item: AudioTask):
    global whisper_service
    logger.debug(
        f"Processing audio transcription for message_id={item.message_id}, chat_id={item.chat_id}, ext={item.ext}"
    )

    if not whisper_service:
        logger.info("Initialising WhisperService")
        whisper_service = WhisperService()

    transcription = await whisper_service.transcribe(item.media_data, item.ext)

    if not transcription:
        transcription = "No transcription generated"

    async with get_session() as session:
        await store_audio_transcription(
            session, item.message_id, item.chat_id, transcription
        )
        await session.commit()

    logger.info(f"Audio transcription stored for message_id={item.message_id}")

    put_classification(item.chat_id, item.message_id)


async def audio_worker():
    logger.info("Audio worker started")
    while True:
        try:
            item = await asyncio.wait_for(audio_queue.get(), timeout=1.0)
            logger.debug(
                f"Dequeued audio task: chat_id={item.chat_id}, message_id={item.message_id}"
            )

            await _process_audio_item(item)
        except asyncio.TimeoutError:
            await asyncio.sleep(0.1)
            continue
        except Exception as e:
            logger.error(
                f"Audio worker error: {e}",
                exc_info=True,
            )
