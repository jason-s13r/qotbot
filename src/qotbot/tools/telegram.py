import asyncio
import base64
import logging
import pickle
import random
import uuid
from collections.abc import Sequence
from typing import Any
from fastmcp.server.providers import Provider
from fastmcp.tools import Tool
from fastmcp.resources import (
    Resource,
    ResourceContent,
    ResourceResult,
    ResourceTemplate,
)
from fastmcp import Context
from telethon import TelegramClient, hints
from telethon.tl.types import (
    InputMediaDice,
    InputMediaPoll,
    Message,
    MessageEntityItalic,
    Poll,
    PollAnswer,
    TextWithEntities,
)

from qotbot.database.database import get_session
from qotbot.database.messages import store_sent_message
from qotbot.utils.config import DATABASE_PATH

logger = logging.getLogger(__name__)


class TelegramProvider(Provider):
    """Provides resources and tools related to a telegram chat."""

    def __init__(self, client: TelegramClient, chat_id: int):
        super().__init__()
        self.client = client
        self.chat_id = chat_id
        self._resource_cache: dict[str, ResourceResult] = {}
        self._pickle_decode_guid = str(uuid.uuid4())

    async def _list_tools(self) -> Sequence[Tool]:
        return [
            Tool.from_function(
                self._get_chat_id,
                name="get_chat_id",
                description="Get the chat_id.",
            ),
            Tool.from_function(
                self._send_message,
                name="send_message",
                description="Send a message to a Telegram chat.",
            ),
            Tool.from_function(
                self._create_poll,
                name="create_poll",
                description=(
                    "Prepare a poll or quiz. Returns a resource_uri that MUST be passed to "
                    "send_message as file_uri to actually send it. The poll is not sent by this tool."
                ),
            ),
            Tool.from_function(
                lambda: dict(resource_uri="telegram://input_media/dice_roll"),
                name="get_dice_roll",
                description=(
                    "Prepare a dice roll. Returns a resource_uri that MUST be passed to "
                    "send_message as file_uri to actually send it. The dice emoji is not sent by this tool."
                ),
            ),
            Tool.from_function(
                lambda message_id: dict(
                    resource_uri=f"telegram://message/{message_id}/media"
                ),
                name="get_message_media_uri",
                description=(
                    "Prepare resource uri of media from a message. Returns a resource_uri that MUST be passed to "
                    "send_message as file_uri to actually send it. The media is not sent by this tool."
                ),
            ),
        ]

    async def _list_resources(self):
        return [
            Resource.from_function(
                self._get_chat_id,
                uri=f"telegram://chat_id",
                name="chat_id",
                description="The chat ID for this Telegram chat.",
            ),
            Resource.from_function(
                self._dice_roll,
                uri="telegram://input_media/dice_roll",
                name="dice_roll",
                description=("A dice roll result that can be sent as a message media."),
            ),
        ]

    def _dice_roll(self):
        return ResourceResult(
            contents=[
                ResourceContent(
                    content=base64.b64encode(
                        pickle.dumps(InputMediaDice("🎲"))
                    ).decode(),
                    mime_type="application/x-python-pickle",
                    meta={"decode_key": self._pickle_decode_guid},
                )
            ],
        )

    async def _list_resource_templates(self):
        return [
            ResourceTemplate.from_function(
                self._get_telegram_cache_resource,
                name="get_telegram_cache_resource",
                uri_template="telegram://cache/{cache_id}",
                description="Access a cached FileLike resource for sending as a file in a message.",
            ),
            ResourceTemplate.from_function(
                self._get_message_media,
                name="get_message_media",
                uri_template="telegram://message/{message_id}/media",
                description="Access media bytes resource for use with other tools, such as sending as a file in a send_message.",
            ),
        ]

    def _get_chat_id(self) -> int:
        """Get the chat ID."""
        return self.chat_id

    async def _send_message(
        self,
        ctx: Context,
        message: str = "",
        reply_to: int | None = None,
        schedule: hints.DateLike | None = None,
        file_uri: str | None = None,
    ):
        try:
            async with self.client.action(self.chat_id, "typing"):
                file = None
                if file_uri:
                    resource = await ctx.read_resource(file_uri)
                    file_name = (
                        None
                        if not resource.meta
                        else resource.meta.get("file_name", None)
                    )
                    if resource and resource.contents:
                        file = [
                            (self._decode_pickle(item) or item.content)
                            for item in resource.contents
                        ]
                    if len(file) == 1:
                        file = file[0]
                    if file_name is not None and file is not None:
                        file = await self.client.upload_file(file, file_name=file_name)

                await asyncio.sleep(0.1)
                response = await self.client.send_message(
                    self.chat_id,
                    message,
                    reply_to=reply_to,
                    file=file,
                    schedule=schedule,
                    parse_mode="markdown",
                )
                await self._store_sent_message(response)
                in_reply_to = f"reply_to={reply_to}" if reply_to is not None else ""
                as_scheduled = (
                    f"SCHEDULED for {schedule}" if schedule is not None else "SENT"
                )
                return f"{as_scheduled} message_id={response.id} {in_reply_to}"
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            raise e

    def _get_telegram_cache_resource(self, cache_id: str):
        uri = f"telegram://cache/{cache_id}"
        entry = self._resource_cache.get(uri)
        if entry is None:
            raise KeyError(f"Unknown or expired cached resource: {uri}")

        return entry

    async def _get_message_media(self, message_id: int):
        """Download media from a message and return it as bytes."""
        try:
            chat = await self.client.get_entity(self.chat_id)
            message: Message = await self.client.get_messages(chat, ids=message_id)
            if not message:
                return None
            if not message.media:
                return None

            data = await self.client.download_media(message, file=bytes)
            mime_type = "application/octet-stream"
            meta = {}
            if message.photo:
                mime_type = "image/jpeg"
                meta["file_name"] = f"photo_{message_id}.jpg"
            elif message.file and message.file.mime_type:
                mime_type = message.file.mime_type
                meta["file_name"] = message.file.name or f"file_{message_id}"

            return ResourceResult(
                contents=[ResourceContent(content=data, mime_type=mime_type)], meta=meta
            )
        except Exception as e:
            logger.error(f"Error downloading media from message {message_id}: {e}")
            raise e

    async def _create_poll(
        self,
        question: str,
        options: list[str],
        public_voters: bool = True,
        multiple_choice: bool = False,
        quiz_answers: list[str] | None = None,
        explanation: str | None = None,
    ):
        correct = []
        answers = []
        for i, opt in enumerate(options):
            answer = PollAnswer(TextWithEntities(opt, []), str(i + 1).encode())
            answers.append(answer)
            if quiz_answers and opt in quiz_answers:
                correct.append(answer.option)

        poll = Poll(
            id=random.randint(1000, 10000),
            question=TextWithEntities(question, []),
            answers=answers,
            public_voters=public_voters,
            quiz=len(correct) > 0,
            multiple_choice=multiple_choice,
        )

        solution_entities = None
        if explanation is not None:
            solution_entities = [MessageEntityItalic(0, len(explanation))]

        input_poll = InputMediaPoll(
            poll=poll,
            correct_answers=correct,
            solution=explanation,
            solution_entities=solution_entities,
        )

        cache_id = str(uuid.uuid4())
        uri = f"telegram://cache/{cache_id}"

        blob = base64.b64encode(pickle.dumps(input_poll)).decode()

        resource = ResourceResult(
            contents=[
                ResourceContent(
                    content=blob,
                    mime_type="application/x-python-pickle",
                    meta={"decode_key": self._pickle_decode_guid},
                )
            ],
        )

        self._resource_cache[uri] = resource

        return {"resource_uri": uri}

    async def _store_sent_message(self, message):
        """Store a message that was sent by the bot (not from an event)."""
        async with get_session() as session:
            await store_sent_message(session, message, self.chat_id)

    def _decode_pickle(self, item: ResourceContent) -> Any:
        if item.mime_type != "application/x-python-pickle":
            return item.content
        if not item.meta:
            return None
        if item.meta.get("decode_key") != self._pickle_decode_guid:
            return None

        try:
            media = pickle.loads(base64.b64decode(item.content))
            return media
        except Exception as e:
            logger.error(f"Failed to decode pickle content: {e}")
            raise ValueError("Invalid pickle content") from e
