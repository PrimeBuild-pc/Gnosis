from pathlib import Path

from gnosis.envfile import mask, read_env, write_env


def test_read_env_ignores_comments_and_blanks(tmp_path: Path):
    path = tmp_path / ".env"
    path.write_text("# comment\nFOO=bar\n\nBAZ=qux\n", encoding="utf-8")
    assert read_env(path) == {"FOO": "bar", "BAZ": "qux"}


def test_write_env_updates_existing_key_preserving_rest(tmp_path: Path):
    path = tmp_path / ".env"
    path.write_text("# header\nFOO=old\nBAZ=qux\n", encoding="utf-8")
    write_env(path, {"FOO": "new"})
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines == ["# header", "FOO=new", "BAZ=qux"]


def test_write_env_appends_new_key(tmp_path: Path):
    path = tmp_path / ".env"
    path.write_text("FOO=bar\n", encoding="utf-8")
    write_env(path, {"NEW_KEY": "value"})
    assert read_env(path) == {"FOO": "bar", "NEW_KEY": "value"}


def test_mask_short_value_fully_masked():
    assert mask("abc") == "***"


def test_mask_long_value_keeps_last_four():
    assert mask("sk-or-v1-abcdef") == "***********cdef"


def test_mask_empty_value():
    assert mask("") == ""
