# Qotbot

A Telegram bot with LLM integration for chat interactions, transcription, and more.

## Features

- **Chat Integration**: Responds to messages in Telegram chats using LLM
- **Voice Transcription**: Transcribes voice messages using Whisper
- **Commands**: `/bye`, `/enable`, `/disable`, `/transcript`, `/classification`, `/summary`
- **Tools**: Wolfram Alpha, web search, weather, LOLcryption, date/time tools, Telegram messaging tools
- **Database**: Stores messages and chat history in SQLite

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
- `LLM_CHAT_MODEL` - LLM model for chat (default: `qwen3.5:4b`)
- `LLM_CLASSIFIER_MODEL` - LLM model for classification (default: `qwen3.5:4b`)

Optional variables:
- `WEB_TIMEOUT` - HTTP request timeout in seconds (default: `20`)

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
│   └── summariser.py    # Chat summarisation
├── tools/               # MCP tools
│   ├── telegram.py      # Telegram provider
│   ├── web_tools.py     # Web search & weather
│   ├── lolcryption.py   # Encryption utilities
│   └── date_tools.py    # Date/time utilities
├── utils/               # Utilities
│   ├── whisper.py       # Whisper transcription
│   └── media.py         # Media handling
└── database/            # SQLite database models
```

## License

MIT
