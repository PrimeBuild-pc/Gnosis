from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any

from fastembed import TextEmbedding
from openai import AsyncOpenAI

from .config import Settings

UsageCallback = Callable[[str, str, int, int], None]


class LLM:
    def __init__(self, settings: Settings) -> None:
        if not settings.chat_api_key:
            raise ValueError("Chiave API chat obbligatoria (OPENAI_API_KEY o GNOSIS_CHAT_API_KEY)")
        self.chat_client = AsyncOpenAI(
            api_key=settings.chat_api_key,
            base_url=settings.chat_base_url,
        )
        self.chat_model = settings.chat_model
        self.on_usage: UsageCallback | None = None
        self.embedding_model = settings.embedding_model
        self.embedding_dimensions = settings.embedding_dimensions
        self._local_embedder: TextEmbedding | None = None
        self.embedding_client: AsyncOpenAI | None = None
        if settings.embedding_provider == "local":
            self._local_embedder = TextEmbedding(settings.embedding_model)
        else:
            if not settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY obbligatoria (GNOSIS_EMBEDDING_PROVIDER=openai)")
            self.embedding_client = AsyncOpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
            )

    def _check_dimensions(self, vectors: list[list[float]]) -> list[list[float]]:
        if any(len(vector) != self.embedding_dimensions for vector in vectors):
            raise ValueError(
                f"Il modello embedding deve produrre vettori da {self.embedding_dimensions} "
                "dimensioni"
            )
        return vectors

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self._local_embedder is not None:
            embedder = self._local_embedder
            vectors = await asyncio.to_thread(
                lambda: [vector.tolist() for vector in embedder.embed(texts)]
            )
            return self._check_dimensions(vectors)
        response = await self.embedding_client.embeddings.create(
            model=self.embedding_model, input=texts
        )
        vectors = [item.embedding for item in sorted(response.data, key=lambda item: item.index)]
        return self._check_dimensions(vectors)

    async def embed_query(self, text: str) -> list[float]:
        """Come embed(), ma usa il prefisso 'query:' dei modelli e5 per un retrieval corretto."""
        if self._local_embedder is not None:
            embedder = self._local_embedder
            vectors = await asyncio.to_thread(
                lambda: [vector.tolist() for vector in embedder.query_embed([text])]
            )
            return self._check_dimensions(vectors)[0]
        return (await self.embed([text]))[0]

    def _record_usage(self, kind: str, usage: Any) -> None:
        if self.on_usage is not None and usage is not None:
            self.on_usage(kind, self.chat_model, usage.prompt_tokens, usage.completion_tokens)

    async def json(self, system: str, prompt: str) -> dict[str, Any]:
        response = await self.chat_client.chat.completions.create(
            model=self.chat_model,
            response_format={"type": "json_object"},
            temperature=0,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        self._record_usage("json", response.usage)
        return json.loads(response.choices[0].message.content or "{}")

    async def text(self, system: str, prompt: str) -> str:
        response = await self.chat_client.chat.completions.create(
            model=self.chat_model,
            temperature=0,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        self._record_usage("text", response.usage)
        return (response.choices[0].message.content or "").strip()
