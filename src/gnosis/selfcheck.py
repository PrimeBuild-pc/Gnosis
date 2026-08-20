"""Controllo di salute che esegue la SQL vera contro il database vero.

I test dell'API usano un database finto: veloci, ma incapaci di accorgersi che una query
non e' valida per Postgres. Un bug cosi' e' gia' arrivato in produzione (un coalesce senza
cast su una colonna text[]), quindi serve un controllo che tocchi davvero il database.

Si usa con `gnosis selfcheck`, anche da un'installazione appena fatta: crea dati con un
prefisso riconoscibile e li rimuove alla fine, senza toccare quelli reali.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from .config import Settings, SourceConfig
from .db import Database

PREFIX = "__selfcheck__"


def _cleanup(db: Database) -> None:
    with db.connection() as connection:
        connection.execute("DELETE FROM sources WHERE external_id LIKE %s", (f"{PREFIX}%",))
        connection.execute("DELETE FROM workspaces WHERE name LIKE %s", (f"{PREFIX}%",))


def run(settings: Settings) -> list[tuple[str, bool, str]]:
    """Restituisce (nome del controllo, esito, dettaglio). Non solleva: raccoglie."""
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
        _cleanup(db)

        # Il caso che era rotto: campi facoltativi a None su una colonna text[].
        workspace_id = check(
            "creazione workspace (campi facoltativi vuoti)",
            lambda: db.upsert_workspace(name=f"{PREFIX}A", platform="discord"),
        )
        check(
            "aggiornamento workspace (ruoli e webhook)",
            lambda: db.upsert_workspace(
                name=f"{PREFIX}A",
                allowed_role_ids=["1", "2"],
                digest_webhook="https://example.invalid/webhook",
            ),
        )
        check("lettura workspace", db.list_workspaces)
        check(
            "ricerca workspace per id esterno",
            lambda: db.workspace_for_external_id("discord", "assente"),
        )

        check(
            "sorgente con workspace",
            lambda: db.upsert_sources(
                [
                    SourceConfig(
                        platform="discord",
                        external_id=f"{PREFIX}1",
                        name=f"{PREFIX}canale",
                        topics=("test",),
                        workspace=f"{PREFIX}A",
                    )
                ]
            ),
        )

        vector = [0.0] * settings.embedding_dimensions
        check("ricerca senza contesto", lambda: db.search("prova", vector))
        check("ricerca con contesto", lambda: db.search("prova", vector, workspace_id=workspace_id))

        now = datetime.now(UTC)
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
            _cleanup(db)
        finally:
            db.close()
    return results
