"""Il caso chicken-and-egg: senza chiave il web deve comunque partire, e salvare la chiave
dalla dashboard deve applicarla al processo in corso senza riavviare il container."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gnosis.api import create_app
from gnosis.config import Settings
from gnosis.llm import LLMNotConfigured

AUTH = ("admin", "secret")


class FakeDatabase:
    def __init__(self, url: str) -> None:
        self.url = url

    def open(self) -> None: ...

    def migrate(self) -> None: ...

    def close(self) -> None: ...

    def record_usage(self, *args) -> None: ...


class FakeLLM:
    def __init__(self, settings: Settings) -> None:
        self.on_usage = None
        self.chat_api_key = settings.chat_api_key
        self.chat_model = settings.chat_model

    def configure_chat(self, settings: Settings) -> None:
        self.chat_api_key = settings.chat_api_key
        self.chat_model = settings.chat_model

    async def embed_query(self, text: str) -> list[float]:
        if not self.chat_api_key:
            raise LLMNotConfigured("Chiave API chat non configurata")
        return [0.0]


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr("gnosis.api.Database", FakeDatabase)
    monkeypatch.setattr("gnosis.api.LLM", FakeLLM)
    env_path = tmp_path / ".env"
    env_path.write_text("GNOSIS_CHAT_API_KEY=\nOPENAI_CHAT_MODEL=gpt-4o-mini\n", encoding="utf-8")
    monkeypatch.setattr("gnosis.api._ENV_PATH", env_path)
    monkeypatch.setenv("GNOSIS_USERNAME", "admin")
    monkeypatch.setenv("GNOSIS_PASSWORD", "secret")
    # setenv registra il valore originale: il monkeypatch lo ripristina anche se a cambiarlo
    # è os.environ.update() dentro update_config.
    monkeypatch.setenv("GNOSIS_CHAT_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
    with TestClient(create_app()) as test_client:
        yield test_client, env_path


def test_web_starts_without_chat_key(client):
    test_client, _ = client
    assert test_client.get("/health").json() == {"status": "ok"}
    assert test_client.get("/api/config", auth=AUTH).status_code == 200
    assert test_client.app.state.llm.chat_api_key == ""


def test_saving_key_applies_without_restart(client):
    test_client, env_path = client
    response = test_client.post(
        "/api/config",
        auth=AUTH,
        json={"values": {"GNOSIS_CHAT_API_KEY": "chiave-nuova"}},
    )
    assert response.status_code == 200
    assert response.json()["restart_required"] is False
    assert "GNOSIS_CHAT_API_KEY=chiave-nuova" in env_path.read_text(encoding="utf-8")
    assert test_client.app.state.llm.chat_api_key == "chiave-nuova"


def test_worker_side_keys_still_require_restart(client):
    test_client, _ = client
    response = test_client.post(
        "/api/config",
        auth=AUTH,
        json={"values": {"DISCORD_BOT_TOKEN": "token"}},
    )
    assert response.json()["restart_required"] is True


def test_chat_without_key_returns_503_not_500(client):
    test_client, _ = client
    response = test_client.post("/api/chat", auth=AUTH, json={"question": "ciao"})
    assert response.status_code == 503
    assert "chiave" in response.json()["detail"].lower()


def test_unknown_key_rejected(client):
    test_client, _ = client
    response = test_client.post(
        "/api/config", auth=AUTH, json={"values": {"GNOSIS_PASSWORD": "scalata"}}
    )
    assert response.status_code == 400
