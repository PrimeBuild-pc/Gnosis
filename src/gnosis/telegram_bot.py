from __future__ import annotations

import logging

from telethon import TelegramClient, events

from .config import Settings
from .db import Database
from .i18n import message, normalize_locale
from .rag import RAG

log = logging.getLogger(__name__)

_MAX_REPLY = 4000


def is_authorized(sender_id: int | None, allowed: frozenset[int]) -> bool:
    return sender_id is not None and sender_id in allowed


def _format_answer(result: dict) -> str:
    text = result["answer"]
    if result["sources"]:
        lines = (
            f"{s['id']} — {s['platform']}/{s['community']} {s['url']}" for s in result["sources"]
        )
        text = f"{text}\n\n" + "\n".join(lines)
    return text[:_MAX_REPLY]


async def run(settings: Settings, rag: RAG, db: Database) -> None:
    if not settings.telegram_bot_token:
        return
    if not settings.telegram_allowed_user_ids:
        raise ValueError("GNOSIS_TELEGRAM_ALLOWED_USERS is required when TELEGRAM_BOT_TOKEN is set")
    allowed = frozenset(settings.telegram_allowed_user_ids)
    client = TelegramClient(
        f"{settings.telegram_session}-bot", settings.telegram_api_id, settings.telegram_api_hash
    )

    async def locale_for(event: events.NewMessage.Event) -> str:
        try:
            sender = await event.get_sender()
            # Telethon exposes Telegram's language_code as lang_code.
            return normalize_locale(getattr(sender, "lang_code", None))
        except Exception:
            log.exception("Telegram: sender language lookup failed")
            return "en"

    @client.on(events.NewMessage(pattern=r"/(?:start|help)(?:@\w+)?(?:\s|$)"))
    async def on_start(event: events.NewMessage.Event) -> None:
        if event.is_private and is_authorized(event.sender_id, allowed):
            await event.reply(message("help", await locale_for(event)))

    @client.on(events.NewMessage(pattern=r"/ask(?:@\w+)?(?:\s+([\s\S]*))?$"))
    async def on_ask(event: events.NewMessage.Event) -> None:
        if not event.is_private or not is_authorized(event.sender_id, allowed):
            return
        locale = await locale_for(event)
        question = (event.pattern_match.group(1) or "").strip()
        if not question:
            await event.reply(message("ask_usage", locale))
            return
        try:
            result = await rag.ask(question, locale=locale)
            await event.reply(_format_answer(result))
        except Exception:
            log.exception("Telegram: answer failed")
            await event.reply(message("answer_error", locale))

    @client.on(events.NewMessage(pattern=r"/digest(?:@\w+)?\s*$"))
    async def on_digest(event: events.NewMessage.Event) -> None:
        if not event.is_private or not is_authorized(event.sender_id, allowed):
            return
        locale = await locale_for(event)
        try:
            digests = db.list_digests(limit=1)
            text = digests[0]["markdown"][:_MAX_REPLY] if digests else message("no_digest", locale)
        except Exception:
            log.exception("Telegram: digest failed")
            text = message("digest_error", locale)
        await event.reply(text)

    await client.start(bot_token=settings.telegram_bot_token)
    await client.run_until_disconnected()
