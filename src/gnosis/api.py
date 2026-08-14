from __future__ import annotations

import secrets
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import Settings
from .db import Database
from .digest import DigestService, previous_week
from .llm import LLM
from .rag import RAG

security = HTTPBasic(auto_error=False)


class Query(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


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
        app.state.db = db
        app.state.rag = RAG(db, llm)
        app.state.digest = DigestService(db, llm, settings.zoneinfo)
        yield
        db.close()

    app = FastAPI(title="Gnosis", version="0.1.0", lifespan=lifespan)

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
        return {"id": digest_id, "period_start": start, "period_end": end}

    app.mount("/", StaticFiles(directory=static_dir), name="web")
    return app
