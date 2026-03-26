import asyncio
import io
import logging
import os
import tempfile
from dataclasses import dataclass

import ffmpeg
import librosa
import whisper

from qotbot.database.database import get_session
from qotbot.database.messages import store_audio_transcription
from qotbot.utils.config import DATABASE_PATH, WHISPER_LANGUAGE, WHISPER_MODEL
from qotbot.workers.classification_worker import put_classification


@dataclass(order=True)
class AudioTask:
    chat_id: int
    message_id: int
    media_data: bytes
    ext: str | None = None


logger = logging.getLogger(__name__)
audio_queue: asyncio.Queue[AudioTask] = asyncio.Queue()
whisper_model = None


def _ffmpeg_extract_audio(
    input_bytes: bytes, ext: str | None, use_temp_file: bool = False
) -> io.BytesIO:
    filename = "pipe:0"
    try:
        if use_temp_file:
            with tempfile.NamedTemporaryFile(
                suffix=ext or ".webm", delete=False
            ) as input_file:
                input_file.write(input_bytes)
                filename = input_file.name
        out, _ = (
            ffmpeg.input(
                filename,
                format=ext.strip(".") if ext else "webm",
                probesize=5000000,
                analyzeduration=5000000,
            )
            .output(
                "pipe:1",
                format="wav",
                ac=1,
                acodec="pcm_s16le",
                ar="16000",
                vn=None,
            )
            .overwrite_output()
            .run(
                input=None if use_temp_file else input_bytes,
                capture_stdout=True,
                capture_stderr=True,
            )
        )
    except ffmpeg.Error as e:
        logger.error(
            f"ffmpeg error during audio extraction: {e.stderr.decode('utf-8') if e.stderr else str(e)}"
        )
        raise ValueError("Audio file is corrupted or invalid")
    finally:
        if use_temp_file and filename != "pipe:0":
            try:
                os.remove(filename)
            except Exception as e:
                logger.debug(f"Failed to remove temporary file {filename}: {e}")

    return io.BytesIO(out)


def _load_whisper_model():
    global whisper_model
    if whisper_model is None:
        logger.info(f"Loading Whisper model: {WHISPER_MODEL}")
        whisper_model = whisper.load_model(WHISPER_MODEL or "turbo")
        logger.info(f"Whisper model '{WHISPER_MODEL}' loaded successfully")
    return whisper_model


async def _transcribe_audio(audio_bytes: bytes, ext: str | None) -> str:
    loop = asyncio.get_running_loop()
    logger.info(f"Transcribing audio with Whisper, ext={ext}")

    def _transcribe():
        audio_buffer = _ffmpeg_extract_audio(audio_bytes, ext)

        audio, sr = librosa.load(audio_buffer, sr=None)
        if audio.size == 0 or len(audio) < sr * 0.1:
            audio_buffer = _ffmpeg_extract_audio(audio_bytes, ext, True)
            audio, sr = librosa.load(audio_buffer, sr=None)

        if audio.size == 0 or len(audio) < sr * 0.1:
            raise ValueError("Audio file is empty or too short")

        model = _load_whisper_model()
        return model.transcribe(audio, language=WHISPER_LANGUAGE, verbose=False)

    result = await loop.run_in_executor(None, _transcribe)
    text = result.get("text", "")
    if isinstance(text, str):
        text = text.strip()
    else:
        text = str(text).strip()
    logger.info(f"Audio transcription complete: {len(text)} characters")
    return text


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
    logger.debug(
        f"Processing audio transcription for message_id={item.message_id}, chat_id={item.chat_id}, ext={item.ext}"
    )

    transcription = await _transcribe_audio(item.media_data, item.ext)

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
