import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from gnosis.collectors import discord as collector
from gnosis.collectors.discord import is_authorized
from gnosis.config import Settings


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
        "question", workspace_id=11, discord_guild_id="101", source_external_ids=["10"]
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


@pytest.mark.parametrize("accessible,expected", [({1}, "Only A"), (set(), "non disponibile")])
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
    assert "non disponibile" in interaction.response.send_message.call_args.args[0]


def test_provider_error_does_not_expose_details(command_harness):
    commands, interaction, _, rag, _ = command_harness
    rag.ask.side_effect = RuntimeError("private-provider-detail")
    asyncio.run(commands["ask"](interaction, "question"))
    assert "private-provider-detail" not in interaction.followup.send.call_args.args[0]
    assert interaction.followup.send.call_args.kwargs["ephemeral"] is True
