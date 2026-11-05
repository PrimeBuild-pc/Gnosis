from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from . import telegram_bot
from .collectors import discord, reddit, telegram
from .config import Settings, load_sources
from .db import Database
from .digest import DigestService, language_name, link_citations, previous_day, previous_week
from .llm import LLM
from .notify import push_digest, send_discord_channel
from .pipeline import Pipeline, store_collected
from .rag import RAG
from .types import CollectedMessage

log = logging.getLogger(__name__)


async def _supervise(db: Database, name: str, run) -> None:
    while True:
        try:
            db.report_status(name, "ok")
            await run()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            log.exception("Collector %s stopped; retrying in 30 seconds", name)
            db.report_status(name, "error", str(error)[:500])
            await asyncio.sleep(30)


async def run_worker() -> None:
    settings = Settings.from_env()
    # Unlike the web, the worker cannot do anything useful without a key: fail
    # immediately and visibly rather than on every processed message.
    if not settings.chat_api_key:
        raise ValueError("Chat API key required (OPENAI_API_KEY or GNOSIS_CHAT_API_KEY)")
    configured_sources = load_sources(settings.sources_file)
    sources = [source for source in configured_sources if source.enabled]
    db = Database(settings.database_url)
    db.open()
    db.migrate()
    source_ids = db.upsert_sources(configured_sources)
    llm = LLM(settings)
    llm.on_usage = db.record_usage
    pipeline = Pipeline(db, llm, settings.relevance_threshold)
    digest = DigestService(db, llm, settings.zoneinfo)
    rag = RAG(db, llm)

    def emit(message: CollectedMessage) -> int | None:
        key = (message.platform, message.source_external_id.lower())
        if key not in source_ids:
            # Channels registered at runtime by "read all channels".
            found = db.source_id(message.platform, message.source_external_id)
            if found is None:
                return None
            source_ids[key] = found
        return store_collected(db, source_ids, message)

    def delete(platform: str, source_external_id: str, external_id: str) -> None:
        source_id = source_ids.get((platform, source_external_id.lower()))
        if source_id is not None:
            db.delete_message(source_id, external_id)

    async def process_loop() -> None:
        while True:
            try:
                count = await pipeline.process_pending()
                if count:
                    log.info("Processed %s messages", count)
            except Exception:
                log.exception("Pipeline error")
            await asyncio.sleep(settings.process_seconds)

    async def publish(workspace: dict[str, Any] | None, start, end, markdown: str) -> None:
        await push_digest(
            settings,
            markdown,
            telegram_chat_id=(workspace["digest_telegram_chat_id"] if workspace else None),
            discord_webhook=workspace["digest_webhook"] if workspace else None,
        )
        channel_id = (workspace or {}).get("digest_channel_id")
        if channel_id and settings.discord_bot_token:
            messages = db.messages_between(start, end, workspace_id=workspace["id"])
            await send_discord_channel(
                settings.discord_bot_token, channel_id, link_citations(markdown, messages)
            )

    async def digest_loop() -> None:
        while True:
            try:
                now = datetime.now(UTC)
                # When workspaces are configured, no mixed digest is published.
                workspaces = db.list_workspaces()
                targets: list[dict[str, Any] | None] = workspaces or [None]
                for workspace in targets:
                    frequency = (workspace or {}).get("digest_frequency", "weekly")
                    if frequency == "off":
                        continue
                    daily = frequency == "daily"
                    start, end = (previous_day if daily else previous_week)(now, settings.zoneinfo)
                    workspace_id = workspace["id"] if workspace else None
                    if db.digest_exists(start, end, workspace_id=workspace_id):
                        continue
                    # Only what is new since the previous digest (e.g. after a frequency change).
                    previous_end = db.last_digest_end(workspace_id)
                    if previous_end and previous_end > start:
                        start = previous_end
                    if start >= end:
                        continue
                    # A digest is published once: wait until the backlog of the period is
                    # classified, or it would summarize only part of it.
                    if db.has_unprocessed_before(end, workspace_id=workspace_id):
                        continue
                    digest_id = await digest.generate(
                        start,
                        end,
                        workspace_id=workspace_id,
                        language=language_name((workspace or {}).get("digest_locale")),
                        title="daily digest" if daily else "weekly digest",
                    )
                    if not digest_id:
                        continue
                    log.info(
                        "Created digest %s for %s",
                        digest_id,
                        workspace["name"] if workspace else "all sources",
                    )
                    markdown = db.list_digests(limit=1, workspace_id=workspace_id)[0]["markdown"]
                    await publish(workspace, start, end, markdown)
            except Exception:
                log.exception("Digest generation error")
            await asyncio.sleep(3600)

    async def retention_loop() -> None:
        while True:
            try:
                raw = db.get_setting("retention_days")
                if raw:
                    cutoff = datetime.now(UTC) - timedelta(days=int(raw))
                    removed = db.prune(cutoff)
                    if removed:
                        log.info("Retention: deleted %s messages older than %s days", removed, raw)
            except Exception:
                log.exception("Retention error")
            await asyncio.sleep(3600)

    grouped = {
        platform: [source for source in sources if source.platform == platform]
        for platform in ("telegram", "discord", "reddit")
    }
    tasks = [("pipeline", process_loop), ("digest", digest_loop), ("retention", retention_loop)]
    # Collectors start as soon as credentials are available, even without enabled sources:
    # they discover available channels for the dashboard dropdown. Otherwise, a channel
    # could not be selected until one had already been entered manually.
    if settings.telegram_api_id and settings.telegram_api_hash:
        tasks.append(
            ("telegram", lambda: telegram.run(settings, grouped["telegram"], emit, delete, db))
        )
    if settings.discord_bot_token:
        tasks.append(
            ("discord", lambda: discord.run(settings, grouped["discord"], emit, delete, rag, db))
        )
    if grouped["reddit"] and settings.reddit_client_id and settings.reddit_client_secret:
        tasks.append(("reddit", lambda: reddit.run(settings, grouped["reddit"], emit)))
    if settings.telegram_bot_token and settings.telegram_api_id and settings.telegram_api_hash:
        tasks.append(("telegram_bot", lambda: telegram_bot.run(settings, rag, db)))

    try:
        async with asyncio.TaskGroup() as group:
            for name, task in tasks:
                group.create_task(_supervise(db, name, task))
    finally:
        db.close()
