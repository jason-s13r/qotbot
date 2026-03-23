import logging
import re
from telethon import events

from qotbot.database.database import get_session
from qotbot.database.rules import (
    add_rule,
    delete_rule,
    get_all_rules_for_chat,
    update_rule,
)
from qotbot.utils.command import Commands
from qotbot.utils.config import DATABASE_PATH

logger = logging.getLogger(__name__)

rules = Commands()


@rules.slash("rules", rules.Permissions(chat_admin=True, is_scoped=True))
async def handle_rules_event(event: events.NewMessage.Event, payload: str = None):
    """Manage chat rules for LLM behavior."""
    logger.info(
        f"/rules command received from {event.sender_id} in chat {event.chat_id}"
    )

    VALID_SPECIFIERS = {"chatter", "classifier"}
    add_match = re.match(r"^add\s+(\S+)\s+(.+)$", payload or "")
    edit_match = re.match(r"^edit\s+(\d+)\s+(.+)$", payload or "")
    delete_match = re.match(r"^delete\s+(\d+)$", payload or "")
    list_match = re.match(r"^list$", payload or "")

    async with get_session() as session:
        if add_match:
            specifier = add_match.group(1)
            rule_text = add_match.group(2)
            if specifier not in VALID_SPECIFIERS:
                async with event.client.action(event.chat_id, "typing"):
                    await event.respond(
                        f"Invalid specifier '{specifier}'. Valid specifiers: {', '.join(VALID_SPECIFIERS)}"
                    )
                return
            rule = await add_rule(session, event.chat_id, specifier, rule_text)
            async with event.client.action(event.chat_id, "typing"):
                await event.respond(
                    f"Rule added (ID: {rule.id}): [{rule.specifier}] {rule.text}"
                )

        elif edit_match:
            rule_id = int(edit_match.group(1))
            rule_text = edit_match.group(2)
            rule = await update_rule(session, event.chat_id, rule_id, rule_text)
            if rule:
                async with event.client.action(event.chat_id, "typing"):
                    await event.respond(
                        f"Rule updated (ID: {rule.id}): [{rule.specifier}] {rule.text}"
                    )
            else:
                async with event.client.action(event.chat_id, "typing"):
                    await event.respond(
                        f"Rule {rule_id} not found or not in this chat."
                    )

        elif delete_match:
            rule_id = int(delete_match.group(1))
            deleted = await delete_rule(session, event.chat_id, rule_id)
            if deleted:
                async with event.client.action(event.chat_id, "typing"):
                    await event.respond(f"Rule {rule_id} deleted.")
            else:
                async with event.client.action(event.chat_id, "typing"):
                    await event.respond(
                        f"Rule {rule_id} not found or not in this chat."
                    )

        elif list_match:
            rules = await get_all_rules_for_chat(session, event.chat_id)
            if not rules:
                async with event.client.action(event.chat_id, "typing"):
                    await event.respond("No rules defined for this chat.")
                return

            rules_text = ["**Rules for this chat:**"]
            for rule in rules:
                rules_text.append(f"{rule.id}. [{rule.specifier}] {rule.text}")
            async with event.client.action(event.chat_id, "typing"):
                await event.respond("\n".join(rules_text))
        else:
            async with event.client.action(event.chat_id, "typing"):
                await event.respond(
                    "**Rules command help:**\n\n"
                    "- `/rules` - Show this help\n"
                    "- `/rules list` - List all rules\n"
                    "- `/rules add <specifier> <text>` - Add a rule\n"
                    "- `/rules edit <id> <text>` - Edit a rule\n"
                    "- `/rules delete <id>` - Delete a rule"
                )
