import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from zoneinfo import ZoneInfo

from gnosis.digest import DigestService, previous_week


def test_previous_week_uses_local_monday_boundaries():
    start, end = previous_week(datetime(2025, 2, 12, 12, tzinfo=UTC), ZoneInfo("Europe/Rome"))
    assert start.isoformat() == "2025-02-03T00:00:00+01:00"
    assert end.isoformat() == "2025-02-10T00:00:00+01:00"


def test_digest_records_every_input_not_only_cited_messages():
    now = datetime.now(UTC)
    db = Mock()
    db.messages_between.return_value = [
        {
            "id": message_id,
            "platform": "discord",
            "source_name": "A",
            "author": "member",
            "sent_at": now,
            "text": "test",
        }
        for message_id in (1, 2)
    ]
    llm = SimpleNamespace(text=AsyncMock(return_value="Summary [M1]"))
    asyncio.run(DigestService(db, llm, ZoneInfo("UTC")).generate(now, now, workspace_id=11))
    assert db.save_digest.call_args.kwargs == {"workspace_id": 11, "message_ids": [1, 2]}
