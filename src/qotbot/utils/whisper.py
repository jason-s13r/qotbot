import asyncio
import io
import logging

import librosa
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

        logger.debug(f"Transcribing audio with Whisper ({self.model_name})")

        def _transcribe():
            # Quick validation: check audio bytes are not empty
            if len(audio_bytes) == 0:
                raise ValueError("Audio file is empty")

            # Load audio from bytes to validate it has content
            audio_buffer = io.BytesIO(audio_bytes)
            audio, sr = librosa.load(audio_buffer, sr=None)
            if audio.size == 0 or len(audio) < sr * 0.1:
                raise ValueError("Audio file is empty or too short")

            return self.model.transcribe(audio, language=language, verbose=False)

        result = await loop.run_in_executor(None, _transcribe)
        text = result["text"].strip()
        logger.debug(f"Transcription complete: {len(text)} characters")
        return text
