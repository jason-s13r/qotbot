import logging
import uuid
from fastmcp.resources import FileResource, ResourceContent, ResourceResult
import soundfile as sf
from kokoro_onnx import Kokoro
from fastmcp import FastMCP

from qotbot.utils.config import TEMP_FILES_PATH, TTS_MODELS_PATH

logger = logging.getLogger(__name__)

tts_tool = FastMCP("Text to Speech")

_kokoro_model: Kokoro | None = None


def _load_kokoro_model():
    global _kokoro_model
    if _kokoro_model is None:
        _kokoro_model = Kokoro(
            TTS_MODELS_PATH / "kokoro-v1.0.onnx", TTS_MODELS_PATH / "voices-v1.0.bin"
        )
    return _kokoro_model


@tts_tool.resource(
    "audio://speech/{name}", mime_type="audio/ogg", meta={"file_name": "audio.ogg"}
)
def get_speech_audio(name: str) -> ResourceResult:
    """
    Get the generated speech audio as a resource. Used in other tools.
    """
    file_name = TEMP_FILES_PATH / name
    with open(file_name, "rb") as f:
        blob = f.read()

        resource = ResourceResult(
            contents=[
                ResourceContent(
                    content=blob,
                    meta={"file_name": file_name.name},
                )
            ],
            meta={"file_name": file_name.name},
        )

        return resource


@tts_tool.tool
def generate_speech(
    text: str,
    voice: str = "af_nicole",
    speed: float = 1.0,
):
    """
    Generate speech audio from text using Kokoro TTS.

    Args:
        text: The text to convert to speech
        voice: Voice ID to use (e.g., "af_nicole", "af_sarah", "am_adam", "am_michael")
        speed: Speech speed multiplier (1.0 = normal, 0.5 = half speed, 2.0 = double speed)

    Returns:
        A resource URI pointing to the generated speech audio file. For use in other tools.
    """
    model = _load_kokoro_model()

    audio_array, sample_rate = model.create(text, voice=voice, speed=speed)

    file_id = str(uuid.uuid4())
    file_name = f"speech_{file_id}.ogg"

    sf.write(
        TEMP_FILES_PATH / file_name,
        audio_array,
        sample_rate,
        format="OGG",
        subtype="OPUS",
    )

    return {"resource_uri": f"audio://speech/{file_name}"}


if __name__ == "__main__":
    tts_tool.run()
