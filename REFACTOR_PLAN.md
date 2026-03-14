# Message Processing Pipeline Refactor

## Overview

Refactor the inline message processing into a **queued, staged processing pipeline** with the following stages:

1. **Store message in DB** - Mark as unprocessed, set media flags
2. **Extract transcriptions** - Audio → Whisper, Image → ImageDescriber
3. **Classify** - Determine if response is needed
4. **Generate response** - Batched (1-3 messages), throttled, Chatter sends via tools

---

## Architecture Flow

```
handle_incoming_message(event)
  ↓
Store in DB (processed=False, flags set, queue_status='pending')
  ↓
Download media (main thread - Telethon requirement)
  ├─ audio → temp file → audio_queue
  └─ image → base64 → image_queue
  ↓
No media → classification_queue

transcription_workers (asyncio.to_thread for Whisper)
  ↓
Update DB → classification_queue

classification_worker
  ↓
Classifier → approve_message tool → response_queue.put()

response_worker (batch 1-3)
  ↓
Query DB for context → Chatter → send via tools → DB responded=True
```

---

## Database Schema Changes

### Message Model (`database/models/message.py`)

**New columns added:**
- `processed: bool` - General processing flag
- `audio_transcribed: bool` - Audio transcription complete
- `image_transcribed: bool` - Image transcription complete
- `classified: bool` - Classification complete
- `responded: bool` - Response sent
- `skip_reason: str | None` - Skip reason for any stage
- `queue_status: str | None` - 'pending', 'transcribing', 'classifying', 'responding', 'complete', 'skipped'

---

## Queue Architecture

### 4 Queues

| Queue | Purpose |
|-------|---------|
| `image_queue` | Image transcription jobs |
| `audio_queue` | Audio transcription jobs |
| `classification_queue` | Classification jobs |
| `response_queue` | Response generation jobs |

### Queue Item Structure

```python
{
    'chat_id': int,
    'message_id': int,
    'temp_path': str | None,      # Audio: OS temp file path
    'base64_data': str | None,    # Image: in-memory base64
    'age_minutes': float,         # For skip logic
}
```

---

## Worker Flow

| Worker | Input Queue | Action | Output Queue |
|--------|-------------|--------|--------------|
| `image_worker` | `image_queue` | ImageDescriber → Update DB | `classification_queue` |
| `audio_worker` | `audio_queue` | Whisper (via `asyncio.to_thread`) → Update DB | `classification_queue` |
| `classification_worker` | `classification_queue` | Classifier → Update DB | `response_queue` (via `approve_message` tool) |
| `response_worker` | `response_queue` | Batch 1-3 → Chatter → Send | Terminal |

---

## Error Handling Strategy

| Condition | Action |
|-----------|--------|
| Age < 30min | Re-queue on failure |
| Age >= 30min | Skip with `skip_reason`, mark `queue_status='skipped'` |

---

## Completed Work

| Component | Status | Details |
|-----------|--------|---------|
| `Message` model | ✅ Complete | Added 7 new columns |
| `database.py` | ✅ Complete | Migrated to async (`create_async_engine`, `async_sessionmaker`, `aiosqlite`) |
| `workers/` dir | ✅ Created | Empty package ready for worker modules |

---

## Remaining Work

### 1. Database Module Async Migration

| File | Current | Needed |
|------|---------|--------|
| `database/messages.py` | Sync `Session` | Async `AsyncSession`, `await session.execute(select(...))`, `async with` context managers |
| `database/chats.py` | Sync `Session` | Same async pattern |
| `database/users.py` | Sync `Session` | Same async pattern |

### 2. New LLM Module

| File | Purpose |
|------|---------|
| `llm/image_describer.py` | Vision agent for image/sticker description (extracted from Classifier) |

### 3. Worker Modules

| File | Purpose |
|------|---------|
| `workers/__init__.py` | Package init, queue exports |
| `workers/queue_manager.py` | Define 4 queues + worker orchestration |
| `workers/transcription.py` | `image_worker`, `audio_worker` |
| `workers/classification.py` | `classification_worker` |
| `workers/response.py` | `response_worker` with batching logic |

### 4. Refactor Existing Modules

