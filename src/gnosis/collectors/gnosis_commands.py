"""/gnosis command group: private member channel, personal API key and server summaries."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import discord
from openai import AsyncOpenAI

from .. import secretbox
from ..config import Settings
from ..db import Database
from ..digest import TextFn, language_name, link_citations, summarize
from ..i18n import message, normalize_locale
from ..notify import split_message

log = logging.getLogger(__name__)

RESUME_LIMIT = 2000
CATEGORY_NAME = "Gnosis"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


def parse_period(
    start: str | None, end: str | None, zone: ZoneInfo
) -> tuple[datetime | None, datetime | None]:
    """DD/MM/YYYY dates in the server timezone; the end date is included."""

    def day(value: str) -> datetime:
        return datetime.strptime(value.strip(), "%d/%m/%Y").replace(tzinfo=zone)

    first = day(start) if start else None
    last = day(end) + timedelta(days=1) if end else None
    if first and last and first >= last:
        raise ValueError("start after end")
    return first, last


def apply_channel_prefs(readable: list[str], prefs: dict[str, Any] | None) -> list[str]:
    """Narrow the member's readable channels with their own choice; never widen them."""
    if not prefs:
        return readable
    chosen = set(prefs["channel_ids"])
    if prefs["mode"] == "only":
        return [channel for channel in readable if channel in chosen]
    return [channel for channel in readable if channel not in chosen]


def validate_key_input(base_url: str, model: str) -> str | None:
    """Return the i18n key of the problem, or None when the input is acceptable."""
    if base_url and not base_url.startswith("https://"):
        return "key_invalid_url"
    if base_url and not model:
        return "key_model_required"
    return None


def user_text_fn(api_key: str, base_url: str, model: str) -> TextFn:
    client = AsyncOpenAI(api_key=api_key, base_url=base_url or None)
    chosen = model or DEFAULT_OPENAI_MODEL

    async def text(system: str, prompt: str) -> str:
        response = await client.chat.completions.create(
            model=chosen,
            temperature=0,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        )
        return (response.choices[0].message.content or "").strip()

    return text


async def build_resume(
    text: TextFn, messages: list[dict[str, Any]], locale: str, period: str, capped: bool
) -> list[str]:
    """Summary chunks ready to post: header, optional cap notice, linked citations."""
    markdown = await summarize(
        text, messages, language_name(locale), title="summary of this Discord server"
    )
    header = message("resume_header", locale).format(period=period, count=len(messages))
    if capped:
        header += "\n_" + message("resume_capped", locale).format(count=len(messages)) + "_"
    return split_message(f"{header}\n\n{link_citations(markdown, messages)}")


