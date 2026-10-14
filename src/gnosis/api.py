from __future__ import annotations

import os
import secrets
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from psycopg.errors import UniqueViolation
from pydantic import BaseModel, Field, field_validator

from . import envfile
from .config import Settings, SourceConfig, load_sources, save_sources
from .db import Database
from .digest import DigestService, previous_week
from .llm import LLM, LLMNotConfigured
from .notify import push_digest
from .rag import RAG

security = HTTPBasic(auto_error=False)

_ENV_PATH = Path(".env")
# Ogni chiave dichiara la sezione a cui appartiene: la dashboard le raggruppa invece di
# presentare un unico elenco piatto. I ruoli Discord e le destinazioni del digest non sono
# qui perche' sono impostazioni di workspace, non globali.
_CONFIG_FIELDS = (
    ("GNOSIS_CHAT_API_KEY", "llm"),
    ("GNOSIS_CHAT_BASE_URL", "llm"),
    ("OPENAI_CHAT_MODEL", "llm"),
    ("OPENAI_API_KEY", "llm"),
    ("OPENAI_BASE_URL", "llm"),
    ("GNOSIS_EMBEDDING_PROVIDER", "llm"),
    ("DISCORD_BOT_TOKEN", "discord"),
    ("TELEGRAM_API_ID", "telegram"),
    ("TELEGRAM_API_HASH", "telegram"),
    ("TELEGRAM_BOT_TOKEN", "telegram"),
    ("GNOSIS_TELEGRAM_ALLOWED_USERS", "telegram"),
    ("REDDIT_CLIENT_ID", "reddit"),
    ("REDDIT_CLIENT_SECRET", "reddit"),
)
_CONFIG_KEYS = tuple(key for key, _ in _CONFIG_FIELDS)
_CONFIG_SECTIONS = dict(_CONFIG_FIELDS)
_SECRET_HINTS = ("KEY", "TOKEN", "SECRET", "HASH", "WEBHOOK")
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


# I tre bot Prime Build. La dashboard e' la stessa per tutti: cambia solo quale e' quello
# corrente e quali degli altri risultano raggiungibili.
_BOT_CATALOG = {
    "gnosis": {
        "name": "Gnosis",
        "icon": "\N{BRAIN}",
        "repo": "https://github.com/PrimeBuild-pc/Gnosis",
        "install": (
            "git clone https://github.com/PrimeBuild-pc/Gnosis.git && cd Gnosis && ./install.sh"
        ),
    },
    "doorman": {
        "name": "Doorman",
        "icon": "\N{DOOR}",
        "repo": "https://github.com/PrimeBuild-pc/Doorman",
        "install": (
            "git clone https://github.com/PrimeBuild-pc/Doorman.git && cd Doorman && ./install.sh"
        ),
    },
    "dview": {
        "name": "D-View",
        "icon": "\N{CLOSED LOCK WITH KEY}",
        "repo": "https://github.com/PrimeBuild-pc/D-View",
        "install": (
            "git clone https://github.com/PrimeBuild-pc/D-View.git && cd D-View "
            "&& pnpm install && docker compose up -d"
        ),
    },
}
_CURRENT_BOT = "gnosis"
_BOT_PROBE_TTL = 30.0
_bot_probe_cache: dict[str, tuple[float, bool]] = {}


def _bot_reachable(url: str) -> bool:
    """Una richiesta breve all'indirizzo dichiarato. Qualsiasi risposta HTTP basta: serve
    sapere se c'e' qualcosa in ascolto, non interrogarne l'API."""
    cached = _bot_probe_cache.get(url)
    now = time.monotonic()
    if cached and now - cached[0] < _BOT_PROBE_TTL:
        return cached[1]
    try:
        with httpx.Client(timeout=2.0, follow_redirects=True) as client:
            client.get(url)
        alive = True
    except Exception:  # noqa: BLE001 - qualsiasi errore di rete significa non raggiungibile
        alive = False
    _bot_probe_cache[url] = (now, alive)
    return alive


def _is_secret(key: str) -> bool:
    return any(hint in key for hint in _SECRET_HINTS)


