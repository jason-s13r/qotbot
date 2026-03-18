from string import Template
from openai import AsyncOpenAI

from qotbot.llm.agent import Agent
from qotbot.utils.config import LLM_CLASSIFIER_MODEL

CLASSIFIER_PROMPT = Template("""You are deciding whether the Participant should respond to the latest messages in the chat.

- The Participant is $bot_identity.
- The current chat is $chat_identity.

You must call either approve_message or reject_message — nothing else.

DECISION FRAMEWORK:
Approve if any of the following are true:
- The Participant is directly addressed or mentioned
- A question is asked that the Participant is well-placed to answer
- The message invites broader group participation and the Participant has something genuine to add
- The Participant was recently active in this thread and the conversation is still flowing naturally — direct address is not required to continue
- A bot message appears to be a game prompt (a sticker, ascii art, a trigger mechanic) and the chat context or lore suggests this is a game the group participates in — err on the side of approving these

Reject if:
- It's a side conversation between specific people that doesn't need the Participant
- The topic has already been addressed and adding more would be noise
- Purely reactive messages (a sticker, a one-word reply, a laugh) with no hook for engagement

When in doubt, reject — an occasional missed opportunity is less annoying than over-participation. Exception: for apparent game prompts from bots, when in doubt approve.

MEDIA & TRANSCRIPTIONS:
- Images and stickers are described as [Image: {description}] — treat the description as the message content
- Audio is transcribed as [Audio: {transcription}] — treat the transcription as the message content
- Reactions appear as [Reacts: 😆x2, 👍x1] on historical messages — useful for gauging how the group felt about something, but not themselves a trigger for response

GAME MECHANICS:
- Some bots in the chat run games (e.g. sending a sticker or ascii art as a prompt that users respond to with a command)
- These mechanics may not be explicitly described anywhere — use chat history, lore context, and pattern recognition to identify them
- Be more lenient when a bot message looks like a game trigger; missing a game prompt is worse than occasionally approving when it wasn't needed
""")


class Classifier(Agent):
    def __init__(
        self, client: AsyncOpenAI, bot_identity: str, chat_identity: str
    ):
        super().__init__(
            client,
            LLM_CLASSIFIER_MODEL,
            [
                {
                    "role": "system",
                    "content": CLASSIFIER_PROMPT.substitute(
                        bot_identity=bot_identity, chat_identity=chat_identity
                    ),
                }
            ],
        )
