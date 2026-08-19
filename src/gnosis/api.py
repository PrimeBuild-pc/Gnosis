from __future__ import annotations

import os
import secrets
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import envfile
from .config import Settings, SourceConfig, load_sources, save_sources
from .db import Database
from .digest import DigestService, previous_week
from .llm import LLM, LLMNotConfigured
from .notify import push_digest
from .rag import RAG

security = HTTPBasic(auto_error=False)

_ENV_PATH = Path(".env")
_CONFIG_KEYS = (
    "GNOSIS_CHAT_API_KEY",
    "GNOSIS_CHAT_BASE_URL",
    "OPENAI_CHAT_MODEL",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "GNOSIS_EMBEDDING_PROVIDER",
    "TELEGRAM_API_ID",
    "TELEGRAM_API_HASH",
    "TELEGRAM_BOT_TOKEN",
    "GNOSIS_TELEGRAM_ALLOWED_USERS",
    "DISCORD_BOT_TOKEN",
    "REDDIT_CLIENT_ID",
    "REDDIT_CLIENT_SECRET",
)
_SECRET_HINTS = ("KEY", "TOKEN", "SECRET", "HASH")
# Chiavi applicabili a caldo: riguardano solo il client di chat di questo processo. Le altre
# toccano l'embedder o i connettori del worker, che vive in un container separato.
_LIVE_KEYS = frozenset(
    {
        "GNOSIS_CHAT_API_KEY",
        "GNOSIS_CHAT_BASE_URL",
        "OPENAI_CHAT_MODEL",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
    }
)


