import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from gnosis.collectors import discord as collector
from gnosis.collectors.discord import is_authorized
from gnosis.config import Settings
from gnosis.i18n import message


def test_authorized_when_role_matches():
    assert is_authorized([42, 7], frozenset({7}))


def test_unauthorized_when_no_role_matches():
    assert not is_authorized([42, 7], frozenset({99}))


def test_unauthorized_when_no_roles():
    assert not is_authorized([], frozenset({7}))


def test_unauthorized_when_allowlist_empty():
    assert not is_authorized([7], frozenset())


@pytest.fixture
def command_harness(monkeypatch):
    commands = {}
    options = {}

    class FakeTree:
        def __init__(self, client):
            pass

        def command(self, name, **kwargs):
            def register(callback):
                commands[name] = callback
                return callback

            return register

    class FakeClient:
        def __init__(self, **kwargs):
            options.update(kwargs)

        async def start(self, token):
            assert token == "fake-token"

    class FakeMember:
        def __init__(self):
            self.roles = [SimpleNamespace(id=7)]

    def channel(channel_id, readable):
        return SimpleNamespace(
            id=channel_id,
            permissions_for=lambda member: SimpleNamespace(
                view_channel=readable, read_message_history=readable
            ),
        )

    monkeypatch.setattr(collector.discord, "Client", FakeClient)
    monkeypatch.setattr(collector.discord, "Member", FakeMember)
    monkeypatch.setattr(collector.discord.app_commands, "CommandTree", FakeTree)
    db = Mock()
    db.workspace_for_external_id.return_value = {"id": 11, "allowed_role_ids": ["7"]}
    db.list_digests.return_value = [{"markdown": "Only A [M1]", "message_ids": [1]}]
    db.accessible_discord_messages.return_value = {1}
    rag = SimpleNamespace(ask=AsyncMock(return_value={"answer": "A [M1]", "sources": []}))
    interaction = SimpleNamespace(
        guild_id=101,
        guild=SimpleNamespace(text_channels=[channel(10, True), channel(20, False)]),
        user=FakeMember(),
        response=SimpleNamespace(send_message=AsyncMock(), defer=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
    )
    asyncio.run(
        collector.run(
            Settings(discord_bot_token="fake-token", discord_allowed_role_ids=(7,)),
            [],
            Mock(),
            Mock(),
            rag,
            db,
        )
    )
    return commands, interaction, db, rag, options


@pytest.mark.parametrize("workspace", [None, {"id": 11, "allowed_role_ids": []}])
@pytest.mark.parametrize("command", ["ask", "digest"])
def test_unmapped_guild_and_revoked_roles_never_query(command_harness, workspace, command):
    commands, interaction, db, rag, _ = command_harness
    db.workspace_for_external_id.return_value = workspace
    args = (interaction, "question") if command == "ask" else (interaction,)
    asyncio.run(commands[command](*args))
    rag.ask.assert_not_called()
    db.list_digests.assert_not_called()
    interaction.response.send_message.assert_awaited_once()
    assert interaction.response.send_message.call_args.kwargs["ephemeral"] is True


def test_ask_scopes_guild_workspace_channels_and_private_reply(command_harness):
    commands, interaction, db, rag, options = command_harness
    asyncio.run(commands["ask"](interaction, "question"))
    db.workspace_for_external_id.assert_called_once_with("discord", "101")
    rag.ask.assert_awaited_once_with(
        "question", workspace_id=11, discord_guild_id="101", source_external_ids=["10"], locale="en"
    )
    interaction.response.defer.assert_awaited_once_with(ephemeral=True)
    assert interaction.followup.send.call_args.kwargs["ephemeral"] is True
    assert options["allowed_mentions"].everyone is False
    assert options["allowed_mentions"].users is False
    assert options["allowed_mentions"].roles is False


def test_dm_never_accesses_global_archive(command_harness):
    commands, interaction, db, rag, _ = command_harness
    interaction.guild_id = None
    interaction.guild = None
    interaction.user = SimpleNamespace()
    asyncio.run(commands["ask"](interaction, "question"))
    db.workspace_for_external_id.assert_not_called()
    rag.ask.assert_not_called()


@pytest.mark.parametrize("accessible,expected", [({1}, "Only A"), (set(), "unavailable")])
def test_digest_rechecks_current_source_access(command_harness, accessible, expected):
    commands, interaction, db, _, _ = command_harness
    db.accessible_discord_messages.return_value = accessible
    asyncio.run(commands["digest"](interaction))
    db.accessible_discord_messages.assert_called_once_with({1}, 11, "101", ["10"])
    call = interaction.response.send_message.call_args
    assert expected in call.args[0]
    assert call.kwargs["ephemeral"] is True


@pytest.mark.parametrize("provenance", [[], [1, 2]])
def test_digest_requires_all_inputs_even_uncited_private_messages(command_harness, provenance):
    commands, interaction, db, _, _ = command_harness
    db.list_digests.return_value = [{"markdown": "Only A [M1]", "message_ids": provenance}]
    db.accessible_discord_messages.return_value = {1}
    asyncio.run(commands["digest"](interaction))
    assert "unavailable" in interaction.response.send_message.call_args.args[0]


def test_provider_error_does_not_expose_details(command_harness):
    commands, interaction, _, rag, _ = command_harness
    rag.ask.side_effect = RuntimeError("private-provider-detail")
    asyncio.run(commands["ask"](interaction, "question"))
    assert "private-provider-detail" not in interaction.followup.send.call_args.args[0]
    assert interaction.followup.send.call_args.kwargs["ephemeral"] is True


@pytest.mark.parametrize(
    "locale,expected",
    [
        (collector.discord.Locale.american_english, "en"),
        (collector.discord.Locale.italian, "it"),
        (collector.discord.Locale.spain_spanish, "es"),
        (collector.discord.Locale.russian, "ru"),
        (collector.discord.Locale.chinese, "zh"),
        (collector.discord.Locale.taiwan_chinese, "zh"),
        (collector.discord.Locale.german, "en"),
    ],
)
def test_ask_uses_interaction_locale_without_changing_scope(command_harness, locale, expected):
    commands, interaction, _, rag, _ = command_harness
    interaction.locale = locale
    asyncio.run(commands["ask"](interaction, "question"))
    rag.ask.assert_awaited_once_with(
        "question",
        workspace_id=11,
        discord_guild_id="101",
        source_external_ids=["10"],
        locale=expected,
    )
    assert interaction.followup.send.call_args.kwargs["ephemeral"] is True


@pytest.mark.parametrize("locale", ["en", "it", "es", "ru", "zh", "unsupported"])
@pytest.mark.parametrize(
    "state", ["unauthorized", "answer_error", "no_digest", "digest_denied", "digest_error", "help"]
)
def test_command_messages_are_localized(command_harness, locale, state):
    commands, interaction, db, rag, _ = command_harness
    interaction.locale = locale
    command = "digest"
    if state == "unauthorized":
        db.workspace_for_external_id.return_value = None
        command = "ask"
    elif state == "answer_error":
        rag.ask.side_effect = RuntimeError("private-provider-detail")
        command = "ask"
    elif state == "no_digest":
        db.list_digests.return_value = []
    elif state == "digest_denied":
        db.accessible_discord_messages.return_value = set()
    elif state == "digest_error":
        db.list_digests.side_effect = RuntimeError("private-database-detail")
    else:
        command = "help"
    args = (interaction, "question") if command == "ask" else (interaction,)
    asyncio.run(commands[command](*args))
    reply = (
        interaction.followup.send if state == "answer_error" else interaction.response.send_message
    )
    reply.assert_awaited_once_with(message(state, locale), ephemeral=True)


@pytest.mark.parametrize("locale", list(collector.discord.Locale))
@pytest.mark.parametrize(
    "key",
    [
        "ask_description",
        "question_description",
        "question_name",
        "digest_description",
        "help_description",
    ],
)
def test_command_metadata_translator(locale, key):
    string = collector.discord.app_commands.locale_str(message(key), key=key)
    translated = asyncio.run(collector.CommandTranslator().translate(string, locale, None))
    assert translated == message(key, locale.value)
    assert len(translated) <= 100


def test_real_command_tree_serializes_localizations_offline(monkeypatch):
    payloads = {}
    sync = AsyncMock()
    monkeypatch.setattr(collector.discord.app_commands.CommandTree, "sync", sync)

    async def start(client, token):
        await client.setup_hook()
        translator = client.tree.translator
        assert isinstance(translator, collector.CommandTranslator)
        for command in client.tree.get_commands():
            payloads[command.name] = await command.get_translated_payload(client.tree, translator)

    monkeypatch.setattr(collector.discord.Client, "start", start)
    asyncio.run(
        collector.run(
            Settings(discord_bot_token="fake"),
            [],
            Mock(),
            Mock(),
            Mock(),
            Mock(),
        )
    )
    sync.assert_awaited_once()
    assert set(payloads) == {"ask", "digest", "help"}
    for locale in ("en-US", "it", "es-ES", "ru", "zh-CN", "zh-TW", "de"):
        for command in ("ask", "digest", "help"):
            assert payloads[command]["description_localizations"][locale] == message(
                f"{command}_description", locale
            )
        option = payloads["ask"]["options"][0]
        assert option["name_localizations"][locale] == message("question_name", locale)
        assert option["description_localizations"][locale] == message(
            "question_description", locale
        )
