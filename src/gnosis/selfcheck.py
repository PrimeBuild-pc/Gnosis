"""Controllo di salute che esegue la SQL vera contro il database vero.

I test dell'API usano un database finto: veloci, ma incapaci di accorgersi che una query
non e' valida per Postgres. Un bug cosi' e' gia' arrivato in produzione (un coalesce senza
cast su una colonna text[]), quindi serve un controllo che tocchi davvero il database.

Si usa con `gnosis selfcheck`, anche da un'installazione appena fatta: crea dati con un
prefisso riconoscibile e li rimuove alla fine, senza toccare quelli reali.
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
    """Restituisce (nome del controllo, esito, dettaglio). Non solleva: raccoglie."""
    prefix = f"{PREFIX}{uuid4().hex}_"
    results: list[tuple[str, bool, str]] = []
    db = Database(settings.database_url)
    db.open()
    try:
        db.migrate()
        results.append(("migrazioni", True, "applicate"))
    except Exception as error:  # noqa: BLE001 - il controllo riporta, non interrompe
        db.close()
        return [("migrazioni", False, str(error))]

    def check(name: str, action) -> object:
        try:
            value = action()
        except Exception as error:  # noqa: BLE001
            results.append((name, False, f"{type(error).__name__}: {error}"))
            return None
        results.append((name, True, ""))
        return value

    try:
        # Il caso che era rotto: campi facoltativi a None su una colonna text[].
        workspace_id = check(
            "creazione workspace (campi facoltativi vuoti)",
            lambda: db.upsert_workspace(name=f"{prefix}A", platform="discord"),
        )
        if workspace_id is None:
            return results
        check(
            "aggiornamento workspace (ruoli e webhook)",
            lambda: db.upsert_workspace(
                name=f"{prefix}A",
                external_id=prefix,
                allowed_role_ids=["1", "2"],
                digest_webhook="https://example.invalid/webhook",
            ),
        )
        check("lettura workspace", db.list_workspaces)
        check(
            "ricerca workspace per id esterno",
            lambda: db.workspace_for_external_id("discord", "assente"),
        )

        # upsert_sources replaces the live allowlist: selfcheck must never call it.
        with db.connection() as connection:
            source_id = connection.execute(
                "INSERT INTO sources (platform, external_id, name, workspace_id) "
                "VALUES ('discord', %s, %s, %s) RETURNING id",
                (f"{prefix}1", f"{prefix}canale", workspace_id),
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

        check("isolamento Discord e citazioni digest", assert_scope)
        check("ricerca senza contesto", lambda: db.search("prova", vector))
        check("ricerca con contesto", lambda: db.search("prova", vector, workspace_id=workspace_id))

        now = datetime.now(UTC)
        check(
            "salvataggio digest con provenienza",
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
            "messaggi per il digest, con contesto",
            lambda: db.messages_between(now - timedelta(days=7), now, workspace_id=workspace_id),
        )
        check("digest gia' presente", lambda: db.digest_exists(now, now, workspace_id=workspace_id))
        check("statistiche con contesto", lambda: db.stats(workspace_id=workspace_id))
        check("canali disponibili", lambda: db.list_available_sources("discord"))
        check("attivita' delle sorgenti", db.source_activity)

        if workspace_id:
            check("eliminazione workspace", lambda: db.delete_workspace(workspace_id))
    finally:
        try:
            _cleanup(db, prefix)
        finally:
            db.close()
    return results
