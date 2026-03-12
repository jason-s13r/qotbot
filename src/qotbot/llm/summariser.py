from string import Template

from openai import AsyncOpenAI
from qotbot.llm.agent import Agent

SUMMARISER_PROMPT = Template("""You are to summarise the transcript of a group chat conversation for the client Participant.

- The client Participant is named $bot_identity.
- The current chat is $chat_identity.
- A prior summary of the conversation may be provided in <summary>.
                             
Consider:
- Summarise the key points of the conversation in a concise manner.
- Focus on the most important information and main topics discussed.
- Exclude irrelevant details and side conversations.
- Identify chat lore, injokes, recurring themes, and important context that may not be explicitly stated.
- List the main participants in the conversation and their apparent roles and relationships.
""")


class Summariser(Agent):
    def __init__(
        self, client: AsyncOpenAI, model: str, bot_identity: str, chat_identity: str
    ):
        super().__init__(
            client,
            model,
            [
                {
                    "role": "system",
                    "content": SUMMARISER_PROMPT.substitute(
                        bot_identity=bot_identity, chat_identity=chat_identity
                    ),
                }
            ],
        )
