"""Offline SQL boundaries; real PostgreSQL semantics are covered by opt-in selfcheck."""

from contextlib import contextmanager
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from gnosis.db import Database


def fake_database(rows):
    db = Database.__new__(Database)
    connection = Mock()
    connection.execute.return_value.fetchall.return_value = rows

    @contextmanager
    def connected():
        yield connection

    db.connection = connected
    return db, connection


def test_search_filters_before_top_30_candidates():
    db, connection = fake_database([])
    db.search("q", [1.0], workspace_id=11, discord_guild_id="101", source_external_ids=["10"])
    sql, params = connection.execute.call_args.args
    eligible = sql.split("), semantic AS (")[0]
    assert "AS MATERIALIZED" in eligible
    assert "s.workspace_id = %s" in eligible
    assert "m.metadata->>'guild_id' = %s" in eligible
    assert "s.external_id = ANY(%s::text[])" in eligible
    assert "s.enabled" in eligible and "m.status = 'processed'" in eligible
    assert "FROM eligible ORDER BY" in sql
    assert "FROM eligible\n" in sql
    assert params[:5] == (11, 11, "101", "101", ["10"])
    assert sql.count("%s") == len(params)


def test_global_search_keeps_indexes_available():
    db, connection = fake_database([])
    db.search("q", [1.0])
    sql, _ = connection.execute.call_args.args
    assert "AS NOT MATERIALIZED" in sql


def test_digest_scope_includes_current_guild_channels_and_enabled_sources():
    db, connection = fake_database([{"id": 1}])
    assert db.accessible_discord_messages({1, 2}, 11, "101", ["10"]) == {1}
    sql, params = connection.execute.call_args.args
    assert "s.enabled AND s.workspace_id = %s AND s.platform = 'discord'" in sql
    assert "m.metadata->>'guild_id' = %s" in sql
    assert params[1:] == (11, "101", ["10"])
    assert sql.count("%s") == len(params)


def test_disabled_sources_never_send_pending_content_to_the_model():
    db, connection = fake_database([])
    db.pending_messages()
    sql, _ = connection.execute.call_args.args
    assert "WHERE s.enabled AND m.status IN ('pending', 'failed')" in sql


def test_workspace_digest_requires_matching_server_metadata():
    db, connection = fake_database([])
    now = datetime.now(UTC)
    db.messages_between(now, now, workspace_id=11)
    sql, params = connection.execute.call_args.args
    assert "w.platform IS DISTINCT FROM 'discord'" in sql
    assert "w.external_id = m.metadata->>'guild_id'" in sql
    assert "s.platform = 'discord'" in sql
    assert sql.count("%s") == len(params)


def test_incomplete_discord_search_never_opens_database():
    db, connection = fake_database([])
    with pytest.raises(ValueError):
        db.search("q", [1.0], discord_guild_id="101", source_external_ids=[])
    connection.execute.assert_not_called()