class Query(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


class ConfigUpdate(BaseModel):
    values: dict[str, str]


class SourceInput(BaseModel):
    platform: str
    external_id: str = Field(min_length=1)
    name: str = ""
    enabled: bool = True
    topics: list[str] = Field(default_factory=list)


class RetentionUpdate(BaseModel):
    days: int | None = Field(default=None, ge=1)


class WipeConfirm(BaseModel):
    confirm: str


class IgnoreAuthorInput(BaseModel):
    platform: str
    author_id: str = Field(min_length=1)


def create_app() -> FastAPI:
    settings = Settings.from_env()
    if not settings.username or not settings.password:
        raise RuntimeError("GNOSIS_USERNAME e GNOSIS_PASSWORD sono obbligatori")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db = Database(settings.database_url)
        db.open()
        db.migrate()
        llm = LLM(settings)
        llm.on_usage = db.record_usage
        app.state.db = db
        app.state.llm = llm
        app.state.rag = RAG(db, llm)
        app.state.digest = DigestService(db, llm, settings.zoneinfo)
        yield
        db.close()

    app = FastAPI(title="Gnosis", version="0.1.0", lifespan=lifespan)

    @app.exception_handler(LLMNotConfigured)
    async def llm_not_configured(request: Request, error: LLMNotConfigured) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(error)})

    def authenticate(
        credentials: Annotated[HTTPBasicCredentials | None, Depends(security)],
    ) -> str:
        valid = (
            bool(credentials)
            and secrets.compare_digest(credentials.username.encode(), settings.username.encode())
            and secrets.compare_digest(credentials.password.encode(), settings.password.encode())
        )
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenziali non valide",
                headers={"WWW-Authenticate": "Basic"},
            )
        return credentials.username

    static_dir = Path(__file__).with_name("static")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", dependencies=[Depends(authenticate)])
    def index():
        return FileResponse(static_dir / "index.html")

    @app.get("/api/stats", dependencies=[Depends(authenticate)])
    def stats(request: Request):
        return request.app.state.db.stats()

    @app.get("/api/sources", dependencies=[Depends(authenticate)])
    def sources(request: Request):
        return request.app.state.db.list_sources()

    @app.post("/api/chat", dependencies=[Depends(authenticate)])
    async def chat(query: Query, request: Request):
        return await request.app.state.rag.ask(query.question)

    @app.post("/api/search", dependencies=[Depends(authenticate)])
    async def search(query: Query, request: Request):
        vector = await request.app.state.rag.llm.embed_query(query.question)
        rows = request.app.state.db.search(query.question, vector)
        return [
            {
                "message_id": row["message_id"],
                "text": row["text"],
                "platform": row["platform"],
                "community": row["source_name"],
                "author": row["author"],
                "timestamp": row["sent_at"],
                "url": row["url"],
            }
            for row in rows
        ]

    @app.get("/api/digests", dependencies=[Depends(authenticate)])
    def digests(request: Request):
        return request.app.state.db.list_digests()

    @app.post("/api/digests/run", dependencies=[Depends(authenticate)])
    async def run_digest(request: Request):
        start, end = previous_week(datetime.now(UTC), settings.zoneinfo)
        digest_id = await request.app.state.digest.generate(start, end)
        if digest_id:
            markdown = request.app.state.db.list_digests(limit=1)[0]["markdown"]
            await push_digest(settings, markdown)
        return {"id": digest_id, "period_start": start, "period_end": end}

    @app.get("/api/config", dependencies=[Depends(authenticate)])
    def get_config():
        current = envfile.read_env(_ENV_PATH)
        return {
            key: (
                envfile.mask(current.get(key, ""))
                if any(hint in key for hint in _SECRET_HINTS)
                else current.get(key, "")
            )
            for key in _CONFIG_KEYS
        }

    @app.post("/api/config", dependencies=[Depends(authenticate)])
    def update_config(update: ConfigUpdate, request: Request):
        nonlocal settings
        unknown = set(update.values) - set(_CONFIG_KEYS)
        if unknown:
            raise HTTPException(
                status_code=400, detail=f"Chiavi non consentite: {', '.join(sorted(unknown))}"
            )
        envfile.write_env(_ENV_PATH, update.values)
        os.environ.update(update.values)
        settings = Settings.from_env()
        request.app.state.llm.configure_chat(settings)
        return {
            "saved": list(update.values),
            "restart_required": bool(set(update.values) - _LIVE_KEYS),
        }

    @app.post("/api/sources", dependencies=[Depends(authenticate)])
    def upsert_source(source: SourceInput, request: Request):
        if source.platform not in {"telegram", "discord", "reddit"}:
            raise HTTPException(status_code=400, detail="Piattaforma non valida")
        existing = load_sources(settings.sources_file)
        updated = [
            item
            for item in existing
            if (item.platform, item.external_id) != (source.platform, source.external_id)
        ]
        updated.append(
            SourceConfig(
                platform=source.platform,
                external_id=source.external_id,
                name=source.name or source.external_id,
                enabled=source.enabled,
                topics=tuple(source.topics),
            )
        )
        save_sources(settings.sources_file, updated)
        request.app.state.db.upsert_sources(updated)
        return {"sources": request.app.state.db.list_sources()}

    @app.get("/api/status", dependencies=[Depends(authenticate)])
    def get_status(request: Request):
        db = request.app.state.db
        return {"workers": db.worker_status(), "sources": db.source_activity()}

    @app.get("/api/settings/retention", dependencies=[Depends(authenticate)])
    def get_retention(request: Request):
        raw = request.app.state.db.get_setting("retention_days")
        return {"days": int(raw) if raw else None}

    @app.post("/api/settings/retention", dependencies=[Depends(authenticate)])
    def set_retention(update: RetentionUpdate, request: Request):
        request.app.state.db.set_setting(
            "retention_days", str(update.days) if update.days else None
        )
        return {"days": update.days}

    @app.post("/api/wipe", dependencies=[Depends(authenticate)])
    def wipe(confirm: WipeConfirm, request: Request):
        if confirm.confirm != "WIPE":
            raise HTTPException(
                status_code=400, detail='Conferma richiesta: invia {"confirm": "WIPE"}'
            )
        request.app.state.db.wipe_all()
        return {"wiped": True}

    @app.get("/api/ignored-authors", dependencies=[Depends(authenticate)])
    def list_ignored(request: Request):
        return request.app.state.db.list_ignored()

    @app.post("/api/ignored-authors", dependencies=[Depends(authenticate)])
    def add_ignored(payload: IgnoreAuthorInput, request: Request):
        request.app.state.db.ignore_author(payload.platform, payload.author_id)
        return {"ignored": True}

    @app.delete("/api/ignored-authors/{platform}/{author_id}", dependencies=[Depends(authenticate)])
    def remove_ignored(platform: str, author_id: str, request: Request):
        request.app.state.db.unignore_author(platform, author_id)
        return {"ignored": False}

    @app.get("/api/usage", dependencies=[Depends(authenticate)])
    def usage(request: Request):
        since = datetime.now(UTC) - timedelta(days=30)
        return request.app.state.db.usage_summary(since)

    @app.get("/api/entities", dependencies=[Depends(authenticate)])
    def list_entities(request: Request, search: str = ""):
        return request.app.state.db.list_entities(search=search)

    @app.get("/api/entities/{entity_id}", dependencies=[Depends(authenticate)])
    def entity_detail(entity_id: int, request: Request):
        detail = request.app.state.db.entity_detail(entity_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="Entità non trovata")
        return detail

    app.mount("/", StaticFiles(directory=static_dir), name="web")
    return app
