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

# Data paths
DATA_PATH = Path(os.getenv("DATA_PATH", "./data"))
DATABASE_PATH = DATA_PATH / "database.db"
LOG_PATH = DATA_PATH / "logs"

# Telegram
TELEGRAM_BOT_OWNER = int(os.getenv("TELEGRAM_BOT_OWNER", 0))

# Response worker config
MAX_BATCH_SIZE = int(os.getenv("MAX_BATCH_SIZE", 5))
MAX_RESPONSE_QUEUE_SIZE = int(os.getenv("MAX_RESPONSE_QUEUE_SIZE", 20))
RESPONSE_WAIT_TIME = int(os.getenv("RESPONSE_WAIT_TIME", 30))

# Web tools
WEB_TIMEOUT = int(os.getenv("WEB_TIMEOUT", 20))
MAX_TRANSCRIPT_DURATION = int(os.getenv("MAX_TRANSCRIPT_DURATION", 120))
