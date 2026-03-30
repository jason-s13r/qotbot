from string import Template
import json

from qotbot.database.database import get_session
from qotbot.database.messages import (
    get_chat_overall_summary,
    get_recent_messages,
    get_sender_name,
)
from qotbot.database.models.message import Message
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from qotbot.utils.config import DATABASE_PATH


def _format_poll_results(poll_results_json: str) -> str:
    try:
        data = json.loads(poll_results_json)
        poll = data.get("poll") or {}
        results = data.get("results") or {}

        question = poll.get("question", {})
        if isinstance(question, dict):
            question = question.get("text", "")

        answers = poll.get("answers", [])
        vote_counts = results.get("results", [])
        total = results.get("total_voters", 0)

        parts = []
        for i, answer in enumerate(answers):
            text = answer.get("text", {})
            if isinstance(text, dict):
                text = text.get("text", "")
            count = vote_counts[i].get("voters", 0) if i < len(vote_counts) else "?"
            parts.append(f"{text}: {count}")

        return f'Poll: "{question}" - {", ".join(parts)} (total: {total} voters)'
    except Exception:
        return f"Poll: {poll_results_json}"


def _format_button_options(button_options_json: str) -> str:
    try:
        data = json.loads(button_options_json)
        buttons = data.get("buttons") or []
        if not buttons:
            return "Buttons: none"

        parts = []
        for button in buttons:
            idx = button.get("index")
            row = button.get("row")
            column = button.get("column")
            text = button.get("text", "")
            parts.append(f"{idx}:{text} (row {row}, col {column})")

        return f"Buttons: {', '.join(parts)}"
    except Exception:
        return f"Buttons: {button_options_json}"


def format_message_for_prompt(message: Message) -> str:
    return (
        f"<message id={message.id} sender_id={message.sender_id} sender_name={get_sender_name(message.sender)} timestamp={message.message_date.isoformat()} reply_to={message.reply_to_message_id or 'None'}>"
        f"{message.text or ''}"
        f"{f' [Image: {message.image_description}]' if message.image_description else ''}"
        f"{f' [Audio: {message.audio_transcription}]' if message.audio_transcription else ''}"
        f"{f' [{_format_poll_results(message.poll_results)}]' if message.poll_results else ''}"
        f"{f' [{_format_button_options(message.button_options)}]' if message.button_options else ''}"
        f"</message>"
    )


def format_messages_for_prompt(messages: list[Message]) -> str:
    return "\n".join([format_message_for_prompt(message) for message in messages])


async def build_common_prompts(
    chat_id: int,
    message_ids: list[int],
    max_recent_messages: int = 50,
) -> list[dict]:
    async with get_session() as session:
        result = await session.execute(
            select(Message)
            .filter(Message.chat_id == chat_id, Message.id.in_(message_ids))
            .options(joinedload(Message.sender))
        )
        messages = list(result.scalars().all())

        if not messages:
            return []

        recent_messages = await get_recent_messages(
            session, chat_id, limit=max_recent_messages, exclude_ids=message_ids
        )
        overall_summary = await get_chat_overall_summary(session, chat_id)

        recent_messages_text = format_messages_for_prompt(
            list(reversed(recent_messages))
        )
        new_messages_content = format_messages_for_prompt(messages)

        user_prompt = Template(
            """Given the following chat information:
<chat_summary>\n$overall_summary\n</chat_summary>
<chat_history>\n$recent_messages_text\n</chat_history>
Please use the appropriate tools regarding:
<new_messages>\n$new_messages_content\n</new_messages>"""
        )

        common_prompts = [
            {
                "role": "user",
                "content": user_prompt.substitute(
                    overall_summary=overall_summary,
                    recent_messages_text=recent_messages_text,
                    new_messages_content=new_messages_content,
                ),
            },
        ]

        return common_prompts
