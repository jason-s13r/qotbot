# Qotbot

A Telegram bot with LLM integration for chat interactions, transcription, and more.

## Features

- **Chat Integration**: Responds to messages in Telegram chats using LLM
- **Voice Transcription**: Transcribes voice/audio messages using Whisper
- **Image Description**: Describes images and stickers using vision models
- **Message Classification**: Classifies messages to determine response priority
- **Chat Summarisation**: Generates summaries of chat conversations
- **Commands**: `/help`, `/enable`, `/disable`, `/summary`, `/rules`, and admin commands
- **Tools**: Web search, weather, TODO management, logs viewer, LOLcryption, date/time tools, Telegram messaging tools
- **Database**: Stores messages, chats, users, summaries, rules, and TODOs in SQLite
- **Async Workers**: Separate workers for audio transcription, image description, classification, and responses

## Requirements

- Python 3.13+
- Telegram API credentials
- LLM API access (Ollama, OpenAI, or Anthropic)
- ffmpeg (for Whisper transcription)

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/jason-s13r/qotbot.git
cd qotbot
```

### 2. Configure environment variables

Copy `sample.env` to `.env` and fill in your credentials:

```bash
cp sample.env .env
```

Required variables:
- `TELEGRAM_API_ID` - Your Telegram API ID
- `TELEGRAM_API_HASH` - Your Telegram API hash
- `TELEGRAM_BOT_TOKEN` - Your Telegram bot token
- `TELEGRAM_BOT_OWNER` - Telegram user ID of the bot owner
- `LLM_API_URL` - LLM API endpoint (default: `http://localhost:11434`)
- `LLM_API_KEY` - LLM API key

Optional variables:
- `LLM_CHAT_MODEL` - LLM model for chat responses (default: `qwen3.5:4b`)
- `LLM_CLASSIFIER_MODEL` - LLM model for message classification (default: `qwen3.5:4b`)
- `LLM_SUMMARY_MODEL` - LLM model for chat summarisation (default: `qwen3.5:4b`)
- `LLM_VISION_MODEL` - LLM model for image description (default: `qwen3.5:4b`)
- `WHISPER_MODEL` - Whisper model for audio transcription (default: `turbo`)
- `WHISPER_LANGUAGE` - Language code for Whisper (default: auto-detect)
- `WEB_TIMEOUT` - HTTP request timeout in seconds (default: `20`)
- `MAX_TRANSCRIPT_DURATION` - Maximum audio duration in seconds for transcription (default: `300`)
- `DATA_PATH` - Path for database and logs (default: `./data`)

### 3. Install dependencies

Using uv (recommended):

```bash
uv sync
```

### 4. Run the bot

```bash
uv run --env-file .env qotbot
```

## Container

Build and run with Podman or Docker:

```bash
# build container image:
podman build -t qotbot .

# run container:
podman run --replace \
           --detach \
           --restart unless-stopped \
           --name "qotbot" \
           --env-file=".env" \
           -v qotbot-data:/app/data:z \
           --tmpfs /app/data/temp:size=5g \
           -it qotbot
```

## License

MIT
