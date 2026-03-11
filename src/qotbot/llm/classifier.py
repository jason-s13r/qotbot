
import logging
from string import Template

from openai import AsyncOpenAI
from qotbot.llm.agent import Agent

CLASSIFIER_PROMPT = Template("""You are a relevance classifier for a group chat Participant.
Determine if the Participant should respond to the recent messages.

Respond with a JSON object in the following format:
{{"needs_response": true/false, "reason": "brief explanation"}}

TOOL USAGE (CRITICAL):
- use approve_message when a response is required.
- use reject_message when there is no response required.

Consider:
- The Participant is named {bot_identity}.
- The Participant is an active participant in the chat {chat_identity}.
- Is the Participant being addressed directly?
- Is there a question directed at the Participant?
- Is the Participant's input valuable to this conversation?
- Or is this a side conversation the Participant should skip?
- If images/stickers are included, analyze their content for relevance
- Consider the conversation context and flow
- The Participant should not respond to every message, only when it has something valuable to contribute
""")

class Classifier(Agent):
    def __init__(self, client: AsyncOpenAI, model: str, bot_identity: str, chat_identity: str):
        super().__init__(client, model, [
            {"role": "system", "content": CLASSIFIER_PROMPT.substitute(bot_identity=bot_identity, chat_identity=chat_identity)}
        ])