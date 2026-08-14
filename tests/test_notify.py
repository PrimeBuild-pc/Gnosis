import asyncio

import pytest

from gnosis.config import Settings
from gnosis.notify import push_digest


def test_push_digest_sends_to_telegram_when_configured(monkeypatch: pytest.MonkeyPatch):
    calls = []

    async def fake_send_telegram(token, chat_id, text):
        calls.append(("telegram", token, chat_id, text))

    monkeypatch.setattr("gnosis.notify.send_telegram", fake_send_telegram)
    settings = Settings(telegram_bot_token="tok", digest_telegram_chat_id="123")
    asyncio.run(push_digest(settings, "hello"))
    assert calls == [("telegram", "tok", "123", "hello")]


def test_push_digest_sends_to_discord_when_configured(monkeypatch: pytest.MonkeyPatch):
    calls = []

    async def fake_send_discord_webhook(url, text):
        calls.append(("discord", url, text))

    monkeypatch.setattr("gnosis.notify.send_discord_webhook", fake_send_discord_webhook)
    settings = Settings(digest_discord_webhook="https://discord.com/api/webhooks/x/y")
    asyncio.run(push_digest(settings, "hello"))
    assert calls == [("discord", "https://discord.com/api/webhooks/x/y", "hello")]


def test_push_digest_noop_when_unconfigured(monkeypatch: pytest.MonkeyPatch):
    calls = []
    monkeypatch.setattr("gnosis.notify.send_telegram", lambda *a: calls.append(a))
    monkeypatch.setattr("gnosis.notify.send_discord_webhook", lambda *a: calls.append(a))
    asyncio.run(push_digest(Settings(), "hello"))
    assert calls == []


def test_push_digest_skips_telegram_without_bot_token(monkeypatch: pytest.MonkeyPatch):
    calls = []
    monkeypatch.setattr("gnosis.notify.send_telegram", lambda *a: calls.append(a))
    settings = Settings(digest_telegram_chat_id="123")
    asyncio.run(push_digest(settings, "hello"))
    assert calls == []
