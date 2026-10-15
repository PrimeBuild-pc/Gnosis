"""Behavior that keeps servers separate instead of mixing them.

The actual SQL filters (search, messages_between) require Postgres and are checked on
deployment; this covers everything else: configuration round trips, per-server role
selection, and per-workspace digest destinations.
"""

import asyncio
from pathlib import Path

import pytest

from gnosis.collectors.discord import allowed_roles_for, is_authorized
from gnosis.config import Settings, SourceConfig, load_sources, save_sources
from gnosis.notify import push_digest


def test_workspace_survives_toml_round_trip(tmp_path: Path):
    path = tmp_path / "sources.toml"
    sources = [
        SourceConfig(
            platform="discord",
            external_id="111",
            name="general",
            topics=("AI",),
            workspace="Server A",
        ),
        SourceConfig(platform="discord", external_id="222", name="random"),
    ]
    save_sources(path, sources)
    loaded = load_sources(path)
    assert [s.workspace for s in loaded] == ["Server A", ""]


def test_load_sources_without_workspace_stays_empty(tmp_path: Path):
    path = tmp_path / "sources.toml"
    path.write_text('[[reddit]]\nsubreddit="python"\n', encoding="utf-8")
    assert load_sources(path)[0].workspace == ""


def test_workspace_roles_win_over_global_allowlist():
    workspace = {"allowed_role_ids": ["7"]}
    roles = allowed_roles_for(workspace, frozenset({99}))
    assert roles == frozenset({7})
    assert is_authorized([7], roles)
    # A global role is no longer enough in a server with its own roles.
    assert not is_authorized([99], roles)


def test_unmapped_server_and_empty_roles_deny_even_global_roles():
    assert allowed_roles_for(None, frozenset({99})) == frozenset()
    assert allowed_roles_for({"allowed_role_ids": []}, frozenset({99})) == frozenset()


def test_digest_goes_to_the_workspace_webhook(monkeypatch: pytest.MonkeyPatch):
    calls = []

    async def fake_send_discord_webhook(url, text):
        calls.append(url)

    monkeypatch.setattr("gnosis.notify.send_discord_webhook", fake_send_discord_webhook)
    settings = Settings(digest_discord_webhook="https://discord.com/api/webhooks/global")
    asyncio.run(
        push_digest(settings, "hello", discord_webhook="https://discord.com/api/webhooks/server-a")
    )
    assert calls == ["https://discord.com/api/webhooks/server-a"]


def test_workspace_without_webhook_does_not_fall_back_to_global(monkeypatch: pytest.MonkeyPatch):
    """A workspace without a webhook must not publish to another scope's webhook."""
    calls = []
    monkeypatch.setattr("gnosis.notify.send_discord_webhook", lambda url, text: calls.append(url))
    settings = Settings(digest_discord_webhook="https://discord.com/api/webhooks/global")
    asyncio.run(push_digest(settings, "hello", discord_webhook=""))
    assert calls == []


def test_global_digest_still_uses_env_destination(monkeypatch: pytest.MonkeyPatch):
    """Without a workspace (None), .env values apply: existing installations do not change."""
    calls = []

    async def fake_send_discord_webhook(url, text):
        calls.append(url)

    monkeypatch.setattr("gnosis.notify.send_discord_webhook", fake_send_discord_webhook)
    settings = Settings(digest_discord_webhook="https://discord.com/api/webhooks/global")
    asyncio.run(push_digest(settings, "hello", discord_webhook=None))
    assert calls == ["https://discord.com/api/webhooks/global"]


def test_bots_env_parsing():
    from gnosis.config import _parse_bots

    assert _parse_bots("doorman=http://a:3000, dview=http://b:3001/") == (
        ("doorman", "http://a:3000"),
        ("dview", "http://b:3001"),
    )
    # Entries without an address are ignored instead of producing a bot with an empty URL.
    assert _parse_bots("doorman=,=http://x,") == ()
    assert _parse_bots("") == ()
