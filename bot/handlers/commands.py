import logging
from telethon import events

from db.database import AsyncSessionLocal
from db.crud import get_or_create_chat, close_session, get_active_session
from config import TELEGRAM_BOT_OWNER, SESSION_TIMEOUT_MINUTES

logger = logging.getLogger(__name__)


def register_command_handlers(bot):
    """Register all command handlers with the bot."""

    @bot.on(events.NewMessage(pattern=r"(?i)^/help$", from_users=TELEGRAM_BOT_OWNER))
    async def handle_help_cmd(event: events.NewMessage.Event):
        """Show help message."""
        help_text = """
**Available Commands:**

/allow [none|command|full] - Set chat permission level
/stop - End the current session
/info - Show chat and session info
/models - List available LLM models
/model [name] - Set/show chat model
/classifier [name] - Set/show classifier model
/help - Show this help message

**Permission Levels:**
- none: Bot ignores the chat
- command: Bot responds to commands only
- full: Full bot functionality
"""
        await event.respond(help_text, parse_mode="markdown")

    @bot.on(
        events.NewMessage(
            pattern=r"(?i)^/allow\s*(\w+)?$", from_users=TELEGRAM_BOT_OWNER
        )
    )
    async def handle_allow_cmd(event: events.NewMessage.Event):
        """Set chat permission level."""
        async with AsyncSessionLocal() as db_session:
            try:
                chat_telegram_id = int(event.chat_id) if event.chat_id else 0
                chat = await get_or_create_chat(
                    db_session,
                    chat_telegram_id,
                    getattr(event.chat, "title", None),
                )

                match = event.pattern_match
                level = match.group(1) if match else None
                if not level:
                    await event.respond(
                        f"Current permission: {chat.permission}\\nUsage: /allow [none|command|full]"
                    )
                    return

                if level.lower() not in ["none", "command", "full"]:
                    await event.respond("Invalid level. Use: none, command, or full")
                    return

                chat.permission = level.lower()
                await db_session.commit()
                await event.respond(f"Permission set to: {level.lower()}")
            except Exception as e:
                logger.error(f"Error in /allow: {e}", exc_info=True)
                await db_session.rollback()
                await event.respond(f"Error: {e}")

    @bot.on(events.NewMessage(pattern=r"(?i)^/stop$", from_users=TELEGRAM_BOT_OWNER))
    async def handle_stop_cmd(event: events.NewMessage.Event):
        """End the current session."""
        async with AsyncSessionLocal() as db_session:
            try:
                chat_telegram_id = int(event.chat_id) if event.chat_id else 0
                chat = await get_or_create_chat(
                    db_session,
                    chat_telegram_id,
                    getattr(event.chat, "title", None),
                )

                active_session = await get_active_session(
                    db_session, chat.id, SESSION_TIMEOUT_MINUTES
                )

                if not active_session:
                    await event.respond("No active session.")
                    return

                await close_session(
                    db_session, active_session, "Session ended by admin"
                )
                await db_session.commit()
                await event.respond(f"Session {active_session.id} closed.")
            except Exception as e:
                logger.error(f"Error in /stop: {e}", exc_info=True)
                await db_session.rollback()
                await event.respond(f"Error: {e}")

    @bot.on(events.NewMessage(pattern=r"(?i)^/info$", from_users=TELEGRAM_BOT_OWNER))
    async def handle_info_cmd(event: events.NewMessage.Event):
        """Show chat and session info."""
        from sqlalchemy import select, func
        from db.models import Message

        async with AsyncSessionLocal() as db_session:
            try:
                chat_telegram_id = int(event.chat_id) if event.chat_id else 0
                chat = await get_or_create_chat(
                    db_session,
                    chat_telegram_id,
                    getattr(event.chat, "title", None),
                )

                message_count_result = await db_session.execute(
                    select(func.count(Message.id)).where(Message.chat_id == chat.id)
                )
                message_count = message_count_result.scalar() or 0

                active_session = await get_active_session(
                    db_session, chat.id, SESSION_TIMEOUT_MINUTES
                )

                info_text = "**Chat Info:**\n"
                info_text += f"Chat ID: {chat.telegram_id}\n"
                info_text += f"Title: {chat.title or 'N/A'}\n"
                info_text += f"Permission: {chat.permission}\n"
                info_text += f"Messages: {message_count}\n"

                if active_session:
                    info_text += "\n**Active Session:**\n"
                    info_text += f"Session ID: {active_session.id}\n"
                    info_text += f"Created: {active_session.created_at.strftime('%Y-%m-%d %H:%M')}\n"
                else:
                    info_text += "\nNo active session."

                await event.respond(info_text, parse_mode="markdown")
            except Exception as e:
                logger.error(f"Error in /info: {e}", exc_info=True)
                await event.respond(f"Error: {e}")

    @bot.on(events.NewMessage(pattern=r"(?i)^/models$", from_users=TELEGRAM_BOT_OWNER))
    async def handle_models_cmd(event: events.NewMessage.Event):
        """List available models from the LLM service."""
        from config import LLM_API_URL, LLM_API_KEY
        from openai import AsyncOpenAI

        client = AsyncOpenAI(base_url=LLM_API_URL, api_key=LLM_API_KEY)

        try:
            models = await client.models.list()
            model_list = [model.id for model in models.data]

            response_text = "**Available Models:**\n\n"
            for model in sorted(model_list):
                response_text += f"- `{model}`\n"

            await event.respond(response_text, parse_mode="markdown")
        except Exception as e:
            await event.respond(f"Error fetching models: {e}")

    @bot.on(
        events.NewMessage(
            pattern=r"(?i)^/model\b\s*(.*)$", from_users=TELEGRAM_BOT_OWNER
        )
    )
    async def handle_model_cmd(event: events.NewMessage.Event):
        """Set the chat model."""
        from config import get_chat_model, set_chat_model

        match = event.pattern_match
        model_name = match.group(1).strip() if match else ""
        if not model_name:
            current = get_chat_model()
            await event.respond(
                f"Current chat model: `{current}`\nUsage: /model <model_name>"
            )
            return

        set_chat_model(model_name)
        await event.respond(f"Chat model set to: `{model_name}`")

    @bot.on(
        events.NewMessage(
            pattern=r"(?i)^/classifier\s*(.*)$", from_users=TELEGRAM_BOT_OWNER
        )
    )
    async def handle_classifier_cmd(event: events.NewMessage.Event):
        """Set the classifier model."""
        from config import get_classifier_model, set_classifier_model

        match = event.pattern_match
        model_name = match.group(1).strip() if match else ""
        if not model_name:
            current = get_classifier_model()
            await event.respond(
                f"Current classifier model: `{current}`\nUsage: /classifier <model_name>"
            )
            return

        set_classifier_model(model_name)
        await event.respond(f"Classifier model set to: `{model_name}`")

    @bot.on(
        events.NewMessage(
            pattern=r"(?i)^/throttle\s*(\d+)?$", from_users=TELEGRAM_BOT_OWNER
        )
    )
    async def handle_throttle_cmd(event: events.NewMessage.Event):
        """Set throttle delay for current chat."""
        from db.crud import set_chat_throttle

        async with AsyncSessionLocal() as db_session:
            try:
                chat = await get_or_create_chat(
                    db_session,
                    abs(int(event.chat_id)) if event.chat_id else 0,
                    getattr(event.chat, "title", None),
                )

                match = event.pattern_match
                seconds_str = match.group(1) if match else None
                if not seconds_str:
                    await event.respond(
                        f"Current throttle: {chat.throttle_seconds}s\\nUsage: /throttle <seconds>"
                    )
                    return

                seconds = int(seconds_str)
                if seconds < 0:
                    await event.respond("Throttle must be >= 0 seconds")
                    return

                await set_chat_throttle(db_session, chat, seconds)
                await db_session.commit()
                await event.respond(f"Throttle set to: {seconds}s")
            except Exception as e:
                logger.error(f"Error in /throttle: {e}", exc_info=True)
                await db_session.rollback()
                await event.respond(f"Error: {e}")

    @bot.on(events.NewMessage(pattern=r"(?i)^/bye$", from_users=TELEGRAM_BOT_OWNER))
    async def handle_bye_cmd(event: events.NewMessage.Event):
        """Leave the chat."""
        from telethon.tl.functions.channels import LeaveChannelRequest

        try:
            input_chat = await event.get_input_chat()
            if input_chat:
                await bot(LeaveChannelRequest(input_chat))
                await event.respond("Left the chat.")
        except Exception as e:
            logger.error(f"Error leaving chat: {e}", exc_info=True)
            await event.respond(f"Error leaving chat: {e}")
