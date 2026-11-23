"""Embedding clients.

Production uses an OpenAI-compatible ``POST {endpoint}/embeddings`` service hosting bge-m3
(for example Hugging Face Text Embeddings Inference). The Runtime image does not load torch.
"""

from __future__ import annotations

import hashlib
import math
import struct
from typing import Protocol

import httpx

from rag_engine.core.errors import UpstreamError
from rag_engine.core.resources import EmbeddingProfile


class Embedder(Protocol):
    async def embed(self, texts: list[str], profile: EmbeddingProfile) -> list[list[float]]: ...


class HashEmbedder:
    """Deterministic unit vectors derived from SHA-256. Only for tests and offline demos."""

    async def embed(self, texts: list[str], profile: EmbeddingProfile) -> list[list[float]]:
        return [self._vector(text, profile.dimensions) for text in texts]

    @staticmethod
    def _vector(text: str, dimensions: int) -> list[float]:
        values: list[float] = []
        counter = 0
        while len(values) < dimensions:
            digest = hashlib.sha256(f"{counter}:{text}".encode()).digest()
            values.extend(struct.unpack(">8i", digest))
            counter += 1
        vector = [value / 2**31 for value in values[:dimensions]]
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


class OpenAICompatibleEmbedder:
    """Calls ``/embeddings`` in batches and validates the returned dimensions."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def embed(self, texts: list[str], profile: EmbeddingProfile) -> list[list[float]]:
        if profile.endpoint is None:
            raise UpstreamError(f"profile {profile.profile_id} has no embedding endpoint", module="embedding")
        vectors: list[list[float]] = []
        for start in range(0, len(texts), profile.batch_size):
            batch = texts[start : start + profile.batch_size]
            vectors.extend(await self._batch(batch, profile))
        return vectors

    async def _batch(self, batch: list[str], profile: EmbeddingProfile) -> list[list[float]]:
        url = profile.endpoint.rstrip("/") + "/embeddings"  # type: ignore[union-attr]
        payload = {"model": profile.request_model or profile.model_id, "input": batch}
        try:
            response = await self._client.post(url, json=payload, timeout=profile.timeout_seconds)
        except httpx.TimeoutException as error:
            raise UpstreamError(
                "embedding service timed out", code="DEADLINE_EXCEEDED", module="embedding", retryable=True
            ) from error
        except httpx.HTTPError as error:
            raise UpstreamError(
                f"embedding service unreachable: {error}", module="embedding", retryable=True
            ) from error
        if response.status_code != 200:
            raise UpstreamError(
                f"embedding service returned HTTP {response.status_code}",
                module="embedding",
                retryable=response.status_code in (429, 500, 502, 503, 504),
            )
        data = sorted(response.json()["data"], key=lambda item: item["index"])
        vectors = [item["embedding"] for item in data]
        if len(vectors) != len(batch) or any(len(vector) != profile.dimensions for vector in vectors):
            raise UpstreamError("embedding service returned unexpected vectors", module="embedding")
        if not all(math.isfinite(value) for vector in vectors for value in vector):
            raise UpstreamError("embedding service returned non-finite values", module="embedding")
        return vectors
