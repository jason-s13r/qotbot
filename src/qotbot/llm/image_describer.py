from string import Template
from openai import AsyncOpenAI

from qotbot.llm.agent import Agent

IMAGE_DESCRIBER_PROMPT = Template("""You are an image describer for a group chat.
Your task is to provide clear, concise descriptions of images, stickers, and other visual media.

- The Participant is named $bot_identity.
- The current chat is $chat_identity.

Describe what you see:
- Identify the main subject(s)
- Note any text visible in the image
- Describe the context or setting
- For stickers, identify the emotion or reaction conveyed
- Keep descriptions factual and neutral
- Be concise but informative (2-4 sentences)

Do not:
- Make assumptions about intent
- Add emotional interpretation unless clearly evident
- Describe beyond what is visible""")


class ImageDescriber(Agent):
    def __init__(
        self, client: AsyncOpenAI, model: str, bot_identity: str, chat_identity: str
    ):
        super().__init__(
            client,
            model,
            [
                {
                    "role": "system",
                    "content": IMAGE_DESCRIBER_PROMPT.substitute(
                        bot_identity=bot_identity, chat_identity=chat_identity
                    ),
                }
            ],
        )
