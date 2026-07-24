from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import UTC, date, datetime, time

import uvicorn

from .collectors.telegram import login as telegram_login
from .config import Settings
from .db import Database
from .digest import DigestService, previous_week
from .llm import LLM
from .worker import run_worker


def _database(settings: Settings) -> Database:
    db = Database(settings.database_url)
    db.open()
    return db


def main() -> None:
    parser = argparse.ArgumentParser(prog="gnosis")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("db-init", help="Applica le migration")
    subcommands.add_parser("web", help="Avvia API e interfaccia")
    subcommands.add_parser("worker", help="Avvia connettori, pipeline e scheduler")
    subcommands.add_parser("telegram-login", help="Crea la sessione Telegram")
    subcommands.add_parser("digest", help="Genera il digest della settimana precedente")
    prune = subcommands.add_parser("prune", help="Elimina messaggi più vecchi della data")
    prune.add_argument("--before", required=True, help="Data UTC YYYY-MM-DD")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    settings = Settings.from_env()

    if args.command == "web":
        uvicorn.run("gnosis.api:create_app", factory=True, host=settings.host, port=settings.port)
    elif args.command == "worker":
        asyncio.run(run_worker())
    elif args.command == "telegram-login":
        asyncio.run(telegram_login(settings))
    else:
        db = _database(settings)
        try:
            db.migrate()
            if args.command == "digest":
                llm = LLM(settings)
                start, end = previous_week(datetime.now(UTC), settings.zoneinfo)
                digest_id = asyncio.run(
                    DigestService(db, llm, settings.zoneinfo).generate(start, end)
                )
                print(digest_id or "Nessun messaggio nel periodo")
            elif args.command == "prune":
                before = datetime.combine(date.fromisoformat(args.before), time(), UTC)
                print(f"Eliminati {db.prune(before)} messaggi")
        finally:
            db.close()


if __name__ == "__main__":
    main()
