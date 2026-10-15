from unittest.mock import MagicMock

from gnosis import selfcheck
from gnosis.config import Settings


def test_selfcheck_never_replaces_the_live_allowlist(monkeypatch):
    db = MagicMock()
    connection = db.connection.return_value.__enter__.return_value
    connection.execute.return_value.fetchone.return_value = {"id": 1}
    db.upsert_workspace.return_value = 1
    db.save_message.return_value = 2
    db.accessible_discord_messages.return_value = {2}
    db.upsert_sources.side_effect = AssertionError("would disable the live allowlist")

    def search(question, vector, **scope):
        if scope.get("discord_guild_id") == question and scope.get("source_external_ids"):
            return [{"message_id": 2}]
        return []

    db.search.side_effect = search
    monkeypatch.setattr(selfcheck, "Database", lambda url: db)
    results = selfcheck.run(Settings())
    assert all(ok for _, ok, _ in results), results
    assert results[0] == ("migrations", True, "applied")
    db.upsert_sources.assert_not_called()
    sql = [call.args[0] for call in connection.execute.call_args_list]
    assert not any("UPDATE sources" in query or "TRUNCATE" in query for query in sql)
    assert all("starts_with" in query for query in sql if query.startswith("DELETE"))
    inputs = db.save_digest.call_args.kwargs["message_ids"]
    assert inputs == [2]
    db.close.assert_called_once()
