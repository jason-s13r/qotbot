from qotbot.database.database import get_session
from qotbot.database.messages import (
    get_chat_overall_summary,
    get_recent_messages,
    get_sender_name,
)
from qotbot.database.models.message import Message
from sqlalchemy import select


def format_message_for_prompt(message: Message) -> str:
    return (
        f"<message id={message.id} sender_id={message.sender_id} sender_name={get_sender_name(message.sender)} timestamp={message.message_date.isoformat()} reply_to={message.reply_to_message_id or 'None'}>"
        f"{message.text or ''}"
        f"{f' [Image: {message.image_description}]' if message.image_description else ''}"
        f"{f' [Audio: {message.audio_transcription}]' if message.audio_transcription else ''}"
        f"</message>"
    )


def format_messages_for_prompt(messages: list[Message]) -> str:
    return "\n".join([format_message_for_prompt(message) for message in messages])


async def build_common_prompts(
    database_path: str,
    chat_id: int,
    message_ids: list[int],
) -> list[dict]:
    async with get_session(database_path) as session:
        result = await session.execute(
            select(Message).filter(
                Message.chat_id == chat_id, Message.id.in_(message_ids)
            )
        )
        messages = result.scalars().all()

        if not messages:
            return []

        recent_messages = await get_recent_messages(
            session, chat_id, limit=50, exclude_ids=message_ids
        )
        overall_summary = await get_chat_overall_summary(session, chat_id)

        recent_messages_text = format_messages_for_prompt(
            list(reversed(recent_messages))
        )
        new_messages_content = format_messages_for_prompt(messages)

        common_prompts = [
            {
                "role": "user",
                "content": f"<chat_summary>\n{overall_summary or ''}\n</chat_summary>",
            },
            {
                "role": "user",
                "content": f"<chat_history>\n{recent_messages_text}\n</chat_history>",
            },
            {
                "role": "user",
                "content": f"<new_messages>\n{new_messages_content}\n</new_messages>",
            },
        ]

        return common_prompts
