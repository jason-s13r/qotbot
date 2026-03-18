from string import Template

from openai import AsyncOpenAI
from qotbot.llm.agent import Agent
from qotbot.utils.config import LLM_SUMMARY_MODEL


SUMMARISER_PROMPT = Template("""You are summarising the transcript of a group chat.

The current chat is: $chat_identity.
Your perspective is that of: $bot_identity.

If a prior summary is provided in <summary>, treat it as ground truth for earlier context and extend or update it rather than replacing it. Evolve it — don't just append.

Produce output in the following structure exactly:

Two paragraphs summarising the chat at a high level — who's in it, what was discussed, general vibe and energy. Hard limit: 100 words. No heading, just prose.

----

## Full Summary
A thorough account of the conversation: main topics, how they developed, key exchanges, and any resolutions or open threads. Integrate earlier context from <summary> where relevant. Written from $bot_identity's perspective — not a neutral record, but their read on what happened.

## Mood & Energy
The current vibe of the chat — active or quiet, chaotic or focused, silly or serious. Note any shifts in tone during the conversation.

## Open Threads
Unanswered questions, unresolved topics, or things the group seems to be still waiting on.

## $bot_identity's Involvement
How $bot_identity has featured in the conversation — what was directed at them, how the group responded to them, anything they should follow up on.

## Participants
For each active participant: their apparent personality, role in the group, and relationships to others.

## Lore & Context
Injokes, recurring themes, nicknames, references, or implicit context that a newcomer would need to follow the chat. Distinguish between established lore being referenced and new lore that emerged in this conversation.

## Perspectives
- **$bot_identity**: your read on the conversation — what stood out, what involved you, your relationship to the topics discussed
- **Others**: a brief characterisation of each key participant's apparent perspective or agenda in this conversation

## Notable Media
Links, images, or files that were significant to the conversation, with brief context on why they mattered.
""")

class Summariser(Agent):
    def __init__(self, client: AsyncOpenAI, bot_identity: str, chat_identity: str):
        super().__init__(
            client,
            LLM_SUMMARY_MODEL,
            [
                {
                    "role": "system",
                    "content": SUMMARISER_PROMPT.substitute(
                        bot_identity=bot_identity, chat_identity=chat_identity
                    ),
                }
            ],
        )
