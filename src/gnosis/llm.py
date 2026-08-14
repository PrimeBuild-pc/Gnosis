from __future__ import annotations

import json
from typing import Any

from openai import AsyncOpenAI

from .config import Settings


class LLM:
    def __init__(self, settings: Settings) -> None:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY obbligatoria (usata per gli embedding)")
        if not settings.chat_api_key:
            raise ValueError("Chiave API chat obbligatoria (OPENAI_API_KEY o GNOSIS_CHAT_API_KEY)")
        self.embedding_client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
        self.chat_client = AsyncOpenAI(
            api_key=settings.chat_api_key,
            base_url=settings.chat_base_url,
        )
        self.chat_model = settings.chat_model
        self.embedding_model = settings.embedding_model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = await self.embedding_client.embeddings.create(
            model=self.embedding_model, input=texts
        )
        vectors = [item.embedding for item in sorted(response.data, key=lambda item: item.index)]
        if any(len(vector) != 1536 for vector in vectors):
            raise ValueError("Il modello embedding deve produrre vettori da 1536 dimensioni")
        return vectors

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
        return (response.choices[0].message.content or "").strip()
