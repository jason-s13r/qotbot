# Telegram LLM Bot Re-architecture Plan

## Overview

Re-architect the telegram-llm-bot to replicate horsebot's behavior using:
- **FastMCP** for tool-based LLM interaction with Telegram
- **SQLite + SQLAlchemy** for persistence
- **Tool-driven output**: All bot messages sent via tools, not direct output
- **Session-based** conversation with debouncing and relevance classification

---

## Reference: Horsebot Features

From `/Users/jason/Documents/git/others/horsebot`:

| Feature | Description |
|---------|-------------|
| **Session-based context** | Messages linked to session with sliding window |
| **Debounce system** | 14-second default batching of rapid messages |
| **Relevance classifier** | Lightweight LLM decides when to respond |
| **Chunk summarization** | Compresses old messages into summaries |
| **Memory system** | Per-user persistent memories |
| **Permission system** | none/command/full per chat |
| **Media enrichment** | Vision for images, Whisper for voice |
| **Tool-based output** | LLM uses tools like `send_messages` |

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TELEGRAM_API_ID` | Telegram API ID | - |
| `TELEGRAM_API_HASH` | Telegram API Hash | - |
| `TELEGRAM_BOT_TOKEN` | BotFather token | - |
| `TELEGRAM_BOT_OWNER` | Admin user ID | - |
| `LLM_API_URL` | Open WebUI API URL | http://bazzite:3000/api |
| `LLM_API_KEY` | API key for LLM | - |
| `LLM_MODEL` | Main conversation model | qwen3.5:latest |
| `LLM_CLASSIFIER_MODEL` | Classifier model | qwen3.5:0.8b |
| `DATABASE_URL` | SQLite path | ./data/bot.db |
| `DEBOUNCE_MS` | Message batching delay | 14000 |
| `SESSION_TIMEOUT_MINUTES` | Session auto-close | 10 |
| `HISTORY_WINDOW` | Messages before chunking | 50 |

---

## Architecture

### High-Level Flow

```
Telegram Message (Telethon event)
  |
  v
Message Handler Pipeline
  |- Extract metadata (mention, reply)
  |- Media enrichment (images/voice)
  |- Permission check
  |- Command interception
  |- Persist to DB
  |- Route to session/classification
        |
        v
  Debounce Timer (per chat)
        |
        v
  Relevance Classifier (qwen3.5:0.8b)
        |
        v
  Build Session Prompt (chunks + history)
        |
        v
  LLM Tool Loop
        |- Call tools (send_messages, etc.)
        |- Persist responses
        |- Loop until stop_turn
```

### Component Structure

```
bot/
├── __init__.py
├── main.py                 # Entry point, event handlers
├── config.py               # Configuration/env vars
├── db/
│   ├── __init__.py
│   ├── base.py             # SQLAlchemy declarative base
│   ├── database.py         # Engine, sessionmaker
│   └── models/             # ORM models
│       ├── __init__.py
│       ├── user.py
│       ├── chat.py
│       ├── message.py
│       ├── session.py
│       ├── chunk.py
│       └── memory.py
├── handlers/
│   ├── __init__.py
│   ├── message.py          # Main message handler
│   ├── commands.py         # /help, /allow, etc.
│   └── media.py            # Image/voice enrichment
├── session/
│   ├── __init__.py
│   ├── manager.py          # Session lifecycle
│   ├── debounce.py         # Message batching
│   ├── classifier.py       # Relevance classification
│   ├── prompt.py           # Session prompt builder
│   └── chunks.py           # Chunk creation/summarization
├── llm/
│   ├── __init__.py
│   ├── client.py           # LLM API wrapper
│   └── tools.py            # Tool definitions
├── tools/                   # FastMCP tools for LLM
│   ├── __init__.py
│   ├── telegram.py          # send_message, send_poll, etc.
│   ├── memory.py            # save_memory, read_memory
│   ├── simple.py            # get_time, etc.
│   └── wolfram_alpha.py     # Existing
└── util/
    ├── __init__.py
    ├── prompts.py           # System prompts
    └── logging.py           # Logging config
```

---

## Database Schema (SQLite)

### Tables

```python
# users - Telegram users
User:
  - id: Integer (PK, autoincrement)
  - telegram_id: BigInteger (unique, not null)
  - username: String (nullable)
  - first_name: String (not null)
  - created_at: DateTime (default: now)

# chats - Telegram chats with permissions
Chat:
  - id: Integer (PK, autoincrement)
  - telegram_id: BigInteger (unique, not null)
  - title: String (nullable)
  - permission: String (default: "none")  # none/command/full
  - created_at: DateTime (default: now)

