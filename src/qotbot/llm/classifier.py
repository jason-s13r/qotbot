from string import Template
from openai import AsyncOpenAI

from qotbot.llm.agent import Agent

CLASSIFIER_PROMPT = Template("""You are a relevance classifier for a group chat Participant.
Determine if the Participant should respond to the recent messages.
                              
- The Participant is named $bot_identity.
- The current chat is $chat_identity.

TOOL USAGE (CRITICAL):
- Call approve_message when a response is required.
- Call reject_message when there is no response required.
- YOU MUST call either approve_message or reject_message.

Consider:
- Is the Participant being addressed directly?
- Is there a question directed at the Participant?
- Is the Participant's input valuable to this conversation?
- Or is this a side conversation the Participant should skip?
- Consider the conversation context and flow.
- If an image, sticker, or audio message is present, it has already been transcribed/described.
- The Participant should not respond to every message, only when it has something valuable to contribute.
- The Participant can interact with bots in the chat, so don't reject solely because the message came from a bot.

IMAGE/STICKER ANALYSIS:
- Messages may include images or stickers that have been described by the image transcription pipeline.
- The image description will appear in the message as [Image: {description}].
- Analyze the description to understand context and relevance.
- Consider if the image conveys emotions or reactions, invoking a response that is relevant to the chat history.
- Consider if the image could be part of game mechanics, which may mean it requires a response.

AUDIO ANALYSIS:
- Messages may include voice messages or audio files that have been transcribed.
- The transcription will appear in the message as [Audio: {transcription}].
- Analyze the transcribed text to understand context and relevance.
- Consider if the audio message is asking for a response or is part of the conversation flow.
""")


class Classifier(Agent):
    def __init__(
        self, client: AsyncOpenAI, model: str, bot_identity: str, chat_identity: str
    ):
        super().__init__(
            client,
            model,
            [
                {
                    "role": "system",
                    "content": CLASSIFIER_PROMPT.substitute(
                        bot_identity=bot_identity, chat_identity=chat_identity
                    ),
                }
            ],
        )
