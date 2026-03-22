import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from qotbot.database.models.rule import Rule

logger = logging.getLogger(__name__)


async def get_all_rules_for_chat(session: AsyncSession, chat_id: int) -> list[Rule]:
    """
    Get all rules for a chat.

    Args:
        session: Async database session
        chat_id: The chat ID to query

    Returns:
        List of Rule objects
    """
    result = await session.execute(
        select(Rule).filter(Rule.chat_id == chat_id).order_by(Rule.created_at.asc())
    )
    return result.scalars().all()


async def add_rule(
    session: AsyncSession, chat_id: int, specifier: str, text: str
) -> Rule:
    """
    Add a new rule for a chat.

    Args:
        session: Async database session
        chat_id: The chat ID
        specifier: The rule specifier (e.g., 'chatter', 'classifier')
        text: The rule text

    Returns:
        The created Rule object
    """
    rule = Rule(chat_id=chat_id, specifier=specifier, text=text)
    session.add(rule)
    logger.info(f"Added rule for chat {chat_id}: {specifier}")
    return rule


async def update_rule(
    session: AsyncSession, chat_id: int, rule_id: int, text: str
) -> Rule | None:
    """
    Update a rule's text.

    Args:
        session: Async database session
        chat_id: The chat ID
        rule_id: The rule ID to update
        text: The new rule text

    Returns:
        The updated Rule object or None if not found
    """
    rule = await session.get(Rule, rule_id)
    if not rule or rule.chat_id != chat_id:
        logger.warning(f"Rule {rule_id} not found for chat {chat_id}")
        return None

    rule.text = text
    logger.info(f"Updated rule {rule_id} for chat {chat_id}")
    return rule


async def delete_rule(session: AsyncSession, chat_id: int, rule_id: int) -> bool:
    """
    Delete a rule.

    Args:
        session: Async database session
        chat_id: The chat ID
        rule_id: The rule ID to delete

    Returns:
        True if deleted, False if not found
    """
    rule = await session.get(Rule, rule_id)
    if not rule or rule.chat_id != chat_id:
        logger.warning(f"Rule {rule_id} not found for chat {chat_id}")
        return False

    await session.delete(rule)
    logger.info(f"Deleted rule {rule_id} for chat {chat_id}")
    return True


async def get_rules_by_specifier(
    session: AsyncSession, chat_id: int, specifier: str
) -> list[Rule]:
    """
    Get rules for a chat filtered by specifier.

    Args:
        session: Async database session
        chat_id: The chat ID
        specifier: The rule specifier to filter by

    Returns:
        List of Rule objects
    """
    result = await session.execute(
        select(Rule)
        .filter(Rule.chat_id == chat_id, Rule.specifier == specifier)
        .order_by(Rule.created_at.asc())
    )
    return result.scalars().all()
