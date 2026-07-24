from __future__ import annotations

from collections.abc import Callable

import discord

from ..config import Settings, SourceConfig
from ..types import CollectedMessage

Emit = Callable[[CollectedMessage], int | None]
Delete = Callable[[str, str, str], None]


async def run(
    settings: Settings,
    sources: list[SourceConfig],
    emit: Emit,
    delete: Delete,
    backfill_limit: int = 200,
) -> None:
    if not settings.discord_bot_token:
        raise ValueError("DISCORD_BOT_TOKEN mancante")
    allowed = {int(source.external_id) for source in sources}
    intents = discord.Intents.default()
    intents.message_content = True

    class Client(discord.Client):
        backfilled = False

        async def collect(self, message: discord.Message) -> None:
            if message.channel.id not in allowed or not message.content:
                return
            emit(
                CollectedMessage(
                    platform="discord",
                    source_external_id=str(message.channel.id),
                    external_id=str(message.id),
                    author=str(message.author),
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

    await Client(intents=intents).start(settings.discord_bot_token)
