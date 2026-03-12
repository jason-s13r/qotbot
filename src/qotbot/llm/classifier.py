import logging
from string import Template

from openai import AsyncOpenAI
from qotbot.llm.agent import Agent

CLASSIFIER_PROMPT = Template("""You are a relevance classifier for a group chat Participant.
Determine if the Participant should respond to the recent messages.
                              
- The Participant is named {bot_identity}.
- The current chat is {chat_identity}.

TOOL USAGE (CRITICAL):
- ALWAYS call describe_image FIRST if an image or sticker is present in the message
- Then use approve_message when a response is required
- Use reject_message when there is no response required

Consider:
- Is the Participant being addressed directly?
- Is there a question directed at the Participant?
- Is the Participant's input valuable to this conversation?
- Or is this a side conversation the Participant should skip?
- If images/stickers are included, analyze their content for relevance
- Consider the conversation context and flow
- The Participant should not respond to every message, only when it has something valuable to contribute
- The Participant can interact with bots in the chat, so don't reject solely because the message came from a bot.

IMAGE/STICKER ANALYSIS:
- Messages may include images, stickers, or other media with base64 encoded data
- ALWAYS call describe_image to store a description of any image you see
- Analyze the visual content to understand context and relevance
- Consider if the image/sticker is asking for a response or is part of the conversation flow
- Stickers often convey emotions or reactions - respond appropriately if relevant""")


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
