from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from .collectors import discord, reddit, telegram
from .config import Settings, load_sources
from .db import Database
from .digest import DigestService, previous_week
from .llm import LLM
from .pipeline import Pipeline, store_collected
from .types import CollectedMessage

log = logging.getLogger(__name__)


async def _supervise(name: str, run) -> None:
    while True:
        try:
            await run()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Connettore %s terminato; nuovo tentativo tra 30 secondi", name)
            await asyncio.sleep(30)


async def run_worker() -> None:
    settings = Settings.from_env()
    configured_sources = load_sources(settings.sources_file)
    sources = [source for source in configured_sources if source.enabled]
    db = Database(settings.database_url)
    db.open()
    db.migrate()
    source_ids = db.upsert_sources(configured_sources)
    llm = LLM(settings)
    pipeline = Pipeline(db, llm, settings.relevance_threshold)
    digest = DigestService(db, llm, settings.zoneinfo)

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
                if not db.digest_exists(start, end):
                    digest_id = await digest.generate(start, end)
                    if digest_id:
                        log.info("Creato digest %s", digest_id)
            except Exception:
                log.exception("Errore nella generazione del digest")
            await asyncio.sleep(3600)

    grouped = {
        platform: [source for source in sources if source.platform == platform]
        for platform in ("telegram", "discord", "reddit")
    }
    tasks = [process_loop, digest_loop]
    if grouped["telegram"] and settings.telegram_api_id and settings.telegram_api_hash:
        tasks.append(lambda: telegram.run(settings, grouped["telegram"], emit, delete))
    if grouped["discord"] and settings.discord_bot_token:
        tasks.append(lambda: discord.run(settings, grouped["discord"], emit, delete))
    if grouped["reddit"] and settings.reddit_client_id and settings.reddit_client_secret:
        tasks.append(lambda: reddit.run(settings, grouped["reddit"], emit))

    try:
        async with asyncio.TaskGroup() as group:
            for index, task in enumerate(tasks):
                group.create_task(_supervise(str(index), task))
    finally:
        db.close()
