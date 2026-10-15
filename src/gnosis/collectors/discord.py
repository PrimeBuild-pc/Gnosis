from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Iterable
from typing import Any

import discord

from ..config import Settings, SourceConfig
from ..db import Database
from ..i18n import message, normalize_locale
from ..rag import RAG, cited_message_ids
from ..types import CollectedMessage

Emit = Callable[[CollectedMessage], int | None]
Delete = Callable[[str, str, str], None]

log = logging.getLogger(__name__)

_MAX_REPLY = 2000


class CommandTranslator(discord.app_commands.Translator):
    async def translate(self, string, locale, context):
        key = string.extras.get("key")
        return message(key, locale.value) if key else None


def is_authorized(member_role_ids: Iterable[int], allowed_role_ids: frozenset[int]) -> bool:
    return bool(allowed_role_ids) and any(
        role_id in allowed_role_ids for role_id in member_role_ids
    )


def allowed_roles_for(workspace: dict[str, Any] | None, fallback: frozenset[int]) -> frozenset[int]:
    """Require an explicit workspace; an empty allowlist revokes access."""
    if workspace is None:
        return frozenset()
    return frozenset(
        int(value) for value in workspace.get("allowed_role_ids", []) if str(value).isdigit()
    )


def readable_channels(interaction: discord.Interaction) -> list[str]:
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        return []
    return [
        str(channel.id)
        for channel in interaction.guild.text_channels
        if channel.permissions_for(interaction.user).view_channel
        and channel.permissions_for(interaction.user).read_message_history
    ]


def _format_answer(result: dict[str, Any]) -> str:
    text = result["answer"]
    if result["sources"]:
        lines = (
            f"{s['id']} — {s['platform']}/{s['community']} {s['url']}" for s in result["sources"]
        )
        text = f"{text}\n\n" + "\n".join(lines)
    return text[:_MAX_REPLY]