def register(
    client: Any,
    settings: Settings,
    db: Database,
    readable_channels: Callable[[discord.Interaction], list[str]],
) -> None:
    locale_str = discord.app_commands.locale_str

    def desc(key: str) -> Any:
        return locale_str(message(key), key=key)

    def locale_of(interaction: discord.Interaction) -> str:
        return normalize_locale(str(getattr(interaction, "locale", "en")))

    async def reply(interaction: discord.Interaction, key: str, **values: str) -> None:
        text = message(key, locale_of(interaction)).format(**values)
        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)

    def workspace_of(interaction: discord.Interaction) -> dict[str, Any] | None:
        if not interaction.guild_id:
            return None
        return db.workspace_for_external_id("discord", str(interaction.guild_id))

    async def member_workspace(interaction: discord.Interaction) -> dict[str, Any] | None:
        """The server's workspace when members may use /gnosis; otherwise reply and None."""
        workspace = workspace_of(interaction) if interaction.guild is not None else None
        if workspace is None:
            await reply(interaction, "not_configured")
            return None
        if workspace.get("member_commands_enabled") is False:
            await reply(interaction, "member_commands_disabled")
            return None
        return workspace

    group = discord.app_commands.Group(
        name="gnosis", description=desc("gnosis_description"), guild_only=True
    )

    async def private_channel_for(interaction: discord.Interaction) -> tuple[Any, bool]:
        """The member's private channel, created on first use. (None, False) after replying
        when it cannot be created."""
        guild = interaction.guild
        user = interaction.user
        existing_id = db.private_channel(str(guild.id), str(user.id))
        existing = guild.get_channel(int(existing_id)) if existing_id else None
        if existing is not None:
            return existing, False
        if not guild.me.guild_permissions.manage_channels:
            await reply(interaction, "need_manage_channels")
            return None, False
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        hidden = discord.PermissionOverwrite(view_channel=False)
        member_access = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True
        )
        category = discord.utils.get(guild.categories, name=CATEGORY_NAME)
        if category is None:
            category = await guild.create_category(
                CATEGORY_NAME,
                overwrites={guild.default_role: hidden, guild.me: member_access},
            )
        channel = await guild.create_text_channel(
            f"gnosis-{user.name}"[:90],
            category=category,
            topic=message("private_topic", locale_of(interaction)),
            overwrites={guild.default_role: hidden, user: member_access, guild.me: member_access},
        )
        # Registered before any message is sent, so the collector never reads it.
        db.set_private_channel(str(guild.id), str(user.id), str(channel.id))
        await channel.send(
            message("private_welcome", locale_of(interaction)).format(user=user.mention),
            allowed_mentions=discord.AllowedMentions(users=[user]),
        )
        return channel, True

    @group.command(name="create", description=desc("create_description"))
    async def create(interaction: discord.Interaction) -> None:
        if await member_workspace(interaction) is None:
            return
        channel, created = await private_channel_for(interaction)
        if channel is not None:
            key = "private_created" if created else "private_exists"
            await reply(interaction, key, channel=channel.mention)

    class KeyModal(discord.ui.Modal):
        def __init__(self, locale: str) -> None:
            super().__init__(title=message("key_modal_title", locale))
            self.locale = locale
            self.api_key = discord.ui.TextInput(
                label=message("key_label", locale), max_length=400, required=True
            )
            self.base_url = discord.ui.TextInput(
                label=message("base_url_label", locale),
                placeholder="https://api.deepseek.com",
                max_length=200,
                required=False,
            )
            self.model = discord.ui.TextInput(
                label=message("model_label", locale),
                placeholder=DEFAULT_OPENAI_MODEL,
                max_length=100,
                required=False,
            )
            for item in (self.api_key, self.base_url, self.model):
                self.add_item(item)

        async def on_submit(self, interaction: discord.Interaction) -> None:
            base_url = self.base_url.value.strip().rstrip("/")
            model = self.model.value.strip()
            problem = validate_key_input(base_url, model)
            if problem:
                await reply(interaction, problem)
                return
            db.set_user_llm_key(
                str(interaction.user.id),
                secretbox.encrypt(settings.secret_key, self.api_key.value.strip()),
                base_url,
                model,
            )
            await reply(interaction, "key_saved")

    @group.command(name="key", description=desc("key_description"))
    async def key(interaction: discord.Interaction) -> None:
        if await member_workspace(interaction) is None:
            return
        await interaction.response.send_modal(KeyModal(locale_of(interaction)))

    @group.command(name="forget", description=desc("forget_description"))
    async def forget(interaction: discord.Interaction) -> None:
        removed = db.delete_user_llm_key(str(interaction.user.id))
        await reply(interaction, "key_forgotten" if removed else "no_key_saved")

    @group.command(name="resume", description=desc("resume_description"))
    @discord.app_commands.describe(start=desc("start_description"), end=desc("end_description"))
    async def resume(
        interaction: discord.Interaction, start: str | None = None, end: str | None = None
    ) -> None:
        locale = locale_of(interaction)
        workspace = await member_workspace(interaction)
        if workspace is None:
            return
        guild_id, user_id = str(interaction.guild_id), str(interaction.user.id)
        stored = db.user_llm_key(user_id)
        api_key = (
            secretbox.decrypt(settings.secret_key, stored["api_key_encrypted"]) if stored else None
        )
        if not api_key:
            await reply(interaction, "need_key")
            return
        try:
            first, last = parse_period(start, end, settings.zoneinfo)
        except ValueError:
            await reply(interaction, "bad_date")
            return
        # Without dates: only what is new since this member's previous summary.
        undated = not start and not end
        since = db.member_last_resume(guild_id, user_id) if undated else None
        if since:
            first = since
        channels = apply_channel_prefs(
            readable_channels(interaction), db.member_channel_prefs(guild_id, user_id)
        )
        # Admin exclusions are applied by messages_for_member (excluded sources are disabled).
        rows = db.messages_for_member(
            workspace["id"], guild_id, channels, first, last, RESUME_LIMIT
        )
        if not rows:
            await reply(interaction, "no_new_messages" if since else "no_messages")
            return
        # Usable from any channel: the summary always goes to the member's private channel.
        channel, _ = await private_channel_for(interaction)
        if channel is None:
            return
        if since:
            period = message("resume_since_last", locale).format(
                date=since.astimezone(settings.zoneinfo).strftime("%d/%m/%Y %H:%M")
            )
        else:
            period = f"{start or message('resume_all_time', locale)} → {end or '…'}"
        await reply(interaction, "resume_working", count=str(len(rows)), channel=channel.mention)
        try:
            chunks = await build_resume(
                user_text_fn(api_key, stored["base_url"], stored["model"]),
                rows,
                locale,
                period,
                capped=len(rows) >= RESUME_LIMIT,
            )
            for chunk in chunks:
                await channel.send(chunk, allowed_mentions=discord.AllowedMentions.none())
            if undated:
                db.set_member_last_resume(guild_id, user_id, rows[-1]["sent_at"])
        except Exception:
            log.exception("Discord: /gnosis resume failed")
            await channel.send(message("resume_error", locale))

    class ChannelPicker(discord.ui.View):
        def __init__(self, mode: str, locale: str) -> None:
            super().__init__(timeout=300)
            self.mode = mode
            select = discord.ui.ChannelSelect(
                channel_types=[discord.ChannelType.text, discord.ChannelType.news],
                min_values=1,
                max_values=25,
                placeholder=message(f"channels_pick_{mode}", locale),
            )
            select.callback = self.picked
            self.select = select
            self.add_item(select)

        async def picked(self, interaction: discord.Interaction) -> None:
            ids = [str(channel.id) for channel in self.select.values]
            db.set_member_channel_prefs(
                str(interaction.guild_id), str(interaction.user.id), self.mode, ids
            )
            mentions = ", ".join(f"<#{channel_id}>" for channel_id in ids)
            await interaction.response.edit_message(
                content=message(f"channels_saved_{self.mode}", locale_of(interaction)).format(
                    channels=mentions
                ),
                view=None,
            )

    mode_choices = [
        discord.app_commands.Choice(name=desc(f"mode_{value}"), value=value)
        for value in ("only", "exclude", "all")
    ]

    @group.command(name="channels", description=desc("channels_description"))
    @discord.app_commands.describe(mode=desc("mode_description"))
    @discord.app_commands.choices(mode=mode_choices)
    async def channels(
        interaction: discord.Interaction, mode: discord.app_commands.Choice[str]
    ) -> None:
        if await member_workspace(interaction) is None:
            return
        if mode.value == "all":
            db.set_member_channel_prefs(
                str(interaction.guild_id), str(interaction.user.id), None, []
            )
            await reply(interaction, "channels_cleared")
            return
        await interaction.response.send_message(
            message(f"channels_pick_{mode.value}", locale_of(interaction)),
            view=ChannelPicker(mode.value, locale_of(interaction)),
            ephemeral=True,
        )

    client.tree.add_command(group)
