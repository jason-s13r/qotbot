from dataclasses import dataclass
import inspect
import logging
import functools
from typing import List, Tuple
from telethon import TelegramClient, events, types
from qotbot.utils.config import TELEGRAM_BOT_OWNER

logger = logging.getLogger(__name__)


class Commands:
    @dataclass
    class Permissions:
        chat_admin: bool = False
        bot_owner: bool = False
        is_scoped: bool = False
        must_reply: bool = False

    @dataclass
    class CommandInfo:
        prefix: str
        command: str
        permissions: "Commands.Permissions"
        description: str | None

    def __init__(self, client: TelegramClient | None = None):
        self._client = client
        self._commands: List[Commands.CommandInfo] = []
        self._me: types.User | None = None
        self._registry: List[Tuple[events.NewMessage, callable]] = []
        self._registries: List["Commands"] = []

    def use(self, other: "Commands") -> "Commands":
        self._registries.append(other)
        return self

    async def register(self, client: TelegramClient, me: types.User | None = None):
        self._client = client
        self._me = me
        if not me:
            self._me = await client.get_me()

        for event, handler in self._registry:
            self._client.add_event_handler(handler, event)

        for registry in self._registries:
            await registry.register(client, self._me)

    def slash(self, command: str, permissions: Permissions = Permissions()):
        return self._command("/", command, permissions)

    def bang(self, command: str, permissions: Permissions = Permissions()):
        return self._command("!", command, permissions)

    def _command(self, prefix: str, command: str, permissions: Permissions):
        """Decorator for command handlers with permission and scoping checks."""

        def decorator(func):
            sig = inspect.signature(func)
            wants_payload = len(sig.parameters) >= 2

            @functools.wraps(func)
            async def wrapper(event: events.NewMessage.Event):
                username = event.pattern_match.group(1)
                payload = event.pattern_match.group(2) or ""
                if not self._me:
                    self._me = await self._client.get_me()

                if permissions.bot_owner and event.sender_id != TELEGRAM_BOT_OWNER:
                    return

                if username and not await self._matches_username(username):
                    return

                if permissions.is_scoped:
                    if not await self._message_is_scoped(event, username):
                        return

                if permissions.chat_admin:
                    if not await self._message_is_sent_from_admin_or_bot_owner(event):
                        logger.debug(
                            f"Command {command} blocked: user_id={event.sender_id} is not admin"
                        )
                        return

                if permissions.must_reply:
                    if not await self._message_is_reply_to_bot(event):
                        logger.debug(f"Command {command} blocked: not a reply to bot")
                        return

                if wants_payload:
                    return await func(event, payload)
                return await func(event)

            pattern = rf"(?i)^{prefix}{command}(?:@(\w+))?(?:\s+(.*))?$"
            self._commands.append(
                Commands.CommandInfo(prefix, command, permissions, func.__doc__)
            )
            self._registry.append((events.NewMessage(pattern=pattern), wrapper))

            return wrapper

        return decorator

    def command_info(self):
        info = []
        info.extend(self._commands)
        for reg in self._registries:
            nested = reg.command_info()
            info.extend(nested)
        return info

    async def build_help_message(self):
        if not self._me:
            self._me = await self._client.get_me()

        def _command_help(grouping: list[Commands.CommandInfo]) -> list[str]:
            help_list = []
            for info in grouping:
                scoped = f"@{self._me.username}" if info.permissions.is_scoped else ""
                cmd_str = f"{info.prefix}{info.command}{scoped}"
                constraints = (
                    "(must reply to bot)" if info.permissions.must_reply else ""
                )
                help_list.append(
                    f"- {cmd_str}: {info.description}{(' ' + constraints) if constraints else ''}"
                )
            return help_list

        info = self.command_info()
        commands = sorted(info, key=lambda x: x.prefix + x.command)
        owner_commands = list(filter(lambda x: x.permissions.bot_owner, commands))
        admin_commands = list(filter(lambda x: x.permissions.chat_admin, commands))
        public_commands = list(
            filter(
                lambda x: not x.permissions.bot_owner and not x.permissions.chat_admin,
                commands,
            )
        )

        help_lines = ["**Available commands:**"]
        if owner_commands:
            help_lines.append("\n**Owner commands:**")
            help_lines.extend(_command_help(owner_commands))
        if admin_commands:
            help_lines.append("\n**Chat Admin commands:**")
            help_lines.extend(_command_help(admin_commands))
        if public_commands:
            help_lines.append("\n**Public commands:**")
            help_lines.extend(_command_help(public_commands))

        return "\n".join(help_lines)

    async def _message_is_sent_from_admin_or_bot_owner(
        self, event: events.NewMessage.Event
    ) -> bool:
        if event.sender_id != TELEGRAM_BOT_OWNER:
            try:
                admins = await self._client.get_participants(
                    event.chat_id, filter=types.ChannelParticipantsAdmins
                )
                if not any(
                    [admin.id for admin in admins if admin.id == event.sender_id]
                ):
                    return False
            except Exception as e:
                logger.error(f"Error checking admin rights: {e}", exc_info=True)
                return False
        return True

    async def _message_is_scoped(
        self, event: events.NewMessage.Event, username: str | None
    ) -> bool:
        """Check if command is scoped to this bot (reply, @mention, or private chat)."""
        if not self._me:
            self._me = await self._client.get_me()

        return (
            event.is_private
            or await self._message_is_reply_to_bot(event)
            or await self._matches_username(username)
        )

    async def _message_is_reply_to_bot(self, event: events.NewMessage.Event) -> bool:
        replied = await event.get_reply_message()
        if not self._me:
            self._me = await self._client.get_me()
        return replied and replied.sender_id == self._me.id

    async def _matches_username(self, username: str) -> bool:
        if not self._me:
            self._me = await self._client.get_me()
        return username and username.lower() == self._me.username.lower()
