# Gnosis repository guide

## Overview

Gnosis is a private, source-grounded knowledge base for Telegram, Discord, and Reddit. The flow is:

`platform collectors → async worker → filtering/embeddings → PostgreSQL + pgvector → RAG/digests/FastAPI web UI`

## Repository structure

- `src/gnosis/` — application package.
  - `cli.py` — `gnosis` command-line entrypoint.
  - `api.py` — FastAPI app and HTTP routes.
  - `worker.py` — collector and processing orchestration.
  - `collectors/` — Telegram, Discord, and Reddit integrations.
  - `pipeline.py`, `rag.py`, `digest.py`, `llm.py` — processing and generation services.
  - `db.py`, `types.py` — persistence and shared types.
  - `config.py` — frozen settings dataclasses, environment loading, and source allowlists.
  - `static/` — vanilla web assets.
- `tests/` — pytest unit tests for configuration, pipeline, retrieval, and digest logic.
- `migrations/` — PostgreSQL/pgvector SQL migrations.
- `config/` — source allowlist template; local `sources.toml` is untracked.
- `docs/` — setup and operations notes.
- `Dockerfile`, `compose.yaml` — container image and `db`/`web`/`worker` services.

## Build, test, and run

Local development requires Python 3.11+:

```bash
python -m pip install -e ".[dev]"
python -m pytest
ruff check src tests
```

Build and run the full stack with Docker Compose:

```bash
docker compose build
docker compose run --rm web gnosis db-init
docker compose up -d
```

Useful CLI commands:

```bash
gnosis web
gnosis worker
gnosis telegram-login
gnosis digest
gnosis prune --before YYYY-MM-DD
```

The application expects `.env` and `config/sources.toml` at runtime. Copy them from the example files when those examples are available, and never commit credentials, platform sessions, backups, or local source configuration.

## Conventions

- Use Python type hints and the existing `from __future__ import annotations` style.
- Keep configuration immutable (`@dataclass(frozen=True)`) and load environment variables through `Settings.from_env()`.
- Keep platform I/O asynchronous; isolate connector-specific behavior under `collectors/`.
- Use the database layer and numbered SQL migrations for persistence changes; do not embed schema changes in application startup.
- Add or update focused pytest tests for pure logic and boundary behavior. Avoid real platform/API calls in unit tests.
- Follow Ruff settings in `pyproject.toml`: Python 3.11 target and 100-character lines.
- Preserve source-grounded answers and citation validation in RAG/digest changes.
- Bind local web access to loopback by default and treat all credentials and collected messages as sensitive.
