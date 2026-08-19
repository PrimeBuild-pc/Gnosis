import asyncio

import pytest

from gnosis.config import Settings
from gnosis.llm import LLM, LLMNotConfigured


def test_missing_chat_key_does_not_block_construction(monkeypatch: pytest.MonkeyPatch):
    """Il web deve partire senza chiave: la dashboard è dove la chiave si inserisce."""
    monkeypatch.setattr("gnosis.llm.TextEmbedding", lambda model_name: object())
    llm = LLM(Settings(chat_api_key="", embedding_provider="local"))
    assert llm.chat_client is None


def test_missing_chat_key_raises_on_use(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("gnosis.llm.TextEmbedding", lambda model_name: object())
    llm = LLM(Settings(chat_api_key="", embedding_provider="local"))
    with pytest.raises(LLMNotConfigured):
        asyncio.run(llm.text("system", "prompt"))
    with pytest.raises(LLMNotConfigured):
        asyncio.run(llm.json("system", "prompt"))


def test_configure_chat_applies_key_without_restart(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("gnosis.llm.TextEmbedding", lambda model_name: object())
    settings = Settings(chat_api_key="", embedding_provider="local")
    llm = LLM(settings)
    embedder = llm._local_embedder
    llm.configure_chat(Settings(chat_api_key="chat-key", chat_model="modello-nuovo"))
    assert llm.chat_client is not None
    assert llm.chat_model == "modello-nuovo"
    assert llm._local_embedder is embedder  # l'embedder non viene ricostruito


def test_local_embedding_provider_does_not_require_openai_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("gnosis.llm.TextEmbedding", lambda model_name: object())
    settings = Settings(chat_api_key="chat-key", embedding_provider="local", openai_api_key="")
    llm = LLM(settings)
    assert llm.embedding_client is None
    assert llm._local_embedder is not None


def test_openai_embedding_provider_raises_on_use_without_key():
    settings = Settings(chat_api_key="chat-key", embedding_provider="openai", openai_api_key="")
    llm = LLM(settings)
    assert llm.embedding_client is None
    with pytest.raises(LLMNotConfigured):
        asyncio.run(llm.embed(["testo"]))


def test_openai_embedding_provider_builds_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("gnosis.llm.TextEmbedding", lambda model_name: object())
    settings = Settings(
        chat_api_key="chat-key", embedding_provider="openai", openai_api_key="openai-key"
    )
    llm = LLM(settings)
    assert llm.embedding_client is not None
    assert llm._local_embedder is None