# messages - All messages
Message:
  - id: Integer (PK, autoincrement)
  - chat_id: Integer (FK -> Chat.id, not null)
  - user_id: Integer (FK -> User.id, not null)
  - session_id: Integer (FK -> ClaudeSession.id, nullable)
  - chunk_id: Integer (FK -> MessageChunk.id, nullable)
  - text: String (not null)
  - is_bot: Boolean (default: False)
  - created_at: DateTime (default: now)

# claude_sessions - Active conversation sessions
ClaudeSession:
  - id: Integer (PK, autoincrement)
  - chat_id: Integer (FK -> Chat.id, not null)
  - trigger_message_id: Integer (FK -> Message.id)
  - status: String (default: "active")  # active/closed
  - summary: String (nullable)  # Session summary on close
  - created_at: DateTime (default: now)
  - updated_at: DateTime (default: now)

# message_chunks - Compressed history summaries
MessageChunk:
  - id: Integer (PK, autoincrement)
  - chat_id: Integer (FK -> Chat.id, not null)
  - chunk_index: Integer (not null)
  - summary: String (not null)
  - message_start: Integer (not null)  # First message ID in chunk
  - message_end: Integer (not null)    # Last message ID in chunk
  - summarized_at: DateTime (default: now)

# memories - Per-user persistent facts
Memory:
  - id: Integer (PK, autoincrement)
  - user_id: Integer (FK -> User.id, not null)
  - content: String (not null)
  - created_at: DateTime (default: now)
  - updated_at: DateTime (default: now)
```

---

## FastMCP Tools

The LLM interacts with Telegram exclusively via tools.

### Core Telegram Tools

| Tool | Description |
|------|-------------|
| `send_message` | Send a message to the chat (markdown support) |
| `send_messages` | Send multiple messages (horsebot style) |
| `send_poll` | Create a poll in the chat |
| `send_sticker` | Send a sticker from registry |
| `stop_turn` | Required - ends Claude's turn |

### Memory Tools

| Tool | Description |
|------|-------------|
| `save_memory` | Save a persistent fact about a user |
| `read_memory` | Read saved memories for a user |

### Utility Tools

| Tool | Description |
|------|-------------|
| `get_time` | Get current time |
| `wolfram_alpha` | Existing Wolfram Alpha tool |

---

## Implementation Phases

### Phase 1: Database & Core Infrastructure

- [ ] Create SQLAlchemy models in `bot/db/models/`
- [ ] Set up database connection and session management
- [ ] Create database initialization
- [ ] Add user/chat persistence on message receipt

### Phase 2: Message Handling Pipeline

- [ ] Refactor `main.py` to use handler pipeline
- [ ] Implement permission system (none/command/full)
- [ ] Add command handling (/help, /allow, /stop)
- [ ] Implement basic message persistence

### Phase 3: Session & Debounce System

- [ ] Implement debounce timer per chat
- [ ] Create session management (create/close/timeout)
- [ ] Add message-to-session linking
- [ ] Implement 10-minute session timeout

### Phase 4: Relevance Classifier & Prompt Building

- [ ] Create classifier using `qwen3.5:0.8b`
- [ ] Implement prompt builder with:
  - System prompt
  - Chunk summaries
  - Recent messages (sliding window)
  - New messages batch
- [ ] Connect classifier to debounce flow

### Phase 5: Chunk System

- [ ] Implement chunk creation when HISTORY_WINDOW reached
- [ ] Add summarization using LLM
- [ ] Handle chunk selection for session prompts

### Phase 6: FastMCP Tool Refinement

- [ ] Restructure tools to be session-aware
- [ ] Add `send_messages` (multiple) support
- [ ] Add `stop_turn` tool (required)
- [ ] Ensure all output goes through tools

### Phase 7: Memory System

- [ ] Implement `save_memory` / `read_memory` tools
- [ ] Persist memories to database

### Phase 8: Media Enrichment (Optional/Future)

- [ ] Image handling with vision (qwen3.5 has vision)
- [ ] Voice transcription (Groq Whisper via Open WebUI)
- [ ] Sticker handling

---

## Key Design Decisions

### 1. Tool-Based Output

The LLM outputs messages **exclusively** via tools:
- System prompt: "NEVER output text directly - ALWAYS use send_message tool"
- `stop_turn` tool required at end of each turn

### 2. Log-Style Conversation

```
[2024-01-15 10:30:45] Alice: Hey, what's up?
[2024-01-15 10:30:47] Bob: Not much, you?
[2024-01-15 10:30:50] *Claude responds via send_message tool*
```

### 3. FastMCP Context Usage

Use FastMCP's `Context` for:
- Accessing database session
- Chat-specific state
- User permissions

```python
@mcp.tool()
async def send_message(text: str, ctx: Context) -> str:
    chat = await ctx.get("current_chat")
    # ... send to Telegram
```

### 4. SQLite with aiosqlite

- Use `aiosqlite` for async support with SQLAlchemy
- Store in `./data/bot.db`
- Run in container with volume mount for persistence
