import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from gnosis import secretbox
from gnosis.collectors.gnosis_commands import (
    build_resume,
    parse_period,
    validate_key_input,
)
from gnosis.digest import link_citations, previous_day
from gnosis.notify import split_message

ROME = ZoneInfo("Europe/Rome")


def test_parse_period_includes_the_end_day_in_server_time():
    start, end = parse_period("01/10/2026", "31/10/2026", ROME)
    assert start.isoformat() == "2026-10-01T00:00:00+02:00"
    assert end.isoformat() == "2026-11-01T00:00:00+01:00"
    assert parse_period(None, None, ROME) == (None, None)


@pytest.mark.parametrize(
    ("start", "end"), [("2026-10-01", None), ("31/02/2026", None), ("05/10/2026", "04/10/2026")]
)
def test_parse_period_rejects_bad_or_reversed_dates(start, end):
    with pytest.raises(ValueError):
        parse_period(start, end, ROME)


@pytest.mark.parametrize(
    ("base_url", "model", "problem"),
    [
        ("", "", None),
        ("https://api.deepseek.com", "deepseek-chat", None),
        ("http://evil.local", "x", "key_invalid_url"),
        ("https://api.deepseek.com", "", "key_model_required"),
    ],
)
def test_key_input_validation(base_url, model, problem):
    assert validate_key_input(base_url, model) == problem


def test_secretbox_round_trip_and_rotation():
    token = secretbox.encrypt("bot-token", "sk-member")
    assert "sk-member" not in token
    assert secretbox.decrypt("bot-token", token) == "sk-member"
    assert secretbox.decrypt("rotated-token", token) is None


def test_resume_links_citations_and_splits_for_discord():
    rows = [
        {
            "id": n,
            "platform": "discord",
            "source_name": "#general",
            "author": "ann",
            "sent_at": datetime(2026, 10, 1, tzinfo=UTC),
            "text": "hello",
            "url": f"https://discord.com/channels/1/2/{n}",
        }
        for n in (5, 9)
    ]
    text = AsyncMock(
        side_effect=["- point [M5]", "## Highlights\n- A [M9] B [M5] C [M77]" + "x" * 2500]
    )
    chunks = asyncio.run(build_resume(text, rows, "it", "01/10/2026 → …", capped=True))
    assert all(len(chunk) <= 2000 for chunk in chunks)
    joined = "".join(chunks)
    assert joined.startswith("**Riassunto del server** · 01/10/2026 → … · 2 messaggi")
    assert "Sono stati inclusi solo i 2 messaggi più recenti." in joined
    assert "[[1]](<https://discord.com/channels/1/2/9>)" in joined
    assert "[[2]](<https://discord.com/channels/1/2/5>)" in joined
    assert "[M77]" not in joined  # unknown citations are dropped, never invented links
    assert "Italian" in text.await_args_list[0].args[0]


def test_link_citations_reuses_numbers():
    rows = [{"id": 1, "url": "u1"}]
    assert link_citations("a [M1] b [M1]", rows) == "a [[1]](<u1>) b [[1]](<u1>)"


def test_split_message_keeps_lines_and_limit():
    text = "line\n" * 900
    chunks = split_message(text)
    assert all(len(chunk) <= 2000 for chunk in chunks)
    assert "".join(chunks) == text


def test_previous_day_is_local_midnight_to_midnight():
    start, end = previous_day(datetime(2026, 11, 5, 0, 30, tzinfo=UTC), ROME)
    assert start.isoformat() == "2026-11-04T00:00:00+01:00"
    assert end.isoformat() == "2026-11-05T00:00:00+01:00"
