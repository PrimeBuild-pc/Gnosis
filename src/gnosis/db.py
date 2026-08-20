from __future__ import annotations

import json
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from pgvector import Vector
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import SourceConfig
from .types import CollectedMessage


class Database:
    def __init__(self, url: str) -> None:
        self.pool = ConnectionPool(
            url,
            min_size=1,
            max_size=6,
            open=False,
            kwargs={"row_factory": dict_row},
        )
        self._vector_ready = False

    def open(self) -> None:
        self.pool.open(wait=True)

    def close(self) -> None:
        self.pool.close()

    @contextmanager
    def connection(self):
        with self.pool.connection() as connection:
            if self._vector_ready:
                register_vector(connection)
            yield connection

    def migrate(self, directory: Path = Path("migrations")) -> None:
        files = sorted(directory.glob("*.sql"))
        if not files:
            raise FileNotFoundError(f"Nessuna migration in {directory}")
        with self.connection() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
            )
            applied = {
                row["name"] for row in connection.execute("SELECT name FROM schema_migrations")
            }
            for file in files:
                if file.name in applied:
                    continue
                connection.execute(file.read_text(encoding="utf-8"))
                connection.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (file.name,))
        self._vector_ready = True

    def upsert_sources(self, sources: Iterable[SourceConfig]) -> dict[tuple[str, str], int]:
        result: dict[tuple[str, str], int] = {}
        with self.connection() as connection:
            connection.execute("UPDATE sources SET enabled = false, updated_at = now()")
            for source in sources:
                workspace_id = (
                    self._workspace_id_by_name(connection, source.workspace, source.platform)
                    if source.workspace
                    else None
                )
                row = connection.execute(
                    """
                    INSERT INTO sources
                        (platform, external_id, name, enabled, topics, workspace_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (platform, external_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        enabled = EXCLUDED.enabled,
                        topics = EXCLUDED.topics,
                        workspace_id = EXCLUDED.workspace_id,
                        updated_at = now()
                    RETURNING id
                    """,
                    (
                        source.platform,
                        source.external_id,
                        source.name,
                        source.enabled,
                        list(source.topics),
                        workspace_id,
                    ),
                ).fetchone()
                result[(source.platform, source.external_id.lower())] = row["id"]
        return result

    @staticmethod
    def _workspace_id_by_name(connection: Any, name: str, platform: str) -> int:
        """Crea il workspace nominato in sources.toml se non esiste ancora: il file resta la
        fonte di verita' dell'allowlist e non richiede un passaggio dalla dashboard."""
        row = connection.execute(
            """
            INSERT INTO workspaces (name, platform) VALUES (%s, %s)
            ON CONFLICT (name) DO UPDATE SET updated_at = now()
            RETURNING id
            """,
            (name, platform),
        ).fetchone()
        return row["id"]

    def list_workspaces(self) -> list[dict[str, Any]]:
        with self.connection() as connection:
            return list(
                connection.execute(
                    """
                    SELECT w.*, count(s.id) FILTER (WHERE s.enabled) AS active_sources
                    FROM workspaces w
                    LEFT JOIN sources s ON s.workspace_id = w.id
                    GROUP BY w.id ORDER BY w.name
                    """
                ).fetchall()
            )

    def upsert_workspace(
        self,
        name: str,
        platform: str | None = None,
        external_id: str | None = None,
        allowed_role_ids: list[str] | None = None,
        digest_webhook: str | None = None,
        digest_telegram_chat_id: str | None = None,
    ) -> int:
        """I campi lasciati a None non vengono toccati: la dashboard ne salva uno per volta."""
        with self.connection() as connection:
            row = connection.execute(
                """
                INSERT INTO workspaces (name, platform, external_id, allowed_role_ids,
                                        digest_webhook, digest_telegram_chat_id)
                VALUES (%s, %s, %s, coalesce(%s, '{}'), coalesce(%s, ''), coalesce(%s, ''))
                ON CONFLICT (name) DO UPDATE SET
                    platform = coalesce(EXCLUDED.platform, workspaces.platform),
                    external_id = coalesce(EXCLUDED.external_id, workspaces.external_id),
                    allowed_role_ids = coalesce(%s, workspaces.allowed_role_ids),
                    digest_webhook = coalesce(%s, workspaces.digest_webhook),
                    digest_telegram_chat_id = coalesce(%s, workspaces.digest_telegram_chat_id),
                    updated_at = now()
                RETURNING id
                """,
                (
                    name,
                    platform,
                    external_id,
                    allowed_role_ids,
                    digest_webhook,
                    digest_telegram_chat_id,
                    allowed_role_ids,
                    digest_webhook,
                    digest_telegram_chat_id,
                ),
            ).fetchone()
            return row["id"]

    def delete_workspace(self, workspace_id: int) -> None:
        with self.connection() as connection:
            connection.execute("DELETE FROM workspaces WHERE id = %s", (workspace_id,))

    def workspace_for_external_id(self, platform: str, external_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            return connection.execute(
                "SELECT * FROM workspaces WHERE platform = %s AND external_id = %s",
                (platform, external_id),
            ).fetchone()

    def replace_available_sources(self, platform: str, rows: list[dict[str, str]]) -> None:
        """Sostituisce l'elenco dei canali scoperti per una piattaforma. Lo scrive il worker,
        unico processo con le sessioni Telegram/Discord attive."""
        with self.connection() as connection:
            connection.execute("DELETE FROM available_sources WHERE platform = %s", (platform,))
            for row in rows:
                connection.execute(
                    """
                    INSERT INTO available_sources
                        (platform, external_id, name, workspace_external_id, workspace_name)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (platform, external_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        workspace_external_id = EXCLUDED.workspace_external_id,
                        workspace_name = EXCLUDED.workspace_name,
                        refreshed_at = now()
                    """,
                    (
                        platform,
                        row["external_id"],
                        row["name"],
                        row.get("workspace_external_id", ""),
                        row.get("workspace_name", ""),
                    ),
                )

    def list_available_sources(self, platform: str = "") -> list[dict[str, Any]]:
        with self.connection() as connection:
            return list(
                connection.execute(
                    """
                    SELECT * FROM available_sources
                    WHERE (%s = '' OR platform = %s)
                    ORDER BY platform, workspace_name, name
                    """,
                    (platform, platform),
                ).fetchall()
            )

    def save_message(self, source_id: int, message: CollectedMessage, content_hash: str) -> int:
        with self.connection() as connection:
            row = connection.execute(
                """
                INSERT INTO messages
                    (source_id, external_id, author, author_id, sent_at, text, url, thread_id,
                     content_hash, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (source_id, external_id) DO UPDATE SET
                    author = EXCLUDED.author,
                    author_id = EXCLUDED.author_id,
                    sent_at = EXCLUDED.sent_at,
                    text = EXCLUDED.text,
                    url = EXCLUDED.url,
                    thread_id = EXCLUDED.thread_id,
                    metadata = EXCLUDED.metadata,
                    content_hash = EXCLUDED.content_hash,
                    status = CASE
                        WHEN messages.content_hash <> EXCLUDED.content_hash THEN 'pending'
                        ELSE messages.status
                    END,
                    processing_error = CASE
                        WHEN messages.content_hash <> EXCLUDED.content_hash THEN NULL
                        ELSE messages.processing_error
                    END,
                    updated_at = now()
                RETURNING id
                """,
                (
                    source_id,
                    message.external_id,
                    message.author,
                    message.author_id,
                    message.sent_at,
                    message.text,
                    message.url,
                    message.thread_id,
                    content_hash,
                    json.dumps(message.metadata),
                ),
            ).fetchone()
            return row["id"]

    def delete_message(self, source_id: int, external_id: str) -> None:
        with self.connection() as connection:
            connection.execute(
                "DELETE FROM messages WHERE source_id = %s AND external_id = %s",
                (source_id, external_id),
            )

    def pending_messages(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.connection() as connection:
            return list(
                connection.execute(
                    """
                    SELECT m.*, s.platform, s.external_id AS source_external_id,
                           s.name AS source_name, s.topics AS source_topics
                    FROM messages m JOIN sources s ON s.id = m.source_id
                    WHERE m.status IN ('pending', 'failed')
                    ORDER BY m.sent_at
                    LIMIT %s
                    """,
                    (limit,),
                ).fetchall()
            )

    def finish_message(
        self,
        message_id: int,
        relevance: float,
        tags: list[str],
        kind: str,
        chunks: list[tuple[str, list[float]]],
    ) -> None:
        status = "processed" if chunks else "ignored"
        with self.connection() as connection:
            connection.execute("DELETE FROM chunks WHERE message_id = %s", (message_id,))
            if chunks:
                connection.executemany(
                    "INSERT INTO chunks (message_id, position, text, embedding) "
                    "VALUES (%s, %s, %s, %s)",
                    [
                        (message_id, position, text, Vector(embedding))
                        for position, (text, embedding) in enumerate(chunks)
                    ],
                )
            connection.execute(
                """
                UPDATE messages SET relevance = %s, tags = %s, kind = %s, status = %s,
                    processing_error = NULL, processed_at = now(), updated_at = now()
                WHERE id = %s
                """,
                (relevance, tags, kind, status, message_id),
            )

    def fail_message(self, message_id: int, error: str) -> None:
        with self.connection() as connection:
            connection.execute(
                "UPDATE messages SET status = 'failed', processing_error = %s, updated_at = now() "
                "WHERE id = %s",
                (error[:1000], message_id),
            )

    def search(
        self,
        query: str,
        embedding: list[float],
        limit: int = 12,
        workspace_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """workspace_id None = tutte le fonti, cioe' il comportamento storico. Con un
        workspace, le citazioni possono provenire solo dalle sue sorgenti."""
        with self.connection() as connection:
            return list(
                connection.execute(
                    """
                    WITH semantic AS (
                        SELECT id, row_number() OVER (ORDER BY embedding <=> %s) AS rank
                        FROM chunks ORDER BY embedding <=> %s LIMIT 30
                    ), lexical AS (
                        SELECT id, row_number() OVER (
                            ORDER BY ts_rank_cd(search_document, websearch_to_tsquery('simple', %s)) DESC
                        ) AS rank
                        FROM chunks
                        WHERE search_document @@ websearch_to_tsquery('simple', %s)
                        ORDER BY ts_rank_cd(search_document, websearch_to_tsquery('simple', %s)) DESC
                        LIMIT 30
                    ), scores AS (
                        SELECT id, sum(score) AS score FROM (
                            SELECT id, 1.0 / (60 + rank) AS score FROM semantic
                            UNION ALL
                            SELECT id, 1.0 / (60 + rank) AS score FROM lexical
                        ) ranked GROUP BY id
                    )
                    SELECT c.id AS chunk_id, c.text, scores.score,
                           m.id AS message_id, m.author, m.sent_at, m.url, m.kind, m.tags,
                           s.platform, s.name AS source_name
                    FROM scores
                    JOIN chunks c ON c.id = scores.id
                    JOIN messages m ON m.id = c.message_id
                    JOIN sources s ON s.id = m.source_id
                    WHERE s.enabled AND (%s::bigint IS NULL OR s.workspace_id = %s)
                    ORDER BY scores.score + 0.002 / (1 + EXTRACT(EPOCH FROM (now() - m.sent_at)) / 2592000) DESC
                    LIMIT %s
                    """,
                    (
                        Vector(embedding),
                        Vector(embedding),
                        query,
                        query,
                        query,
                        workspace_id,
                        workspace_id,
                        limit,
                    ),
                ).fetchall()
            )

    def messages_between(
        self, start: datetime, end: datetime, workspace_id: int | None = None
    ) -> list[dict[str, Any]]:
        with self.connection() as connection:
            return list(
                connection.execute(
                    """
                    SELECT m.id, m.author, m.sent_at, m.text, m.url, m.kind, m.tags,
                           m.relevance, s.platform, s.name AS source_name
                    FROM messages m JOIN sources s ON s.id = m.source_id
                    WHERE s.enabled AND m.status = 'processed'
                      AND m.sent_at >= %s AND m.sent_at < %s
                      AND (%s::bigint IS NULL OR s.workspace_id = %s)
                    ORDER BY m.sent_at
                    """,
                    (start, end, workspace_id, workspace_id),
                ).fetchall()
            )

    def save_digest(
        self,
        start: datetime,
        end: datetime,
        markdown: str,
        source_count: int,
        workspace_id: int | None = None,
    ) -> int:
        with self.connection() as connection:
            row = connection.execute(
                """
                INSERT INTO digests
                    (period_start, period_end, markdown, source_count, workspace_id)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (workspace_id, period_start, period_end) DO UPDATE SET
                    markdown = EXCLUDED.markdown,
                    source_count = EXCLUDED.source_count,
                    created_at = now()
                RETURNING id
                """,
                (start, end, markdown, source_count, workspace_id),
            ).fetchone()
            return row["id"]

    def list_digests(
        self, limit: int = 20, workspace_id: int | None = None
    ) -> list[dict[str, Any]]:
        with self.connection() as connection:
            return list(
                connection.execute(
                    """
                    SELECT d.*, w.name AS workspace_name FROM digests d
                    LEFT JOIN workspaces w ON w.id = d.workspace_id
                    WHERE (%s::bigint IS NULL OR d.workspace_id = %s)
                    ORDER BY d.period_start DESC LIMIT %s
                    """,
                    (workspace_id, workspace_id, limit),
                ).fetchall()
            )

    def digest_exists(
        self, start: datetime, end: datetime, workspace_id: int | None = None
    ) -> bool:
        with self.connection() as connection:
            return (
                connection.execute(
                    """
                    SELECT 1 FROM digests
                    WHERE period_start = %s AND period_end = %s
                      AND workspace_id IS NOT DISTINCT FROM %s
                    """,
                    (start, end, workspace_id),
                ).fetchone()
                is not None
            )

    def stats(self, workspace_id: int | None = None) -> dict[str, int]:
        with self.connection() as connection:
            row = connection.execute(
                """
                SELECT
                    (SELECT count(*) FROM sources s
                     WHERE s.enabled
                       AND (%s::bigint IS NULL OR s.workspace_id = %s)) AS sources,
                    (SELECT count(*) FROM messages m JOIN sources s ON s.id = m.source_id
                     WHERE (%s::bigint IS NULL OR s.workspace_id = %s)) AS messages,
                    (SELECT count(*) FROM chunks c
                     JOIN messages m ON m.id = c.message_id
                     JOIN sources s ON s.id = m.source_id
                     WHERE (%s::bigint IS NULL OR s.workspace_id = %s)) AS chunks,
                    (SELECT count(*) FROM digests d
                     WHERE (%s::bigint IS NULL OR d.workspace_id = %s)) AS digests
                """,
                (workspace_id,) * 8,
            ).fetchone()
            return dict(row)

    def list_sources(self) -> list[dict[str, Any]]:
        with self.connection() as connection:
            return list(
                connection.execute(
                    "SELECT s.platform, s.external_id, s.name, s.enabled, s.topics, "
                    "s.updated_at, s.workspace_id, w.name AS workspace_name "
                    "FROM sources s LEFT JOIN workspaces w ON w.id = s.workspace_id "
                    "ORDER BY s.platform, s.name"
                ).fetchall()
            )

    def prune(self, before: datetime) -> int:
        with self.connection() as connection:
            result = connection.execute("DELETE FROM messages WHERE sent_at < %s", (before,))
            return result.rowcount

    def wipe_all(self) -> None:
        with self.connection() as connection:
            connection.execute(
                "TRUNCATE TABLE messages, chunks, digests, entities RESTART IDENTITY CASCADE"
            )

    def report_status(self, component: str, status: str, detail: str | None = None) -> None:
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO worker_status (component, status, detail, updated_at)
                VALUES (%s, %s, %s, now())
                ON CONFLICT (component) DO UPDATE SET
                    status = EXCLUDED.status, detail = EXCLUDED.detail, updated_at = now()
                """,
                (component, status, detail),
            )

    def worker_status(self) -> list[dict[str, Any]]:
        with self.connection() as connection:
            return list(
                connection.execute("SELECT * FROM worker_status ORDER BY component").fetchall()
            )

    def source_activity(self) -> list[dict[str, Any]]:
        with self.connection() as connection:
            return list(
                connection.execute(
                    """
                    SELECT s.platform, s.name, s.enabled, w.name AS workspace_name,
                           max(m.processed_at) AS last_processed_at,
                           count(m.id) FILTER (WHERE m.status = 'pending') AS pending
                    FROM sources s
                    LEFT JOIN messages m ON m.source_id = s.id
                    LEFT JOIN workspaces w ON w.id = s.workspace_id
                    GROUP BY s.id, s.platform, s.name, s.enabled, w.name
                    ORDER BY s.platform, s.name
                    """
                ).fetchall()
            )

    def is_ignored(self, platform: str, author_id: str) -> bool:
        with self.connection() as connection:
            return (
                connection.execute(
                    "SELECT 1 FROM ignored_authors WHERE platform = %s AND author_id = %s",
                    (platform, author_id),
                ).fetchone()
                is not None
            )

    def ignore_author(self, platform: str, author_id: str) -> None:
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO ignored_authors (platform, author_id) VALUES (%s, %s) "
                "ON CONFLICT DO NOTHING",
                (platform, author_id),
            )

    def unignore_author(self, platform: str, author_id: str) -> None:
        with self.connection() as connection:
            connection.execute(
                "DELETE FROM ignored_authors WHERE platform = %s AND author_id = %s",
                (platform, author_id),
            )

    def list_ignored(self) -> list[dict[str, Any]]:
        with self.connection() as connection:
            return list(
                connection.execute(
                    "SELECT platform, author_id, created_at FROM ignored_authors "
                    "ORDER BY created_at DESC"
                ).fetchall()
            )

    def get_setting(self, key: str) -> str | None:
        with self.connection() as connection:
            row = connection.execute("SELECT value FROM settings WHERE key = %s", (key,)).fetchone()
            return row["value"] if row else None

    def set_setting(self, key: str, value: str | None) -> None:
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO settings (key, value) VALUES (%s, %s) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                (key, value),
            )

    def record_usage(
        self, kind: str, model: str, prompt_tokens: int, completion_tokens: int
    ) -> None:
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO api_usage (kind, model, prompt_tokens, completion_tokens) "
                "VALUES (%s, %s, %s, %s)",
                (kind, model, prompt_tokens, completion_tokens),
            )

    def usage_summary(self, since: datetime) -> list[dict[str, Any]]:
        with self.connection() as connection:
            return list(
                connection.execute(
                    """
                    SELECT kind, model, count(*) AS requests,
                           sum(prompt_tokens) AS prompt_tokens,
                           sum(completion_tokens) AS completion_tokens
                    FROM api_usage
                    WHERE created_at >= %s
                    GROUP BY kind, model
                    ORDER BY kind, model
                    """,
                    (since,),
                ).fetchall()
            )

    def upsert_entity(self, entity_type: str, name: str) -> int:
        normalized = name.strip().casefold()
        with self.connection() as connection:
            row = connection.execute(
                """
                INSERT INTO entities (type, name, normalized_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (type, normalized_name) DO UPDATE SET name = entities.name
                RETURNING id
                """,
                (entity_type, name.strip(), normalized),
            ).fetchone()
            return row["id"]

    def link_mention(self, entity_id: int, message_id: int) -> None:
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO entity_mentions (entity_id, message_id) VALUES (%s, %s) "
                "ON CONFLICT DO NOTHING",
                (entity_id, message_id),
            )

    def add_relation(
        self, source_entity_id: int, target_entity_id: int, relation: str, message_id: int
    ) -> None:
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO entity_relations "
                "(source_entity_id, target_entity_id, relation, message_id) "
                "VALUES (%s, %s, %s, %s)",
                (source_entity_id, target_entity_id, relation, message_id),
            )

    def list_entities(self, search: str = "", limit: int = 50) -> list[dict[str, Any]]:
        with self.connection() as connection:
            return list(
                connection.execute(
                    """
                    SELECT e.id, e.type, e.name, count(DISTINCT em.message_id) AS mentions
                    FROM entities e
                    LEFT JOIN entity_mentions em ON em.entity_id = e.id
                    WHERE %s = '' OR e.name ILIKE '%%' || %s || '%%'
                    GROUP BY e.id
                    ORDER BY mentions DESC, e.name
                    LIMIT %s
                    """,
                    (search, search, limit),
                ).fetchall()
            )

    def entity_detail(self, entity_id: int) -> dict[str, Any] | None:
        with self.connection() as connection:
            entity = connection.execute(
                "SELECT * FROM entities WHERE id = %s", (entity_id,)
            ).fetchone()
            if not entity:
                return None
            relations = connection.execute(
                """
                SELECT r.id, r.relation,
                       se.id AS source_id, se.name AS source_name,
                       te.id AS target_id, te.name AS target_name
                FROM entity_relations r
                JOIN entities se ON se.id = r.source_entity_id
                JOIN entities te ON te.id = r.target_entity_id
                WHERE r.source_entity_id = %s OR r.target_entity_id = %s
                """,
                (entity_id, entity_id),
            ).fetchall()
            mentions = connection.execute(
                """
                SELECT m.id, m.url, m.sent_at, m.author, s.platform, s.name AS source_name
                FROM entity_mentions em
                JOIN messages m ON m.id = em.message_id
                JOIN sources s ON s.id = m.source_id
                WHERE em.entity_id = %s
                ORDER BY m.sent_at DESC
                LIMIT 50
                """,
                (entity_id,),
            ).fetchall()
            return {"entity": entity, "relations": list(relations), "mentions": list(mentions)}
