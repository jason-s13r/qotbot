import logging
from openai import AsyncOpenAI
from config import LLM_API_URL, LLM_API_KEY, get_classifier_model

logger = logging.getLogger(__name__)


CLASSIFIER_PROMPT = """You are a relevance classifier for a group chat AI assistant.
Determine if the AI should respond to the recent messages.

Respond with ONLY a JSON object:
{"needs_response": true/false, "reason": "brief explanation"}

Consider:
- Is the AI being addressed directly?
- Is there a question directed at the AI?
- Is the AI's input valuable to this conversation?
- Or is this a side conversation the AI should skip?
- If images/stickers are included, analyze their content for relevance
- Consider the conversation context and flow
- The AI should not respond to every message, only when it has something valuable to contribute
"""


async def classify_messages(messages: list[dict]) -> dict:
    """
    Classify a batch of messages to determine if the AI should respond.

    Args:
        messages: List of dicts with 'sender', 'text', 'timestamp', 'is_bot' keys
            and optional 'media' key with {'type': str, 'base64': str}

    Returns:
        dict with 'needs_response' (bool) and 'reason' (str)
    """
    client = AsyncOpenAI(base_url=LLM_API_URL, api_key=LLM_API_KEY)

    content_parts = []
    content_parts.append(
        {"type": "text", "text": "Recent chat messages (newest at bottom):"}
    )

    for i, m in enumerate(messages):
        sender_prefix = "[Bot]" if m.get("is_bot") else f"[{m['sender']}]"

        if m.get("media"):
            media = m["media"]
            content_parts.append(
                {"type": "text", "text": f"{sender_prefix} sent a {media['type']}:"}
            )
            if media.get("base64"):
                content_parts.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{media['base64']}"
                        },
                    }
                )
        else:
            text_content = m.get("text", "")
            if text_content:
                content_parts.append(
                    {"type": "text", "text": f"{sender_prefix}: {text_content}"}
                )
            else:
                content_parts.append(
                    {"type": "text", "text": f"{sender_prefix}: [no text]"}
                )

    try:
        response = await client.chat.completions.create(
            model=get_classifier_model(),
            messages=[
                {"role": "system", "content": CLASSIFIER_PROMPT},
                {"role": "user", "content": content_parts},
            ],
            temperature=0.3,
            max_tokens=100,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content or "{}"
        import json

        result = json.loads(content)
        return {
            "needs_response": result.get("needs_response", False),
            "reason": result.get("reason", ""),
        }
    except Exception as e:
        logger.error(f"Classification error: {e}")
        return {
            "needs_response": True,
            "reason": f"Error in classifier: {str(e)}, defaulting to respond",
        }
