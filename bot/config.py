import os
from pathlib import Path

# Telegram Configuration
TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_BOT_OWNER = int(os.getenv("TELEGRAM_BOT_OWNER", "0"))

# LLM Configuration
LLM_API_URL = os.getenv("LLM_API_URL", "http://localhost:3000/api")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3.5:latest")
LLM_CLASSIFIER_MODEL = os.getenv("LLM_CLASSIFIER_MODEL", "qwen3.5:0.8b")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "")

# Runtime model configuration (can be changed via commands)
_runtime_config = {
    "classifier_model": LLM_CLASSIFIER_MODEL,
    "chat_model": LLM_MODEL,
}


def get_classifier_model() -> str:
    """Get the current classifier model."""
    return _runtime_config["classifier_model"]


def get_chat_model() -> str:
    """Get the current chat model."""
    return _runtime_config["chat_model"]


def set_classifier_model(model: str):
    """Set the classifier model."""
    global _runtime_config
    _runtime_config["classifier_model"] = model


def set_chat_model(model: str):
    """Set the chat model."""
    global _runtime_config
    _runtime_config["chat_model"] = model


# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/bot.db")
DATA_PATH = Path(os.getenv("DATA_PATH", "./data"))

# Bot Behavior Configuration
DEBOUNCE_MS = int(os.getenv("DEBOUNCE_MS", "14000"))
SESSION_TIMEOUT_MINUTES = int(os.getenv("SESSION_TIMEOUT_MINUTES", "10"))
HISTORY_WINDOW = int(os.getenv("HISTORY_WINDOW", "50"))

# Bot Identity (optional - defaults to bot's Telegram profile)
BOT_NAMES = os.getenv("BOT_NAMES", "")  # Comma-separated alternative names
if BOT_NAMES:
    BOT_NAMES = [name.strip().lower() for name in BOT_NAMES.split(",")]
else:
    BOT_NAMES = []

# Response Configuration
RESPONSE_MODE = os.getenv("RESPONSE_MODE", "active")  # active, passive, random
RANDOM_RESPONSE_CHANCE = float(os.getenv("RANDOM_RESPONSE_CHANCE", "0.0"))  # 0.0-1.0

# Permission Configuration
DEFAULT_PERMISSION = os.getenv("DEFAULT_PERMISSION", "none")  # none, command, full

# Memory Configuration
ENABLE_MEMORY = os.getenv("ENABLE_MEMORY", "true").lower() == "true"

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")  # DEBUG, INFO, WARNING, ERROR

# Throttle Configuration
THROTTLE_SECONDS = int(os.getenv("THROTTLE_SECONDS", "2"))
