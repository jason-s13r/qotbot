from string import Template
from openai import AsyncOpenAI

from qotbot.llm.agent import Agent
from qotbot.utils.config import LLM_VISION_MODEL


IMAGE_DESCRIBER_PROMPT = Template("""You are describing visual media from a group chat so that other systems can understand its content.

Describe what you see clearly and concisely:
- Identify the main subject(s) and any relevant context or setting
- Note any visible text verbatim
- For stickers or emoji-style images, identify the emotion or reaction they convey

Keep descriptions factual. 1-2 sentences for simple stickers, up to 4 for complex images. Do not speculate beyond what is visible.
""")


class ImageDescriber(Agent):
    def __init__(self, client: AsyncOpenAI, bot_identity: str, chat_identity: str):
        super().__init__(
            client,
            LLM_VISION_MODEL,
            [
                {
                    "role": "system",
                    "content": IMAGE_DESCRIBER_PROMPT.substitute(
                        bot_identity=bot_identity, chat_identity=chat_identity
                    ),
                }
            ],
        )
