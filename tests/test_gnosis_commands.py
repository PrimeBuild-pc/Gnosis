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


def test_resume_from_any_channel_creates_private_channel_and_posts_there(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock

    from gnosis.collectors import gnosis_commands as gc
    from gnosis.config import Settings

    class Tree:
        def add_command(self, group):
            self.group = group

    client = SimpleNamespace(tree=Tree())
    settings = Settings(discord_bot_token="t", secret_key="s", timezone="Europe/Rome")
    db = Mock()
    db.workspace_for_external_id.return_value = {"id": 7}
    db.private_channel.return_value = None
    db.user_llm_key.return_value = {
        "api_key_encrypted": secretbox.encrypt("s", "sk-member"),
        "base_url": "",
        "model": "",
    }
    db.messages_for_member.return_value = [{"id": 1}]
    used_keys = []

    def fake_text_fn(api_key, base_url, model):
        used_keys.append(api_key)
        return AsyncMock()

    monkeypatch.setattr(gc, "user_text_fn", fake_text_fn)
    monkeypatch.setattr(gc, "build_resume", AsyncMock(return_value=["summary"]))
    gc.register(client, settings, db, lambda interaction: ["10"])
    resume = client.tree.group.get_command("resume").callback

    private = SimpleNamespace(id=555, mention="<#555>", send=AsyncMock())
    public = SimpleNamespace(id=10, send=AsyncMock())
    done = {"value": False}

    async def defer(**kwargs):
        done["value"] = True

    guild = SimpleNamespace(
        id=1,
        me=Bot(),
        default_role="everyone",
        categories=[],
        get_channel=lambda channel_id: None,
        create_category=AsyncMock(return_value="category"),
        create_text_channel=AsyncMock(return_value=private),
    )
    interaction = SimpleNamespace(
        guild=guild,
        guild_id=1,
        channel=public,
        channel_id=10,
        locale="it",
        user=Member(),
        response=SimpleNamespace(
            is_done=lambda: done["value"], defer=defer, send_message=AsyncMock()
        ),
        followup=SimpleNamespace(send=AsyncMock()),
    )
    asyncio.run(resume(interaction, None, None))

    guild.create_text_channel.assert_awaited_once()
    db.set_private_channel.assert_called_once_with("1", "42", "555")
    assert used_keys == ["sk-member"]
    private.send.assert_any_await("summary", allowed_mentions=ANY_MENTIONS)
    public.send.assert_not_awaited()
    sent = interaction.followup.send.await_args.args[0]
    assert "<#555>" in sent and "1 messaggi" in sent


class Member:
    """Hashable like discord.Member, which is used as a permission-overwrite key."""

    id = 42
    name = "ann"
    mention = "<@42>"


class Bot:
    guild_permissions = type("Permissions", (), {"manage_channels": True})()


class _AnyMentions:
    def __eq__(self, other):
        return True


ANY_MENTIONS = _AnyMentions()
