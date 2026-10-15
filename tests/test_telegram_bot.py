import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from gnosis import telegram_bot
from gnosis.config import Settings
from gnosis.i18n import message, normalize_locale
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


@pytest.fixture
def command_harness(monkeypatch):
    handlers = {}

    class FakeClient:
        def __init__(self, *args):
            pass

        def on(self, event):
            def register(callback):
                handlers[callback.__name__] = (callback, event.pattern)
                return callback

            return register

        async def start(self, **kwargs):
            pass

        async def run_until_disconnected(self):
            pass

    monkeypatch.setattr(telegram_bot, "TelegramClient", FakeClient)
    db = Mock()
    db.list_digests.return_value = []
    rag = SimpleNamespace(ask=AsyncMock(return_value={"answer": "Answer [M1]", "sources": []}))
    asyncio.run(
        telegram_bot.run(
            Settings(telegram_bot_token="fake", telegram_allowed_user_ids=(42,)),
            rag,
            db,
        )
    )

    def event_for(handler, text, locale):
        return SimpleNamespace(
            is_private=True,
            sender_id=42,
            reply=AsyncMock(),
            get_sender=AsyncMock(return_value=SimpleNamespace(lang_code=locale)),
            pattern_match=handlers[handler][1](text),
        )

    return handlers, db, rag, event_for


@pytest.mark.parametrize("locale", ["en-US", "it", "es", "ru", "zh-Hans", "de", None])
def test_telegram_ask_passes_sender_language(command_harness, locale):
    handlers, _, rag, event_for = command_harness
    event = event_for("on_ask", "/ask question", locale)
    asyncio.run(handlers["on_ask"][0](event))
    rag.ask.assert_awaited_once_with("question", locale=normalize_locale(locale))
    event.reply.assert_awaited_once_with("Answer [M1]")


@pytest.mark.parametrize("locale", ["en", "it", "es", "ru", "zh", "de", None])
@pytest.mark.parametrize(
    "state", ["help", "ask_usage", "answer_error", "no_digest", "digest_error"]
)
def test_telegram_messages_are_localized(command_harness, locale, state):
    handlers, db, rag, event_for = command_harness
    if state == "help":
        handler, text = "on_start", "/help"
    elif state in {"ask_usage", "answer_error"}:
        handler, text = "on_ask", "/ask" if state == "ask_usage" else "/ask q"
        rag.ask.side_effect = RuntimeError("private-provider-detail")
    else:
        handler, text = "on_digest", "/digest"
        if state == "digest_error":
            db.list_digests.side_effect = RuntimeError("private-database-detail")
    event = event_for(handler, text, locale)
    asyncio.run(handlers[handler][0](event))
    event.reply.assert_awaited_once_with(message(state, locale))


@pytest.mark.parametrize("private,sender_id", [(False, 42), (True, 99), (True, None)])
@pytest.mark.parametrize(
    "handler,text", [("on_start", "/help"), ("on_ask", "/ask q"), ("on_digest", "/digest")]
)
def test_telegram_checks_permissions_before_locale_lookup(
    command_harness, private, sender_id, handler, text
):
    handlers, db, rag, event_for = command_harness
    event = event_for(handler, text, "ru")
    event.is_private, event.sender_id = private, sender_id
    asyncio.run(handlers[handler][0](event))
    event.get_sender.assert_not_called()
    event.reply.assert_not_called()
    db.list_digests.assert_not_called()
    rag.ask.assert_not_called()


def test_sender_lookup_failure_falls_back_to_english(command_harness):
    handlers, _, rag, event_for = command_harness
    event = event_for("on_ask", "/ask q", "it")
    event.get_sender.side_effect = RuntimeError("lookup failed")
    asyncio.run(handlers["on_ask"][0](event))
    rag.ask.assert_awaited_once_with("q", locale="en")


@pytest.mark.parametrize(
    "handler,text",
    [("on_start", "/starter"), ("on_ask", "/askmore q"), ("on_digest", "/digestive")],
)
def test_command_patterns_do_not_match_prefixes(command_harness, handler, text):
    handlers, _, _, _ = command_harness
    assert handlers[handler][1](text) is None


@pytest.mark.parametrize("text", ["/start", "/help", "/help@gnosis_bot"])
def test_help_aliases(command_harness, text):
    handlers, _, _, event_for = command_harness
    event = event_for("on_start", text, "es")
    assert event.pattern_match is not None
    asyncio.run(handlers["on_start"][0](event))
    event.reply.assert_awaited_once_with(message("help", "es"))
