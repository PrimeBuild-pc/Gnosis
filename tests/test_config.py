from pathlib import Path

import pytest

from gnosis.config import load_sources


def test_load_sources(tmp_path: Path):
    path = tmp_path / "sources.toml"
    path.write_text('[[reddit]]\nsubreddit="python"\ntopics=["software"]\n', encoding="utf-8")
    sources = load_sources(path)
    assert sources[0].external_id == "python"
    assert sources[0].name == "python"


def test_empty_allowlist_is_rejected(tmp_path: Path):
    path = tmp_path / "sources.toml"
    path.write_text("", encoding="utf-8")
    with pytest.raises(ValueError):
        load_sources(path)
