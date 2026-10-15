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
from .selfcheck import run as run_selfcheck
from .worker import run_worker


def _database(settings: Settings) -> Database:
    db = Database(settings.database_url)
    db.open()
    return db


def main() -> None:
    parser = argparse.ArgumentParser(prog="gnosis")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("db-init", help="Apply migrations")
    subcommands.add_parser("web", help="Start the API and interface")
    subcommands.add_parser("worker", help="Start collectors, pipeline, and scheduler")
    subcommands.add_parser("telegram-login", help="Create the Telegram session")
    subcommands.add_parser("digest", help="Generate the previous week's digest")
    subcommands.add_parser("selfcheck", help="Verify that queries work on the configured database")
    prune = subcommands.add_parser("prune", help="Delete messages older than the date")
    prune.add_argument("--before", required=True, help="UTC date YYYY-MM-DD")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    settings = Settings.from_env()

    if args.command == "selfcheck":
        results = run_selfcheck(settings)
        for name, ok, detail in results:
            print(f"{'OK  ' if ok else 'FAILED'} {name}{f' — {detail}' if detail else ''}")
        failed = [name for name, ok, _ in results if not ok]
        if failed:
            raise SystemExit(f"{len(failed)} checks failed")
        print(f"{len(results)} checks passed")
    elif args.command == "web":
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
                print(digest_id or "No messages in the period")
            elif args.command == "prune":
                before = datetime.combine(date.fromisoformat(args.before), time(), UTC)
                print(f"Deleted {db.prune(before)} messages")
        finally:
            db.close()


if __name__ == "__main__":
    main()
