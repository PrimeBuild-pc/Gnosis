"""Il comportamento che rende i server separati invece che mescolati.

I filtri SQL veri (search, messages_between) richiedono un Postgres e sono verificati sul
deploy; qui si copre tutto il resto: round-trip della configurazione, scelta dei ruoli per
server, e destinazioni del digest per workspace.
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
    # Il ruolo globale non basta piu' dentro un server che ha i suoi.
    assert not is_authorized([99], roles)


def test_global_allowlist_used_when_workspace_has_no_roles():
    assert allowed_roles_for(None, frozenset({99})) == frozenset({99})
    assert allowed_roles_for({"allowed_role_ids": []}, frozenset({99})) == frozenset({99})


def test_digest_goes_to_the_workspace_webhook(monkeypatch: pytest.MonkeyPatch):
    calls = []

    async def fake_send_discord_webhook(url, text):
        calls.append(url)

    monkeypatch.setattr("gnosis.notify.send_discord_webhook", fake_send_discord_webhook)
    settings = Settings(digest_discord_webhook="https://discord.com/api/webhooks/globale")
    asyncio.run(
        push_digest(settings, "hello", discord_webhook="https://discord.com/api/webhooks/server-a")
    )
    assert calls == ["https://discord.com/api/webhooks/server-a"]


def test_workspace_without_webhook_does_not_fall_back_to_global(monkeypatch: pytest.MonkeyPatch):
    """Un workspace senza webhook non deve pubblicare sul webhook di un altro contesto."""
    calls = []
    monkeypatch.setattr("gnosis.notify.send_discord_webhook", lambda url, text: calls.append(url))
    settings = Settings(digest_discord_webhook="https://discord.com/api/webhooks/globale")
    asyncio.run(push_digest(settings, "hello", discord_webhook=""))
    assert calls == []


def test_global_digest_still_uses_env_destination(monkeypatch: pytest.MonkeyPatch):
    """Senza workspace (None) valgono i valori di .env: le installazioni esistenti non cambiano."""
    calls = []

    async def fake_send_discord_webhook(url, text):
        calls.append(url)

    monkeypatch.setattr("gnosis.notify.send_discord_webhook", fake_send_discord_webhook)
    settings = Settings(digest_discord_webhook="https://discord.com/api/webhooks/globale")
    asyncio.run(push_digest(settings, "hello", discord_webhook=None))
    assert calls == ["https://discord.com/api/webhooks/globale"]
