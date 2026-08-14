from pathlib import Path

import pytest

from gnosis.config import Settings, load_sources


def test_chat_provider_falls_back_to_openai(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.delenv("GNOSIS_CHAT_API_KEY", raising=False)
    monkeypatch.delenv("GNOSIS_CHAT_BASE_URL", raising=False)
    settings = Settings.from_env()
    assert settings.chat_api_key == "openai-key"
    assert settings.chat_base_url == "https://api.openai.com/v1"


def test_chat_provider_overrides_openai(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("GNOSIS_CHAT_API_KEY", "openrouter-key")
    monkeypatch.setenv("GNOSIS_CHAT_BASE_URL", "https://openrouter.ai/api/v1")
    settings = Settings.from_env()
    assert settings.chat_api_key == "openrouter-key"
    assert settings.chat_base_url == "https://openrouter.ai/api/v1"


def test_telegram_allowed_users_parsed_as_ints(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GNOSIS_TELEGRAM_ALLOWED_USERS", "111, 222,333")
    assert Settings.from_env().telegram_allowed_user_ids == (111, 222, 333)


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
