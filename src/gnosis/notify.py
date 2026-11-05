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


def split_message(text: str, limit: int = _DISCORD_LIMIT) -> list[str]:
    """Split on line breaks so each Discord message stays under the limit."""
    chunks: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        while len(line) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]
        if len(current) + len(line) > limit:
            chunks.append(current)
            current = ""
        current += line
    if current.strip():
        chunks.append(current)
    return chunks


async def send_discord_channel(bot_token: str, channel_id: str, text: str) -> None:
    """Post as the bot (no webhook needed); mentions in summaries never ping anyone."""
    async with httpx.AsyncClient(timeout=15) as client:
        for chunk in split_message(text):
            response = await client.post(
                f"https://discord.com/api/v10/channels/{channel_id}/messages",
                headers={"Authorization": f"Bot {bot_token}"},
                json={"content": chunk, "allowed_mentions": {"parse": []}},
            )
            response.raise_for_status()


async def push_digest(
    settings: Settings,
    markdown: str,
    telegram_chat_id: str | None = None,
    discord_webhook: str | None = None,
) -> None:
    """Publish the digest to configured destinations (optional and independent).

    Destinations may come from the workspace: passing them explicitly gives each server
    its own digest on its own webhook. Otherwise, fall back to the global .env values
    so existing installations continue to work.
    """
    chat_id = telegram_chat_id if telegram_chat_id is not None else settings.digest_telegram_chat_id
    webhook = discord_webhook if discord_webhook is not None else settings.digest_discord_webhook
    if chat_id and settings.telegram_bot_token:
        await send_telegram(settings.telegram_bot_token, chat_id, markdown)
    if webhook:
        await send_discord_webhook(webhook, markdown)
