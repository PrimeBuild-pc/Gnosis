from __future__ import annotations

import httpx

from .config import Settings

_TELEGRAM_LIMIT = 4096
_DISCORD_LIMIT = 2000


async def send_telegram(bot_token: str, chat_id: str, text: str) -> None:
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": text[:_TELEGRAM_LIMIT]},
        )
        response.raise_for_status()


async def send_discord_webhook(webhook_url: str, text: str) -> None:
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(webhook_url, json={"content": text[:_DISCORD_LIMIT]})
        response.raise_for_status()


async def push_digest(settings: Settings, markdown: str) -> None:
    """Pubblica il digest sulle destinazioni configurate (facoltative, indipendenti)."""
    if settings.digest_telegram_chat_id and settings.telegram_bot_token:
        await send_telegram(settings.telegram_bot_token, settings.digest_telegram_chat_id, markdown)
    if settings.digest_discord_webhook:
        await send_discord_webhook(settings.digest_discord_webhook, markdown)