async def run(
    settings: Settings,
    sources: list[SourceConfig],
    emit: Emit,
    delete: Delete,
    rag: RAG,
    db: Database,
    backfill_limit: int = 200,
) -> None:
    if not settings.discord_bot_token:
        raise ValueError("Missing DISCORD_BOT_TOKEN")
    allowed = {int(source.external_id) for source in sources}
    allowed_roles = frozenset(settings.discord_allowed_role_ids)
    intents = discord.Intents.default()
    intents.message_content = True

    class Client(discord.Client):
        backfilled = False

        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            self.tree = discord.app_commands.CommandTree(self)

        async def setup_hook(self) -> None:
            await self.tree.set_translator(CommandTranslator())
            await self.tree.sync()

        async def collect(self, message: discord.Message) -> None:
            if message.channel.id not in allowed or not message.content:
                return
            emit(
                CollectedMessage(
                    platform="discord",
                    source_external_id=str(message.channel.id),
                    external_id=str(message.id),
                    author=str(message.author),
                    author_id=str(message.author.id),
                    sent_at=message.created_at,
                    text=message.content,
                    url=message.jump_url,
                    thread_id=(
                        str(message.reference.message_id)
                        if message.reference and message.reference.message_id
                        else None
                    ),
                    metadata={"guild_id": str(message.guild.id) if message.guild else None},
                )
            )

        def publish_available(self) -> None:
            """Publish visible channels for the dashboard dropdown instead of manual IDs."""
            db.replace_available_sources(
                "discord",
                [
                    {
                        "external_id": str(channel.id),
                        "name": f"#{channel.name}",
                        "workspace_external_id": str(guild.id),
                        "workspace_name": guild.name,
                    }
                    for guild in self.guilds
                    for channel in guild.text_channels
                ],
            )

        async def refresh_available_loop(self) -> None:
            while True:
                try:
                    self.publish_available()
                except Exception:
                    log.exception("Discord: available channel refresh failed")
                await asyncio.sleep(3600)

        async def on_ready(self) -> None:
            if self.backfilled:
                return
            self.backfilled = True
            self.loop.create_task(self.refresh_available_loop())
            for channel_id in allowed:
                channel = self.get_channel(channel_id)
                if isinstance(channel, (discord.TextChannel, discord.Thread)):
                    async for message in channel.history(limit=backfill_limit):
                        await self.collect(message)

        async def on_message(self, message: discord.Message) -> None:
            await self.collect(message)

        async def on_message_edit(self, _before: discord.Message, after: discord.Message) -> None:
            await self.collect(after)

        async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent) -> None:
            if payload.channel_id in allowed:
                delete("discord", str(payload.channel_id), str(payload.message_id))

    client = Client(intents=intents, allowed_mentions=discord.AllowedMentions.none())

    def member_role_ids(interaction: discord.Interaction) -> tuple[int, ...]:
        if isinstance(interaction.user, discord.Member):
            return tuple(role.id for role in interaction.user.roles)
        return ()

    def context_for(interaction: discord.Interaction) -> tuple[frozenset[int], int | None]:
        """Resolve allowed roles and workspace for the command's server."""
        workspace = (
            db.workspace_for_external_id("discord", str(interaction.guild_id))
            if interaction.guild_id
            else None
        )
        return allowed_roles_for(workspace, allowed_roles), (workspace["id"] if workspace else None)

    @client.tree.command(
        name="ask",
        description=discord.app_commands.locale_str(
            message("ask_description"), key="ask_description"
        ),
    )
    @discord.app_commands.describe(
        question=discord.app_commands.locale_str(
            message("question_description"), key="question_description"
        )
    )
    @discord.app_commands.rename(
        question=discord.app_commands.locale_str("question", key="question_name")
    )
    async def ask_command(interaction: discord.Interaction, question: str) -> None:
        locale = normalize_locale(str(getattr(interaction, "locale", "en")))
        roles, workspace_id = context_for(interaction)
        if workspace_id is None or not is_authorized(member_role_ids(interaction), roles):
            await interaction.response.send_message(message("unauthorized", locale), ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            result = await rag.ask(
                question,
                workspace_id=workspace_id,
                discord_guild_id=str(interaction.guild_id),
                source_external_ids=readable_channels(interaction),
                locale=locale,
            )
            await interaction.followup.send(_format_answer(result), ephemeral=True)
        except Exception:
            log.exception("Discord: answer failed")
            await interaction.followup.send(message("answer_error", locale), ephemeral=True)

    @client.tree.command(
        name="digest",
        description=discord.app_commands.locale_str(
            message("digest_description"), key="digest_description"
        ),
    )
    async def digest_command(interaction: discord.Interaction) -> None:
        locale = normalize_locale(str(getattr(interaction, "locale", "en")))
        roles, workspace_id = context_for(interaction)
        if workspace_id is None or not is_authorized(member_role_ids(interaction), roles):
            await interaction.response.send_message(message("unauthorized", locale), ephemeral=True)
            return
        try:
            digests = db.list_digests(limit=1, workspace_id=workspace_id)
            if not digests:
                text = message("no_digest", locale)
            else:
                markdown = digests[0]["markdown"]
                cited = cited_message_ids(markdown)
                inputs = set(digests[0].get("message_ids", []))
                accessible = db.accessible_discord_messages(
                    inputs, workspace_id, str(interaction.guild_id), readable_channels(interaction)
                )
                if not inputs or not cited or not cited <= inputs or inputs != accessible:
                    text = message("digest_denied", locale)
                else:
                    text = markdown[:_MAX_REPLY]
        except Exception:
            log.exception("Discord: digest failed")
            text = message("digest_error", locale)
        await interaction.response.send_message(text, ephemeral=True)

    @client.tree.command(
        name="help",
        description=discord.app_commands.locale_str(
            message("help_description"), key="help_description"
        ),
    )
    async def help_command(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            message("help", str(getattr(interaction, "locale", "en"))), ephemeral=True
        )

    await client.start(settings.discord_bot_token)
