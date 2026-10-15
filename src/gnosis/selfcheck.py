"""Health check that executes real SQL against the real database.

API tests use a fake database: fast, but unable to detect queries that are invalid in
Postgres. Such a bug has already reached production (coalesce without a cast on a text[]
column), so a check that actually accesses the database is needed.

Run with `gnosis selfcheck`, even on a fresh installation: it creates data with a
recognizable prefix and removes it afterward, without touching real data.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from .config import Settings
from .db import Database
from .types import CollectedMessage

PREFIX = "__selfcheck__"


def _cleanup(db: Database, prefix: str) -> None:
    with db.connection() as connection:
        connection.execute("DELETE FROM sources WHERE starts_with(external_id, %s)", (prefix,))
        connection.execute("DELETE FROM workspaces WHERE starts_with(name, %s)", (prefix,))


def run(settings: Settings) -> list[tuple[str, bool, str]]:
    """Return (check name, outcome, detail). Collect failures rather than raising them."""
    prefix = f"{PREFIX}{uuid4().hex}_"
    results: list[tuple[str, bool, str]] = []
    db = Database(settings.database_url)
    db.open()
    try:
        db.migrate()
        results.append(("migrations", True, "applied"))
    except Exception as error:  # noqa: BLE001 - report the failure rather than abort
        db.close()
        return [("migrations", False, str(error))]

    def check(name: str, action) -> object:
        try:
            value = action()
        except Exception as error:  # noqa: BLE001
            results.append((name, False, f"{type(error).__name__}: {error}"))
            return None
        results.append((name, True, ""))
        return value

    try:
        # The previously broken case: optional fields set to None on a text[] column.
        workspace_id = check(
            "workspace creation (empty optional fields)",
            lambda: db.upsert_workspace(name=f"{prefix}A", platform="discord"),
        )
        if workspace_id is None:
            return results
        check(
            "workspace update (roles and webhook)",
            lambda: db.upsert_workspace(
                name=f"{prefix}A",
                external_id=prefix,
                allowed_role_ids=["1", "2"],
                digest_webhook="https://example.invalid/webhook",
            ),
        )
        check("workspace listing", db.list_workspaces)
        check(
            "workspace lookup by external ID",
            lambda: db.workspace_for_external_id("discord", "missing"),
        )

        # upsert_sources replaces the live allowlist: selfcheck must never call it.
        with db.connection() as connection:
            source_id = connection.execute(
                "INSERT INTO sources (platform, external_id, name, workspace_id) "
                "VALUES ('discord', %s, %s, %s) RETURNING id",
                (f"{prefix}1", f"{prefix}channel", workspace_id),
            ).fetchone()["id"]
        vector = [1.0] + [0.0] * (settings.embedding_dimensions - 1)
        message_id = db.save_message(
            source_id,
            CollectedMessage(
                platform="discord",
                source_external_id=f"{prefix}1",
                external_id="1",
                author="selfcheck",
                sent_at=datetime.now(UTC),
                text=prefix,
                url="",
                metadata={"guild_id": prefix},
            ),
            prefix,
        )
        db.finish_message(message_id, 1.0, [], "test", [(prefix, vector)])

        def assert_scope():
            rows = db.search(
                prefix,
                vector,
                workspace_id=workspace_id,
                discord_guild_id=prefix,
                source_external_ids=[f"{prefix}1"],
            )
            assert {row["message_id"] for row in rows} == {message_id}
            assert not db.search(
                prefix,
                vector,
                workspace_id=workspace_id,
                discord_guild_id="other-guild",
                source_external_ids=[f"{prefix}1"],
            )
            assert not db.search(
                prefix,
                vector,
                workspace_id=workspace_id,
                discord_guild_id=prefix,
                source_external_ids=[],
            )
            assert db.accessible_discord_messages(
                {message_id}, workspace_id, prefix, [f"{prefix}1"]
            ) == {message_id}

        check("Discord isolation and digest citations", assert_scope)
        check("unscoped search", lambda: db.search("test", vector))
        check("scoped search", lambda: db.search("test", vector, workspace_id=workspace_id))

        now = datetime.now(UTC)
        check(
            "digest saving with provenance",
            lambda: db.save_digest(
                now,
                now,
                f"Selfcheck [M{message_id}]",
                1,
                workspace_id=workspace_id,
                message_ids=[message_id],
            ),
        )
        check(
            "scoped digest messages",
            lambda: db.messages_between(now - timedelta(days=7), now, workspace_id=workspace_id),
        )
        check(
            "digest already exists", lambda: db.digest_exists(now, now, workspace_id=workspace_id)
        )
        check("scoped statistics", lambda: db.stats(workspace_id=workspace_id))
        check("available channels", lambda: db.list_available_sources("discord"))
        check("source activity", db.source_activity)

        if workspace_id:
            check("workspace deletion", lambda: db.delete_workspace(workspace_id))
    finally:
        try:
            _cleanup(db, prefix)
        finally:
            db.close()
    return results
