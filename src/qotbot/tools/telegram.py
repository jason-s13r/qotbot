import asyncio
import base64
import hashlib
import logging
import pickle
import random
import re
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
from telethon.tl.functions.messages import SendVoteRequest
from telethon.tl.types import (
    InputMediaDice,
    InputMediaPoll,
    Message,
    MessageEntityItalic,
    MessageMediaPoll,
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

    def __init__(self, client: TelegramClient, chat_id: int, message_id: int):
        super().__init__()
        self._client = client
        self._chat_id = chat_id
        self._message_id = message_id
        self._resource_cache: dict[str, ResourceResult] = {}
        self._pickle_decode_guid = str(uuid.uuid4())
        # Dedupes repeated send_message tool calls for one response cycle.
        self._sent_message_fingerprints: set[str] = set()
        self._is_bot: bool | None = None  # resolved lazily in _list_tools

    async def _resolve_is_bot(self) -> bool:
        if self._is_bot is None:
            me = await self._client.get_me()
            self._is_bot = bool(getattr(me, "bot", False))
        return self._is_bot

    async def _list_tools(self) -> Sequence[Tool]:
        is_bot = await self._resolve_is_bot()
        tools = [
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
            Tool.from_function(
                self._get_poll_results,
                name="get_poll_results",
                description=(
                    "Fetch the current poll results for a message that contains a poll directly from Telegram. "
                    "Returns the poll question, answer options with indices, vote counts, and total voters."
                ),
            ),
            Tool.from_function(
                self._send_poll_vote,
                name="send_poll_vote",
                description=(
                    "Vote in a poll. Specify the message_id of the poll message and the option to vote for "
                    "either by its 0-based index or by its exact text. Pass an empty list to retract your vote."
                ),
            ),
            Tool.from_function(
                self._get_message_button_options,
                name="get_message_button_options",
                description=(
                    "Get clickable button options for a message with Telegram buttons. "
                    "Returns each button with 0-based index, row, column, and text."
                ),
            ),
            Tool.from_function(
                self._click_message_button,
                name="click_message_button",
                description=(
                    "Click a Telegram button in a message. Select exactly one of: button_index, "
                    "button_text, or (row and column)."
                ),
            ),
            Tool.from_function(
                self._get_user_profile_photo,
                name="get_user_profile_photo",
                description=(
                    "Get a user's profile photo. Returns a resource_uri that can be used with send_message "
                    "as file_uri or passed to vision-capable models. User can be specified by username (e.g. 'john'), "
                    "user_id (e.g. 123456), or phone number (e.g. '+1234567890')."
                ),
            ),
        ]
        if is_bot:
            tools = [
                t
                for t in tools
                if t.name not in {"send_poll_vote", "click_message_button"}
            ]
        return tools

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
            ResourceTemplate.from_function(
                self._get_user_profile_photo,
                name="get_user_profile_photo",
                uri_template="telegram://user/{user}/profile_photo",
                description="Access user profile photo bytes resource for use with other tools, such as sending as a file or passing to vision models.",
            ),
        ]

    def _get_chat_id(self) -> int:
        """Get the chat ID."""
        return self._chat_id

    async def _get_poll_results(self, message_id: int) -> dict:
        """Fetch live poll results from Telegram for a message containing a poll."""
        chat = await self._client.get_entity(self._chat_id)
        msg: Message = await self._client.get_messages(chat, ids=message_id)
        if msg is None:
            return {"error": f"Message {message_id} not found."}
        if not isinstance(msg.media, MessageMediaPoll):
            return {"error": f"Message {message_id} does not contain a poll."}

        poll = msg.media.poll
        results = msg.media.results

        question = (
            poll.question.text if hasattr(poll.question, "text") else str(poll.question)
        )

        vote_counts = {r.option: r.voters for r in (results.results or [])}
        chosen = {r.option for r in (results.results or []) if r.chosen}
        correct = {
            r.option for r in (results.results or []) if getattr(r, "correct", False)
        }

        options = []
        for i, answer in enumerate(poll.answers):
            opt_text = (
                answer.text.text if hasattr(answer.text, "text") else str(answer.text)
            )
            entry = {
                "index": i,
                "option": opt_text,
                "voters": vote_counts.get(answer.option, 0),
                "chosen": answer.option in chosen,
            }
            if poll.quiz:
                entry["correct"] = answer.option in correct
            options.append(entry)

        return {
            "message_id": message_id,
            "question": question,
            "options": options,
            "total_voters": results.total_voters or 0,
            "closed": poll.closed,
            "quiz": poll.quiz,
            "multiple_choice": poll.multiple_choice,
        }

    async def _send_poll_vote(
        self,
        message_id: int,
        options: list[int | str],
    ) -> dict:
        """Vote in a poll. Each entry in options is either a 0-based index or the exact option text.
        Pass an empty list to retract the current vote."""
        chat = await self._client.get_entity(self._chat_id)
        msg: Message = await self._client.get_messages(chat, ids=message_id)
        if msg is None:
            return {"error": f"Message {message_id} not found."}
        if not isinstance(msg.media, MessageMediaPoll):
            return {"error": f"Message {message_id} does not contain a poll."}

        poll = msg.media.poll
        if poll.closed:
            return {"error": "Poll is closed and no longer accepts votes."}

        chosen_bytes: list[bytes] = []
        for opt in options:
            if isinstance(opt, int):
                if opt < 0 or opt >= len(poll.answers):
                    return {
                        "error": f"Option index {opt} is out of range (0–{len(poll.answers) - 1})."
                    }
                chosen_bytes.append(poll.answers[opt].option)
            else:
                match = next(
                    (
                        a.option
                        for a in poll.answers
                        if (a.text.text if hasattr(a.text, "text") else str(a.text))
                        == opt
                    ),
                    None,
                )
                if match is None:
                    valid = [
                        a.text.text if hasattr(a.text, "text") else str(a.text)
                        for a in poll.answers
                    ]
                    return {
                        "error": f"Option {opt!r} not found. Valid options: {valid}"
                    }
                chosen_bytes.append(match)

        await self._client(
            SendVoteRequest(
                peer=chat,
                msg_id=message_id,
                options=chosen_bytes,
            )
        )

        if not chosen_bytes:
            return {"message_id": message_id, "result": "vote retracted"}
        voted_texts = [
            (a.text.text if hasattr(a.text, "text") else str(a.text))
            for a in poll.answers
            if a.option in chosen_bytes
        ]
        return {"message_id": message_id, "result": "voted", "options": voted_texts}

    async def _get_message_button_options(self, message_id: int) -> dict:
        """Return clickable button options for a Telegram message."""
        chat = await self._client.get_entity(self._chat_id)
        msg: Message = await self._client.get_messages(chat, ids=message_id)
        if msg is None:
            return {"error": f"Message {message_id} not found."}

        buttons = getattr(msg, "buttons", None)
        if not buttons:
            return {
                "message_id": message_id,
                "has_buttons": False,
                "buttons": [],
            }

        flattened = []
        idx = 0
        for row_index, row in enumerate(buttons):
            for column_index, button in enumerate(row):
                flattened.append(
                    {
                        "index": idx,
                        "row": row_index,
                        "column": column_index,
                        "text": getattr(button, "text", "") or "",
                    }
                )
                idx += 1

        return {
            "message_id": message_id,
            "has_buttons": True,
            "buttons": flattened,
        }

    async def _click_message_button(
        self,
        message_id: int,
        button_index: int | None = None,
        button_text: str | None = None,
        row: int | None = None,
        column: int | None = None,
    ) -> dict:
        """Click a Telegram message button by index, exact text, or row/column position."""
        selectors = 0
        selectors += 1 if button_index is not None else 0
        selectors += 1 if button_text is not None else 0
        selectors += 1 if (row is not None or column is not None) else 0

        if selectors != 1:
            return {
                "error": (
                    "Specify exactly one selector: button_index, button_text, "
                    "or (row and column)."
                )
            }

        if (row is None) != (column is None):
            return {"error": "Both row and column must be provided together."}

        chat = await self._client.get_entity(self._chat_id)
        msg: Message = await self._client.get_messages(chat, ids=message_id)
        if msg is None:
            return {"error": f"Message {message_id} not found."}

        buttons = getattr(msg, "buttons", None)
        if not buttons:
            return {
                "error": f"Message {message_id} does not contain clickable buttons."
            }

        try:
            if button_index is not None:
                if button_index < 0:
                    return {"error": "button_index must be >= 0."}
                await msg.click(i=button_index)

                selected = await self._button_at_flat_index(msg, button_index)
                return {
                    "message_id": message_id,
                    "result": "clicked",
                    "selector": {"button_index": button_index},
                    "button": selected,
                }

            if button_text is not None:
                await msg.click(text=button_text)
                return {
                    "message_id": message_id,
                    "result": "clicked",
                    "selector": {"button_text": button_text},
                }

            await msg.click(i=row, j=column)
            selected = await self._button_at_position(msg, row, column)
            return {
                "message_id": message_id,
                "result": "clicked",
                "selector": {"row": row, "column": column},
                "button": selected,
            }
        except Exception as e:
            logger.error(
                "Error clicking button for message_id=%s in chat_id=%s: %s",
                message_id,
                self._chat_id,
                e,
                exc_info=True,
            )
            return {"error": f"Failed to click button: {str(e)}"}

    async def _button_at_flat_index(self, msg: Message, index: int) -> dict | None:
        buttons = getattr(msg, "buttons", None)
        if not buttons:
            return None

        idx = 0
        for row_index, row in enumerate(buttons):
            for column_index, button in enumerate(row):
                if idx == index:
                    return {
                        "index": idx,
                        "row": row_index,
                        "column": column_index,
                        "text": getattr(button, "text", "") or "",
                    }
                idx += 1

        return None

    async def _button_at_position(
        self, msg: Message, row: int, column: int
    ) -> dict | None:
        buttons = getattr(msg, "buttons", None)
        if not buttons:
            return None
        if row < 0 or row >= len(buttons):
            return None
        if column < 0 or column >= len(buttons[row]):
            return None

        button = buttons[row][column]
        flat_index = 0
        for row_index, buttons_row in enumerate(buttons):
            if row_index < row:
                flat_index += len(buttons_row)
            else:
                break
        flat_index += column

        return {
            "index": flat_index,
            "row": row,
            "column": column,
            "text": getattr(button, "text", "") or "",
        }

    async def _send_message(
        self,
        ctx: Context,
        message: str = "",
        reply_to: int | None = None,
        schedule: hints.DateLike | None = None,
        file_uri: str | None = None,
    ):
        try:
            fingerprint = self._message_fingerprint(
                message=message,
                reply_to=reply_to,
                schedule=schedule,
                file_uri=file_uri,
            )
            if fingerprint in self._sent_message_fingerprints:
                dedupe_response = (
                    f"DUPLICATE_SUPPRESSED fingerprint={fingerprint[:12]} "
                    f"reply_to={reply_to} file_uri={file_uri}"
                )
                logger.info(dedupe_response)
                return dedupe_response

            self._sent_message_fingerprints.add(fingerprint)

            async with self._client.action(self._chat_id, "typing"):
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
                        file = await self._client.upload_file(file, file_name=file_name)

                await asyncio.sleep(0.1)
                response = await self._client.send_message(
                    self._chat_id,
                    message,
                    reply_to=reply_to,
                    file=file,
                    schedule=schedule,
                    parse_mode="markdown",
                )
                await self._store_sent_message(response)
                with_message_id = f"message_id={response.id}"
                in_reply_to = f"reply_to={reply_to}" if reply_to is not None else ""
                as_scheduled = (
                    f"SCHEDULED for {schedule}" if schedule is not None else "SENT"
                )
                with_content = f"with content: {message}" if message else ""
                with_file = f"and file_uri: {file_uri}" if file_uri else ""
                response = " ".join(
                    filter(
                        None,
                        [
                            as_scheduled,
                            with_message_id,
                            in_reply_to,
                            with_content,
                            with_file,
                        ],
                    )
                ).strip()

                logger.info(response)
                return response
        except Exception as e:
            logger.error(
                f"Error sending message to chat_id={self._chat_id}: {e}", exc_info=True
            )
            raise e

    def _message_fingerprint(
        self,
        message: str,
        reply_to: int | None,
        schedule: hints.DateLike | None,
        file_uri: str | None,
    ) -> str:
        normalized_message = re.sub(r"\s+", " ", message or "").strip()
        payload = "|".join(
            [
                normalized_message,
                str(reply_to) if reply_to is not None else "",
                str(schedule) if schedule is not None else "",
                file_uri or "",
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _get_telegram_cache_resource(self, cache_id: str):
        uri = f"telegram://cache/{cache_id}"
        entry = self._resource_cache.get(uri)
        if entry is None:
            raise KeyError(f"Unknown or expired cached resource: {uri}")

        return entry

    async def _get_message_media(self, message_id: int):
        """Download media from a message and return it as bytes."""
        try:
            chat = await self._client.get_entity(self._chat_id)
            message: Message = await self._client.get_messages(chat, ids=message_id)
            if not message:
                return None
            if not message.media:
                return None

            data = await self._client.download_media(message, file=bytes)
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
            logger.error(
                f"Error downloading media from message_id={message_id}: {e}",
                exc_info=True,
            )
            raise e

    async def _get_user_profile_photo(self, user: str | int):
        """Download a user's profile photo and return it as a resource."""
        try:
            entity = await self._client.get_entity(user)
            photo = await self._client.download_profile_photo(entity, file=bytes)

            if photo is None:
                return None

            mime_type = "image/jpeg"
            user_id = getattr(entity, "id", "unknown")

            return ResourceResult(
                contents=[ResourceContent(content=photo, mime_type=mime_type)],
                meta={"file_name": f"profile_photo_{user_id}.jpg", "user_id": user_id},
            )
        except Exception as e:
            logger.error(
                f"Error downloading profile photo for user={user}: {e}",
                exc_info=True,
            )
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
            await store_sent_message(session, message, self._chat_id, self._message_id)

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
            logger.error(
                f"Failed to decode pickle content for resource: {e}", exc_info=True
            )
            raise ValueError("Invalid pickle content") from e
