
import logging
from string import Template

from openai import AsyncOpenAI
from qotbot.llm.agent import Agent

CLASSIFIER_PROMPT = Template("""You are a relevance classifier for a group chat AI assistant.
Determine if the AI should respond to the recent messages.

Respond with a JSON object in the following format:
{{"needs_response": true/false, "reason": "brief explanation"}}

TOOL USAGE (CRITICAL):
- use approve_message when a response is required.
- use reject_message when there is no response required.

Consider:
- The AI is named {bot_identity}.
- The AI is an active participant in the chat {chat_identity}.
- Is the AI being addressed directly?
- Is there a question directed at the AI?
- Is the AI's input valuable to this conversation?
- Or is this a side conversation the AI should skip?
- If images/stickers are included, analyze their content for relevance
- Consider the conversation context and flow
- The AI should not respond to every message, only when it has something valuable to contribute
""")

class Classifier(Agent):
    def __init__(self, client: AsyncOpenAI, model: str, bot_identity: str, chat_identity: str):
        super().__init__(client, model, [
            {"role": "system", "content": CLASSIFIER_PROMPT.substitute(bot_identity=bot_identity, chat_identity=chat_identity)}
        ])