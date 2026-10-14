"""Check processing against psycopg's actual connection/cursor API."""

from contextlib import contextmanager
from unittest.mock import Mock

import pytest
from psycopg import Connection, Cursor

from gnosis.db import Database


@pytest.mark.parametrize("chunks", [[], [("first", [1.0, 0.0]), ("second", [0.0, 1.0])]])
def test_finish_message_uses_cursor_for_batch_insert(chunks):
    connection = Mock(spec=Connection)
    cursor = Mock(spec=Cursor)
    connection.cursor.return_value.__enter__ = Mock(return_value=cursor)
    connection.cursor.return_value.__exit__ = Mock(return_value=False)
    db = Database.__new__(Database)

    @contextmanager
    def connected():
        yield connection

    db.connection = connected
    db.finish_message(7, 0.8, ["test"], "note", chunks)

    assert connection.execute.call_args_list[0].args == (
        "DELETE FROM chunks WHERE message_id = %s",
        (7,),
    )
    if chunks:
        sql, rows = cursor.executemany.call_args.args
        assert "INSERT INTO chunks" in sql
        assert [(row[0], row[1], row[2], row[3].to_list()) for row in rows] == [
            (7, position, text, vector) for position, (text, vector) in enumerate(chunks)
        ]
        connection.cursor.return_value.__exit__.assert_called_once()
    else:
        connection.cursor.assert_not_called()
    assert connection.execute.call_args.args[1] == (
        0.8,
        ["test"],
        "note",
        "processed" if chunks else "ignored",
        7,
    )
