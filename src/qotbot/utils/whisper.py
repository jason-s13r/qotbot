import asyncio
import logging
import tempfile
from pathlib import Path

import whisper

logger = logging.getLogger(__name__)


class WhisperService:
    """Self-hosted Whisper speech-to-text service."""

    def __init__(self, model_name: str = "turbo"):
        """Initialize Whisper model.

        Args:
            model_name: Whisper model size (tiny, base, small, medium, large, turbo)
        """
        logger.info(f"Loading Whisper model: {model_name}")
        self.model_name = model_name
        self.model = whisper.load_model(model_name)
        logger.info(f"Whisper model loaded successfully")

    async def transcribe(self, audio_bytes: bytes, language: str | None = None) -> str:
        """Transcribe audio bytes to text.

        Args:
            audio_bytes: Raw audio data
            language: Optional language code (e.g., 'en', 'ja'). None for auto-detect.

        Returns:
            Transcribed text
        """
        loop = asyncio.get_running_loop()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            temp_path = f.name

        try:
            logger.debug(f"Transcribing audio with Whisper ({self.model_name})")

            def _transcribe():
                return self.model.transcribe(
                    temp_path, language=language if language else None, verbose=False
                )

            result = await loop.run_in_executor(None, _transcribe)
            text = result["text"].strip()
            logger.debug(f"Transcription complete: {len(text)} characters")
            return text

        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}", exc_info=True)
            raise
        finally:
            Path(temp_path).unlink(missing_ok=True)
