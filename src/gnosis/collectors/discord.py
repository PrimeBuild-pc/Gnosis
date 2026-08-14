from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

import discord

from ..config import Settings, SourceConfig
from ..db import Database
from ..rag import RAG
from ..types import CollectedMessage

Emit = Callable[[CollectedMessage], int | None]
Delete = Callable[[str, str, str], None]

_MAX_REPLY = 2000
_UNAUTHORIZED = "Non autorizzato, o comando non configurato (GNOSIS_DISCORD_ALLOWED_ROLE_IDS)."


def is_authorized(member_role_ids: Iterable[int], allowed_role_ids: frozenset[int]) -> bool:
    return bool(allowed_role_ids) and any(
        role_id in allowed_role_ids for role_id in member_role_ids
    )


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
        raise ValueError("DISCORD_BOT_TOKEN mancante")
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

        async def on_ready(self) -> None:
            if self.backfilled:
                return
            self.backfilled = True
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

    client = Client(intents=intents)

    def member_role_ids(interaction: discord.Interaction) -> tuple[int, ...]:
        if isinstance(interaction.user, discord.Member):
            return tuple(role.id for role in interaction.user.roles)
        return ()

    @client.tree.command(name="ask", description="Chiedi qualcosa alle fonti raccolte")
    @discord.app_commands.describe(domanda="La tua domanda")
    async def ask_command(interaction: discord.Interaction, domanda: str) -> None:
        if not is_authorized(member_role_ids(interaction), allowed_roles):
            await interaction.response.send_message(_UNAUTHORIZED, ephemeral=True)
            return
        await interaction.response.defer()
        result = await rag.ask(domanda)
        await interaction.followup.send(_format_answer(result))

    @client.tree.command(name="digest", description="Ultimo digest settimanale")
    async def digest_command(interaction: discord.Interaction) -> None:
        if not is_authorized(member_role_ids(interaction), allowed_roles):
            await interaction.response.send_message(_UNAUTHORIZED, ephemeral=True)
            return
        digests = db.list_digests(limit=1)
        if not digests:
            await interaction.response.send_message("Nessun digest disponibile.", ephemeral=True)
            return
        await interaction.response.send_message(digests[0]["markdown"][:_MAX_REPLY])

    await client.start(settings.discord_bot_token)
