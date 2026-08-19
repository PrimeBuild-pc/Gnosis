from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from telethon import TelegramClient, events, utils

from ..config import Settings, SourceConfig
from ..db import Database
from ..types import CollectedMessage

log = logging.getLogger(__name__)

Emit = Callable[[CollectedMessage], int | None]
Delete = Callable[[str, str, str], None]


def _link(chat_id: int, username: str | None, message_id: int) -> str:
    if username:
        return f"https://t.me/{username}/{message_id}"
    value = str(chat_id)
    return f"https://t.me/c/{value[4:]}/{message_id}" if value.startswith("-100") else ""


async def login(settings: Settings) -> None:
    if not settings.telegram_api_id or not settings.telegram_api_hash:
        raise ValueError("TELEGRAM_API_ID e TELEGRAM_API_HASH obbligatori")
    client = TelegramClient(
        settings.telegram_session, settings.telegram_api_id, settings.telegram_api_hash
    )
    await client.start()
    await client.disconnect()


async def run(
    settings: Settings,
    sources: list[SourceConfig],
    emit: Emit,
    delete: Delete,
    db: Database | None = None,
    backfill_limit: int = 200,
) -> None:
    if not settings.telegram_api_id or not settings.telegram_api_hash:
        raise ValueError("Credenziali Telegram mancanti")
    chat_ids = [int(source.external_id) for source in sources]
    allowed = {str(chat_id) for chat_id in chat_ids}
    client = TelegramClient(
        settings.telegram_session, settings.telegram_api_id, settings.telegram_api_hash
    )

    async def collect(message: Any) -> None:
        chat_id = str(message.chat_id)
        if chat_id not in allowed or not message.message:
            return
        sender = await message.get_sender()
        chat = await message.get_chat()
        emit(
            CollectedMessage(
                platform="telegram",
                source_external_id=chat_id,
                external_id=str(message.id),
                author=utils.get_display_name(sender) if sender else "",
                sent_at=message.date,
                text=message.message,
                url=_link(message.chat_id, getattr(chat, "username", None), message.id),
                thread_id=str(message.reply_to_msg_id) if message.reply_to_msg_id else None,
                author_id=str(message.sender_id) if message.sender_id else None,
            )
        )

    # Con chat_ids vuoto i filtri di Telethon non restringerebbero nulla: meglio non
    # registrare affatto gli handler, cosi' un avvio di sola scoperta non ascolta tutto.
    if chat_ids:

        @client.on(events.NewMessage(chats=chat_ids))
        async def on_message(event):
            await collect(event.message)

        @client.on(events.MessageEdited(chats=chat_ids))
        async def on_edit(event):
            await collect(event.message)

        @client.on(events.MessageDeleted(chats=chat_ids))
        async def on_delete(event):
            if event.chat_id is not None:
                for message_id in event.deleted_ids:
                    delete("telegram", str(event.chat_id), str(message_id))

    async def publish_available() -> None:
        """Pubblica le chat raggiungibili dall'account per la tendina della dashboard.

        Lo fa il worker perche' la sessione Telethon vive nel suo volume: il container web
        non puo' elencare i dialoghi.
        """
        rows = []
        async for dialog in client.iter_dialogs():
            if dialog.is_user:
                continue
            rows.append({"external_id": str(dialog.id), "name": dialog.name or str(dialog.id)})
        db.replace_available_sources("telegram", rows)

    async def refresh_available_loop() -> None:
        while True:
            try:
                await publish_available()
            except Exception:
                log.exception("Telegram: aggiornamento chat disponibili fallito")
            await asyncio.sleep(3600)

    await client.start()
    if db is not None:
        asyncio.create_task(refresh_available_loop())
    for chat_id in chat_ids:
        async for message in client.iter_messages(chat_id, limit=backfill_limit):
            await collect(message)
    await client.run_until_disconnected()
