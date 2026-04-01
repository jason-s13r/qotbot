import os
from pathlib import Path

# Bot identity
BOT_NAME = os.getenv("BOT_NAME", "qotbot")

# LLM models
LLM_CHAT_MODEL = os.getenv("LLM_CHAT_MODEL", "qwen3.5:4b")
LLM_CLASSIFIER_MODEL = os.getenv("LLM_CLASSIFIER_MODEL", "qwen3.5:4b")
LLM_SUMMARY_MODEL = os.getenv("LLM_SUMMARY_MODEL", "qwen3.5:4b")
LLM_VISION_MODEL = os.getenv("LLM_VISION_MODEL", "qwen3.5:4b")

# Whisper models
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "turbo")
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", None)
MAX_TRANSCRIPT_DURATION = int(os.getenv("MAX_TRANSCRIPT_DURATION", 300))

# Data paths
DATA_PATH = Path(os.getenv("DATA_PATH", "./data"))
DATABASE_PATH = DATA_PATH / "database.db"
LOGS_DB_PATH = DATA_PATH / "logs.db"
LOG_PATH = DATA_PATH / "logs"
TTS_MODELS_PATH = DATA_PATH / "models"
TEMP_FILES_PATH = Path(os.getenv("TEMP_FILES_PATH", "./data/temp"))

# Telegram
TELEGRAM_BOT_OWNER = int(os.getenv("TELEGRAM_BOT_OWNER", 0))

# Web tools
WEB_TIMEOUT = int(os.getenv("WEB_TIMEOUT", 20))

# Create necessary directories if they don't exist
DATA_PATH.mkdir(parents=True, exist_ok=True)
LOG_PATH.mkdir(parents=True, exist_ok=True)
TTS_MODELS_PATH.mkdir(parents=True, exist_ok=True)
TEMP_FILES_PATH.mkdir(parents=True, exist_ok=True)