from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from gnosis.digest import previous_week


def test_previous_week_uses_local_monday_boundaries():
    start, end = previous_week(datetime(2025, 2, 12, 12, tzinfo=UTC), ZoneInfo("Europe/Rome"))
    assert start.isoformat() == "2025-02-03T00:00:00+01:00"
    assert end.isoformat() == "2025-02-10T00:00:00+01:00"