class Query(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    workspace_id: int | None = Field(default=None, gt=0)

    @field_validator("question")
    @classmethod
    def nonblank_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Domanda vuota")
        return value.strip()


class ConfigUpdate(BaseModel):
    values: dict[str, str]

    @field_validator("values")
    @classmethod
    def validate_settings(cls, values: dict[str, str]) -> dict[str, str]:
        if values.get("GNOSIS_EMBEDDING_PROVIDER", "local") not in {"local", "openai"}:
            raise ValueError("Provider embedding non valido")
        for key in ("TELEGRAM_API_ID", "GNOSIS_TELEGRAM_ALLOWED_USERS"):
            raw = values.get(key, "")
            if raw and any(
                not value.strip().isascii()
                or not value.strip().isdigit()
                or int(value.strip()) <= 0
                for value in raw.split(",")
            ):
                raise ValueError(f"{key}: ID numerici positivi richiesti")
            if key == "TELEGRAM_API_ID" and "," in raw:
                raise ValueError("TELEGRAM_API_ID: un solo ID richiesto")
        return values


class SourceInput(BaseModel):
    platform: str
    external_id: str = Field(min_length=1)
    name: str = ""
    enabled: bool = True
    topics: list[str] = Field(default_factory=list)
    workspace: str = ""


class WorkspaceInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    platform: Literal["discord", "telegram", "reddit"] | None = None
    external_id: str | None = None
    allowed_role_ids: list[str] | None = None
    digest_webhook: str | None = None
    digest_telegram_chat_id: str | None = None

    @field_validator("name")
    @classmethod
    def workspace_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Nome workspace vuoto")
        return value.strip()

    @field_validator("external_id")
    @classmethod
    def numeric_server_id(cls, value: str | None) -> str | None:
        if value is not None and (not value.isascii() or not value.isdigit() or int(value) <= 0):
            raise ValueError("ID server non valido")
        return value

    @field_validator("allowed_role_ids")
    @classmethod
    def numeric_roles(cls, values: list[str] | None) -> list[str] | None:
        if values is not None and any(
            not value.isascii() or not value.isdigit() or int(value) <= 0 for value in values
        ):
            raise ValueError("ID ruolo non valido")
        return values


class RetentionUpdate(BaseModel):
    days: int | None = Field(default=None, ge=1)


class WipeConfirm(BaseModel):
    confirm: str


class IgnoreAuthorInput(BaseModel):
    platform: str
    author_id: str = Field(min_length=1)


def create_app() -> FastAPI:
    settings = Settings.from_env()
    if not settings.username or not settings.password or settings.password == "change-me":
        raise RuntimeError("Imposta GNOSIS_USERNAME e una GNOSIS_PASSWORD personale")

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

    @app.middleware("http")
    async def private_app(request: Request, call_next):
        if request.url.path != "/health":
            try:
                authenticate(await security(request))
            except HTTPException as error:
                return JSONResponse(
                    status_code=error.status_code,
                    content={"detail": error.detail},
                    headers=error.headers,
                )
            if request.method not in {"GET", "HEAD", "OPTIONS"}:
                origin = request.headers.get("origin")
                expected = f"{request.url.scheme}://{request.url.netloc}"
                if (origin and origin != expected) or request.headers.get("sec-fetch-site") in {
                    "cross-site",
                    "same-site",
                }:
                    return JSONResponse(status_code=403, content={"detail": "Origine non valida"})
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.exception_handler(UniqueViolation)
    async def duplicate_workspace(request: Request, error: UniqueViolation) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": "ID server gia' assegnato"})

    def public_workspaces(db):
        return [
            {**row, "digest_webhook": envfile.mask(row.get("digest_webhook", ""))}
            for row in db.list_workspaces()
        ]

    def require_workspace(db, workspace_id):
        if workspace_id is not None and not any(
            row["id"] == workspace_id for row in db.list_workspaces()
        ):
            raise HTTPException(status_code=404, detail="Workspace non trovato")

    static_dir = Path(__file__).with_name("static")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", dependencies=[Depends(authenticate)])
    def index():
        return FileResponse(static_dir / "index.html")

    @app.get("/api/stats", dependencies=[Depends(authenticate)])
    def stats(request: Request, workspace_id: int | None = None):
        return request.app.state.db.stats(workspace_id=workspace_id)

    @app.get("/api/bots", dependencies=[Depends(authenticate)])
    def bots():
        """I bot Prime Build affiancati: quello corrente, e gli altri con il loro stato.

        Il probe lo fa il backend e non il browser: da JavaScript una richiesta verso un
        altro host sarebbe bloccata dal CORS e non si potrebbe distinguere "spento" da
        "raggiungibile ma di un'altra origine".
        """
        configured = dict(settings.bots)
        result = []
        for identifier, entry in _BOT_CATALOG.items():
            url = configured.get(identifier)
            current = identifier == _CURRENT_BOT
            result.append(
                {
                    "id": identifier,
                    "name": entry["name"],
                    "icon": entry["icon"],
                    "repo": entry["repo"],
                    "install": entry["install"],
                    "url": url,
                    "current": current,
                    "installed": current or bool(url and _bot_reachable(url)),
                }
            )
        return result

    @app.get("/api/workspaces", dependencies=[Depends(authenticate)])
    def workspaces(request: Request):
        return public_workspaces(request.app.state.db)

    @app.post("/api/workspaces", dependencies=[Depends(authenticate)])
    def upsert_workspace(payload: WorkspaceInput, request: Request):
        request.app.state.db.upsert_workspace(
            name=payload.name,
            platform=payload.platform,
            external_id=payload.external_id,
            allowed_role_ids=payload.allowed_role_ids,
            digest_webhook=payload.digest_webhook,
            digest_telegram_chat_id=payload.digest_telegram_chat_id,
        )
        return {"workspaces": public_workspaces(request.app.state.db)}

    @app.delete("/api/workspaces/{workspace_id}", dependencies=[Depends(authenticate)])
    def delete_workspace(workspace_id: int, request: Request):
        request.app.state.db.delete_workspace(workspace_id)
        return {"workspaces": public_workspaces(request.app.state.db)}

    @app.get("/api/available-sources", dependencies=[Depends(authenticate)])
    def available_sources(request: Request, platform: str = ""):
        """Canali e chat che il bot vede davvero, per la tendina del tab Sorgenti.
        Li scopre il worker: qui si legge solo la cache che ha scritto."""
        return request.app.state.db.list_available_sources(platform)

    @app.get("/api/sources", dependencies=[Depends(authenticate)])
    def sources(request: Request):
        return request.app.state.db.list_sources()

    @app.post("/api/chat", dependencies=[Depends(authenticate)])
    async def chat(query: Query, request: Request):
        require_workspace(request.app.state.db, query.workspace_id)
        return await request.app.state.rag.ask(query.question, workspace_id=query.workspace_id)

    @app.post("/api/search", dependencies=[Depends(authenticate)])
    async def search(query: Query, request: Request):
        require_workspace(request.app.state.db, query.workspace_id)
        vector = await request.app.state.rag.llm.embed_query(query.question)
        rows = request.app.state.db.search(query.question, vector, workspace_id=query.workspace_id)
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
    def digests(request: Request, workspace_id: int | None = None):
        return request.app.state.db.list_digests(workspace_id=workspace_id)

    @app.post("/api/digests/run", dependencies=[Depends(authenticate)])
    async def run_digest(request: Request, workspace_id: int | None = None):
        db = request.app.state.db
        require_workspace(db, workspace_id)
        start, end = previous_week(datetime.now(UTC), settings.zoneinfo)
        digest_id = await request.app.state.digest.generate(start, end, workspace_id=workspace_id)
        if digest_id and (workspace_id is not None or not db.list_workspaces()):
            markdown = db.list_digests(limit=1, workspace_id=workspace_id)[0]["markdown"]
            workspace = next((w for w in db.list_workspaces() if w["id"] == workspace_id), None)
            await push_digest(
                settings,
                markdown,
                telegram_chat_id=workspace["digest_telegram_chat_id"] if workspace else None,
                discord_webhook=workspace["digest_webhook"] if workspace else None,
            )
        return {"id": digest_id, "period_start": start, "period_end": end}

    @app.get("/api/setup", dependencies=[Depends(authenticate)])
    def setup_state(request: Request):
        """Cosa e' pronto e cosa manca. Restituisce solo dati: le spiegazioni vivono nel
        dizionario i18n del frontend, cosi' le traduzioni stanno in un posto solo."""
        active: dict[str, int] = {}
        for row in request.app.state.db.list_sources():
            if row["enabled"]:
                active[row["platform"]] = active.get(row["platform"], 0) + 1
        return [
            {
                "key": "chat",
                "required": True,
                "ready": bool(settings.chat_api_key),
                "sources": None,
                "fields": ["GNOSIS_CHAT_API_KEY", "GNOSIS_CHAT_BASE_URL", "OPENAI_CHAT_MODEL"],
            },
            {
                "key": "discord",
                "required": False,
                "ready": bool(settings.discord_bot_token),
                "sources": active.get("discord", 0),
                "fields": ["DISCORD_BOT_TOKEN"],
            },
            {
                "key": "telegram",
                "required": False,
                "ready": bool(settings.telegram_api_id and settings.telegram_api_hash),
                "sources": active.get("telegram", 0),
                "fields": ["TELEGRAM_API_ID", "TELEGRAM_API_HASH"],
            },
            {
                "key": "reddit",
                "required": False,
                "ready": bool(settings.reddit_client_id and settings.reddit_client_secret),
                "sources": active.get("reddit", 0),
                "fields": ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET"],
            },
        ]

    @app.get("/api/config", dependencies=[Depends(authenticate)])
    def get_config():
        current = envfile.read_env(_ENV_PATH)
        return [
            {
                "key": key,
                "section": section,
                "secret": _is_secret(key),
                "value": (
                    envfile.mask(current.get(key, "")) if _is_secret(key) else current.get(key, "")
                ),
            }
            for key, section in _CONFIG_FIELDS
        ]

    @app.post("/api/config", dependencies=[Depends(authenticate)])
    def update_config(update: ConfigUpdate, request: Request):
        nonlocal settings
        unknown = set(update.values) - set(_CONFIG_KEYS)
        if unknown:
            raise HTTPException(
                status_code=400, detail=f"Chiavi non consentite: {', '.join(sorted(unknown))}"
            )
        try:
            envfile.write_env(_ENV_PATH, update.values)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
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
                workspace=source.workspace,
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
