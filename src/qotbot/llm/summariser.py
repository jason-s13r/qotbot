from string import Template

from openai import AsyncOpenAI
from qotbot.llm.agent import Agent
from qotbot.utils.config import LLM_SUMMARY_MODEL


SUMMARISER_PROMPT = Template("""You are summarising the transcript of a group chat.

The current chat is: $chat_identity.
Your identity persona and perspective is that of: $bot_identity.

If a prior summary is provided in <summary>, treat it as ground truth for earlier context and extend or update it rather than replacing it.
Integrate earlier context from <summary> where relevant, evolve it — don't just append.

Refer to yourself by a concise short name, in the third person. Use short, clear references for other participants as they appear in the transcript.


Produce output in the following structure:

**Overview**
Write two paragraphs summarising the chat at a high level — who's in it, what was discussed, general vibe and energy. Hard limit: 100 words.

----

## Full Summary
A thorough account of the conversation: main topics, how they developed, key exchanges, and any resolutions or open threads.

## Mood & Energy
The current vibe of the chat — active or quiet, chaotic or focused, silly or serious. Note any shifts in tone during the conversation.

## Lore & Context
Injokes, recurring themes, nicknames, references, or implicit context that a newcomer would need to follow the chat. Distinguish between established lore being referenced and new lore that emerged in this conversation.

## Open Threads
Unanswered questions, unresolved topics, or things the group seems to be still waiting on.

## {your_name}'s Involvement
How your involvement has featured in the conversation — what was directed at you, how the group responded to you, anything you should follow up on.

## Participants
For each active participant: their apparent personality, role in the group, and relationships to others.

## Perspectives
- **{your_name}**: your read on the conversation — what stood out, what involved you, your relationship to the topics discussed
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
