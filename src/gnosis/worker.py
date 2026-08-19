from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from . import telegram_bot
from .collectors import discord, reddit, telegram
from .config import Settings, load_sources
from .db import Database
from .digest import DigestService, previous_week
from .llm import LLM
from .notify import push_digest
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
            log.exception("Connettore %s terminato; nuovo tentativo tra 30 secondi", name)
            db.report_status(name, "error", str(error)[:500])
            await asyncio.sleep(30)


async def run_worker() -> None:
    settings = Settings.from_env()
    # Il worker, a differenza del web, non ha nulla di utile da fare senza chiave: meglio
    # fallire subito e visibilmente che a ogni messaggio elaborato.
    if not settings.chat_api_key:
        raise ValueError("Chiave API chat obbligatoria (OPENAI_API_KEY o GNOSIS_CHAT_API_KEY)")
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
                    log.info("Elaborati %s messaggi", count)
            except Exception:
                log.exception("Errore nella pipeline")
            await asyncio.sleep(settings.process_seconds)

    async def digest_loop() -> None:
        while True:
            try:
                start, end = previous_week(datetime.now(UTC), settings.zoneinfo)
                # Un digest per workspace, piu' uno globale se esistono sorgenti non
                # assegnate: senza questo, due server finirebbero nello stesso riassunto.
                workspaces = db.list_workspaces()
                targets: list[dict[str, Any] | None] = [*workspaces, None]
                for workspace in targets:
                    workspace_id = workspace["id"] if workspace else None
                    if db.digest_exists(start, end, workspace_id=workspace_id):
                        continue
                    digest_id = await digest.generate(start, end, workspace_id=workspace_id)
                    if not digest_id:
                        continue
                    log.info(
                        "Creato digest %s per %s",
                        digest_id,
                        workspace["name"] if workspace else "tutte le fonti",
                    )
                    markdown = db.list_digests(limit=1, workspace_id=workspace_id)[0]["markdown"]
                    await push_digest(
                        settings,
                        markdown,
                        telegram_chat_id=(
                            workspace["digest_telegram_chat_id"] if workspace else None
                        ),
                        discord_webhook=workspace["digest_webhook"] if workspace else None,
                    )
            except Exception:
                log.exception("Errore nella generazione del digest")
            await asyncio.sleep(3600)

    async def retention_loop() -> None:
        while True:
            try:
                raw = db.get_setting("retention_days")
                if raw:
                    cutoff = datetime.now(UTC) - timedelta(days=int(raw))
                    removed = db.prune(cutoff)
                    if removed:
                        log.info(
                            "Retention: eliminati %s messaggi più vecchi di %s giorni", removed, raw
                        )
            except Exception:
                log.exception("Errore nella retention")
            await asyncio.sleep(3600)

    grouped = {
        platform: [source for source in sources if source.platform == platform]
        for platform in ("telegram", "discord", "reddit")
    }
    tasks = [("pipeline", process_loop), ("digest", digest_loop), ("retention", retention_loop)]
    if grouped["telegram"] and settings.telegram_api_id and settings.telegram_api_hash:
        tasks.append(
            ("telegram", lambda: telegram.run(settings, grouped["telegram"], emit, delete, db))
        )
    if grouped["discord"] and settings.discord_bot_token:
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
