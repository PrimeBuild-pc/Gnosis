from __future__ import annotations

import logging

from telethon import TelegramClient, events

from .config import Settings
from .db import Database
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
        raise ValueError(
            "GNOSIS_TELEGRAM_ALLOWED_USERS obbligatorio quando TELEGRAM_BOT_TOKEN è impostato"
        )
    allowed = frozenset(settings.telegram_allowed_user_ids)
    client = TelegramClient(
        f"{settings.telegram_session}-bot", settings.telegram_api_id, settings.telegram_api_hash
    )

    @client.on(events.NewMessage(pattern="/start"))
    async def on_start(event: events.NewMessage.Event) -> None:
        if is_authorized(event.sender_id, allowed):
            await event.reply("Ciao! Usa /ask <domanda> oppure /digest.")

    @client.on(events.NewMessage(pattern=r"/ask(?:\s+(.+))?"))
    async def on_ask(event: events.NewMessage.Event) -> None:
        if not is_authorized(event.sender_id, allowed):
            return
        question = (event.pattern_match.group(1) or "").strip()
        if not question:
            await event.reply("Uso: /ask <domanda>")
            return
        try:
            result = await rag.ask(question)
            await event.reply(_format_answer(result))
        except Exception:
            log.exception("Errore durante /ask")
            await event.reply("Errore durante l'elaborazione della domanda.")

    @client.on(events.NewMessage(pattern="/digest"))
    async def on_digest(event: events.NewMessage.Event) -> None:
        if not is_authorized(event.sender_id, allowed):
            return
        digests = db.list_digests(limit=1)
        if not digests:
            await event.reply("Nessun digest disponibile.")
            return
        await event.reply(digests[0]["markdown"][:_MAX_REPLY])

    await client.start(bot_token=settings.telegram_bot_token)
    await client.run_until_disconnected()