| File | Change |
|------|--------|
| `tools/telegram.py` | Accept `client + chat_id` instead of `event` |
| `__main__.py` | Handler enqueue logic, worker startup via `asyncio.gather()`, remove inline Chatter calls |

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Async SQLAlchemy | Non-blocking DB access for concurrent workers |
| `asyncio.to_thread()` | Offload CPU-heavy Whisper without blocking event loop |
| Separate queues per stage | Clear flow control, independent error handling |
| Download in handler | Telethon must stay in main event loop |
| Hybrid storage (temp file vs base64) | Audio can be large (files), images smaller (memory) |
| Batch 1-3 messages | Chatter controls pacing via message chunking |

---

## Implementation Order

1. **Database async migration** (`messages.py`, `chats.py`, `users.py`)
2. **ImageDescriber agent** (`llm/image_describer.py`)
3. **Worker modules** (`workers/__init__.py`, `queue_manager.py`, `transcription.py`, `classification.py`, `response.py`)
4. **TelegramProvider refactor** (`tools/telegram.py`)
5. **Main handler refactor** (`__main__.py`)

---

## Pattern Changes: Sync → Async SQLAlchemy

### Before (Sync)
```python
from sqlalchemy.orm import Session

with Session() as session:
    message = session.get(Message, (chat_id, message_id))
    message.audio_transcription = result
    session.commit()
```

### After (Async)
```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

async with async_session() as session:
    message = await session.get(Message, (chat_id, message_id))
    message.audio_transcription = result
    await session.commit()
```

### Query Pattern Change
```python
# Before
results = session.query(Message).filter(...).all()

# After
result = await session.execute(select(Message).filter(...))
results = result.scalars().all()
```

---

## Prompt Enhancement: `<new_messages>` Format

### Current
```xml
<new_messages>
<message sender_id={id} sender_name={name}>
{text}
[Image: {description}]
[Audio: {transcription}]
</message>
</new_messages>
```

### Enhanced
```xml
<new_messages>
<message id={msg_id} sender_id={id} sender_name={name} timestamp={iso_datetime} reply_to={reply_to_id|None}>
{text}
[Image: {description}]
[Audio: {transcription}]
</message>
</new_messages>
```

---

## Classification Tool Change

### Current (Inline)
```python
@classifier_tools.tool
async def approve_message(reason: str):
    chat_result = await chatter.invoke(...)  # Inline invoke
    return chat_result
```

### Refactored (Enqueue)
```python
@classifier_tools.tool
async def approve_message(reason: str):
    await response_queue.put({
        'chat_id': chat_id,
        'message_id': message_id,
        'classification_reason': reason
    })
    return "QUEUED_FOR_RESPONSE"
```

---

## Worker Startup Pattern

```python
async def start():
    # Init DB, connect bot
    # ...
    
    # Start workers as concurrent tasks
    await asyncio.gather(
        bot.run_until_disconnected(),
        asyncio.create_task(image_worker()),
        asyncio.create_task(audio_worker()),
        asyncio.create_task(classification_worker()),
        asyncio.create_task(response_worker()),
    )
```

---

## File Changes Summary

### Files to Modify

| File | Changes |
|------|---------|
| `database/models/message.py` | Add 7 columns (✅ Done) |
| `database/database.py` | Async engine migration (✅ Done) |
| `database/messages.py` | All functions → `async def`, `await` patterns |
| `database/chats.py` | All functions → `async def`, `await` patterns |
| `database/users.py` | All functions → `async def`, `await` patterns |
| `tools/telegram.py` | Accept `client + chat_id` instead of `event` |
| `__main__.py` | Handler enqueue logic, worker startup, remove inline Chatter calls |

### Files to Create

| File | Purpose |
|------|---------|
| `llm/image_describer.py` | Vision agent module |
| `workers/__init__.py` | Package init |
| `workers/queue_manager.py` | Queue definitions + orchestration |
| `workers/transcription.py` | Image + audio workers |
| `workers/classification.py` | Classification worker |
| `workers/response.py` | Response worker with batching |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Telethon event timeout | Process quickly, don't hold event objects |
| DB session conflicts | Each worker uses isolated `async_session()` |
| Worker crash/recovery | Re-queue if message <30min, skip if >1hr |
| CPU blocking (Whisper) | Use `asyncio.to_thread()` for offload |
| Response thundering herd | Batch 1-3 messages, Chatter controls pacing |

---

## Open Questions

1. **image_describer model**: Use same LLM model as chat, or vision-specific endpoint?
2. **Temp file directory**: `DATA_PATH / "temp"` or system `/tmp`?
3. **Worker count**: One worker per stage, or pool of workers per stage?
4. **Reply semantics**: Should responses use `reply_to=message_id` or just post to chat?
