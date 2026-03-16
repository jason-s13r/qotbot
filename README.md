# Qotbot

A Telegram bot with LLM integration for chat interactions, transcription, and more.

## Features

- **Chat Integration**: Responds to messages in Telegram chats using LLM
- **Voice Transcription**: Transcribes voice/audio messages using Whisper
- **Image Description**: Describes images and stickers using vision models
- **Message Classification**: Classifies messages to determine response priority
- **Chat Summarisation**: Generates summaries of chat conversations
- **Commands**: `/bye`, `/enable`, `/disable`, `/transcript`, `/classification`, `/summary`
- **Tools**: Wolfram Alpha, web search, weather, LOLcryption, date/time tools, Telegram messaging tools
- **Database**: Stores messages, chats, users, and summaries in SQLite
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
- `MAX_TRANSCRIPT_DURATION` - Maximum audio duration in seconds for transcription (default: `120`)
- `MAX_BATCH_SIZE` - Maximum batch size for response worker (default: `10`)
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

## Docker

Build and run with Docker:

```bash
docker build -t qotbot .
docker run --env-file .env qotbot
```

## Project Structure

```
src/qotbot/
├── __main__.py          # Bot entry point
├── llm/                 # LLM integration
│   ├── agent.py         # Base agent
│   ├── chatter.py       # Chat responses
│   ├── classifier.py    # Message classification
│   ├── summariser.py    # Chat summarisation
│   └── image_describer.py  # Image description
├── tools/               # MCP tools
│   ├── telegram.py      # Telegram provider
│   ├── web_tools.py     # Web search & weather
│   ├── lolcryption.py   # Encryption utilities
│   ├── date_tools.py    # Date/time utilities
│   └── classification_tools.py  # Message classification
├── utils/               # Utilities
│   ├── whisper.py       # Whisper transcription
│   ├── media.py         # Media handling
│   ├── config.py        # Configuration
│   └── build_common_prompts.py  # Prompt formatting
├── workers/             # Async workers
│   ├── audio_worker.py  # Audio transcription worker
│   ├── image_worker.py  # Image description worker
│   ├── classification_worker.py  # Message classification worker
│   ├── response_worker.py  # Response generation worker
│   └── models/          # Worker models
├── database/            # SQLite database
│   ├── database.py      # Database setup
│   ├── messages.py      # Message storage
│   ├── chats.py         # Chat storage
│   ├── users.py         # User storage
│   └── models/          # SQLAlchemy models
└── __init__.py
```

## License

MIT
