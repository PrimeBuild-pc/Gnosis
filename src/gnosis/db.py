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
                row = connection.execute(
                    """
                    INSERT INTO sources (platform, external_id, name, enabled, topics)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (platform, external_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        enabled = EXCLUDED.enabled,
                        topics = EXCLUDED.topics,
                        updated_at = now()
                    RETURNING id
                    """,
                    (
                        source.platform,
                        source.external_id,
                        source.name,
                        source.enabled,
                        list(source.topics),
                    ),
                ).fetchone()
                result[(source.platform, source.external_id.lower())] = row["id"]
        return result

    def save_message(self, source_id: int, message: CollectedMessage, content_hash: str) -> int:
        with self.connection() as connection:
            row = connection.execute(
                """
                INSERT INTO messages
                    (source_id, external_id, author, sent_at, text, url, thread_id,
                     content_hash, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (source_id, external_id) DO UPDATE SET
                    author = EXCLUDED.author,
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

    def search(self, query: str, embedding: list[float], limit: int = 12) -> list[dict[str, Any]]:
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
                    WHERE s.enabled
                    ORDER BY scores.score + 0.002 / (1 + EXTRACT(EPOCH FROM (now() - m.sent_at)) / 2592000) DESC
                    LIMIT %s
                    """,
                    (Vector(embedding), Vector(embedding), query, query, query, limit),
                ).fetchall()
            )

    def messages_between(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        with self.connection() as connection:
            return list(
                connection.execute(
                    """
                    SELECT m.id, m.author, m.sent_at, m.text, m.url, m.kind, m.tags,
                           m.relevance, s.platform, s.name AS source_name
                    FROM messages m JOIN sources s ON s.id = m.source_id
                    WHERE s.enabled AND m.status = 'processed'
                      AND m.sent_at >= %s AND m.sent_at < %s
                    ORDER BY m.sent_at
                    """,
                    (start, end),
                ).fetchall()
            )

    def save_digest(self, start: datetime, end: datetime, markdown: str, source_count: int) -> int:
        with self.connection() as connection:
            row = connection.execute(
                """
                INSERT INTO digests (period_start, period_end, markdown, source_count)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (period_start, period_end) DO UPDATE SET
                    markdown = EXCLUDED.markdown,
                    source_count = EXCLUDED.source_count,
                    created_at = now()
                RETURNING id
                """,
                (start, end, markdown, source_count),
            ).fetchone()
            return row["id"]

    def list_digests(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connection() as connection:
            return list(
                connection.execute(
                    "SELECT * FROM digests ORDER BY period_start DESC LIMIT %s", (limit,)
                ).fetchall()
            )

    def digest_exists(self, start: datetime, end: datetime) -> bool:
        with self.connection() as connection:
            return (
                connection.execute(
                    "SELECT 1 FROM digests WHERE period_start = %s AND period_end = %s",
                    (start, end),
                ).fetchone()
                is not None
            )

    def stats(self) -> dict[str, int]:
        with self.connection() as connection:
            row = connection.execute(
                """
                SELECT
                    (SELECT count(*) FROM sources WHERE enabled) AS sources,
                    (SELECT count(*) FROM messages) AS messages,
                    (SELECT count(*) FROM chunks) AS chunks,
                    (SELECT count(*) FROM digests) AS digests
                """
            ).fetchone()
            return dict(row)

    def list_sources(self) -> list[dict[str, Any]]:
        with self.connection() as connection:
            return list(
                connection.execute(
                    "SELECT platform, external_id, name, enabled, topics, updated_at "
                    "FROM sources ORDER BY platform, name"
                ).fetchall()
            )

    def prune(self, before: datetime) -> int:
        with self.connection() as connection:
            result = connection.execute("DELETE FROM messages WHERE sent_at < %s", (before,))
            return result.rowcount
