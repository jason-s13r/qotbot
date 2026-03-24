import asyncio
import io
import logging
import os
import tempfile
import ffmpeg
import librosa
import whisper

from qotbot.utils.config import WHISPER_LANGUAGE, WHISPER_MODEL

logger = logging.getLogger(__name__)


def _ffmpeg_extract_audio(
    input_bytes: bytes, ext: str, use_temp_file: bool = False
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
                format=ext.strip("."),
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


class WhisperService:
    """Self-hosted Whisper speech-to-text service."""

    def __init__(self):
        """Initialize Whisper model.

        Args:
            model_name: Whisper model size (tiny, base, small, medium, large, turbo)
        """
        logger.info(f"Loading Whisper model: {WHISPER_MODEL}")
        self.model_name = WHISPER_MODEL
        self.model = whisper.load_model(WHISPER_MODEL or "turbo")
        logger.info(f"Whisper model '{WHISPER_MODEL}' loaded successfully")

    async def transcribe(self, audio_bytes: bytes, ext: str | None = None) -> str:
        loop = asyncio.get_running_loop()
        logger.info(f"Transcribing audio with Whisper ({self.model_name}), ext={ext}")

        def _transcribe():
            audio_buffer = _ffmpeg_extract_audio(audio_bytes, ext)

            audio, sr = librosa.load(audio_buffer, sr=None)
            if audio.size == 0 or len(audio) < sr * 0.1:
                audio_buffer = _ffmpeg_extract_audio(audio_bytes, ext, True)
                audio, sr = librosa.load(audio_buffer, sr=None)

            if audio.size == 0 or len(audio) < sr * 0.1:
                raise ValueError("Audio file is empty or too short")

            return self.model.transcribe(
                audio, language=WHISPER_LANGUAGE, verbose=False
            )

        result = await loop.run_in_executor(None, _transcribe)
        text = result.get("text", "")
        if isinstance(text, str):
            text = text.strip()
        else:
            text = str(text).strip()
        logger.info(f"Audio transcription complete: {len(text)} characters")
        return text
