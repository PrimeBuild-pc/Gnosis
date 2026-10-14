import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from gnosis import telegram_bot
from gnosis.config import Settings
from gnosis.telegram_bot import is_authorized


def test_authorized_user_is_allowed():
    assert is_authorized(42, frozenset({42, 7}))


def test_unknown_user_is_denied():
    assert not is_authorized(99, frozenset({42, 7}))


def test_missing_sender_is_denied():
    assert not is_authorized(None, frozenset({42}))


def test_empty_allowlist_denies_everyone():
    assert not is_authorized(42, frozenset())


def test_authorized_operator_cannot_publish_global_answers_in_groups(monkeypatch):
    handlers = []

    class FakeClient:
        def __init__(self, *args):
            pass

        def on(self, event):
            def register(callback):
                handlers.append(callback)
                return callback

            return register

        async def start(self, **kwargs):
            pass

        async def run_until_disconnected(self):
            pass

    monkeypatch.setattr(telegram_bot, "TelegramClient", FakeClient)
    db = Mock()
    rag = SimpleNamespace(ask=AsyncMock())
    asyncio.run(
        telegram_bot.run(
            Settings(
                telegram_bot_token="fake",
                telegram_allowed_user_ids=(42,),
            ),
            rag,
            db,
        )
    )
    event = SimpleNamespace(is_private=False, sender_id=42, reply=AsyncMock())
    for handler in handlers:
        asyncio.run(handler(event))
    db.list_digests.assert_not_called()
    rag.ask.assert_not_called()
    event.reply.assert_not_called()
