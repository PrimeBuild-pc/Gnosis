import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from gnosis import worker
from gnosis.config import Settings


@pytest.mark.parametrize(
    "workspaces,expected",
    [
        ([{"id": 1, "name": "A"}, {"id": 2, "name": "B"}], [1, 2]),
        ([], [None]),
    ],
)
def test_scheduler_never_adds_a_mixed_digest_to_scoped_workspaces(
    tmp_path, monkeypatch, workspaces, expected
):
    sources = tmp_path / "sources.toml"
    sources.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        worker.Settings, "from_env", lambda: Settings(chat_api_key="fake", sources_file=sources)
    )
    db = Mock()
    db.list_workspaces.return_value = workspaces
    db.digest_exists.return_value = False
    monkeypatch.setattr(worker, "Database", lambda url: db)
    monkeypatch.setattr(worker, "LLM", Mock())
    generate = AsyncMock(return_value=None)
    monkeypatch.setattr(worker, "DigestService", lambda *args: Mock(generate=generate))

    async def only_digest(database, name, run):
        if name == "digest":
            await run()

    async def stop_after_one_cycle(seconds):
        raise asyncio.CancelledError

    monkeypatch.setattr(worker, "_supervise", only_digest)
    monkeypatch.setattr(worker.asyncio, "sleep", stop_after_one_cycle)
    asyncio.run(worker.run_worker())
    assert [call.kwargs["workspace_id"] for call in generate.call_args_list] == expected
    db.close.assert_called_once()
