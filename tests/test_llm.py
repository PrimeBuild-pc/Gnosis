import pytest

from gnosis.config import Settings
from gnosis.llm import LLM


def test_missing_chat_key_raises():
    settings = Settings(chat_api_key="", embedding_provider="local")
    with pytest.raises(ValueError):
        LLM(settings)


def test_local_embedding_provider_does_not_require_openai_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("gnosis.llm.TextEmbedding", lambda model_name: object())
    settings = Settings(chat_api_key="chat-key", embedding_provider="local", openai_api_key="")
    llm = LLM(settings)
    assert llm.embedding_client is None
    assert llm._local_embedder is not None


def test_openai_embedding_provider_requires_openai_key():
    settings = Settings(chat_api_key="chat-key", embedding_provider="openai", openai_api_key="")
    with pytest.raises(ValueError):
        LLM(settings)


def test_openai_embedding_provider_builds_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("gnosis.llm.TextEmbedding", lambda model_name: object())
    settings = Settings(
        chat_api_key="chat-key", embedding_provider="openai", openai_api_key="openai-key"
    )
    llm = LLM(settings)
    assert llm.embedding_client is not None
    assert llm._local_embedder is None
