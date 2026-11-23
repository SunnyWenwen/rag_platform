"""Index storage interface and an in-memory implementation.

``ElasticsearchIndexStore`` (es_store.py) is the production implementation. The in-memory
store mirrors its semantics so the Runtime and its tests run without Elasticsearch; it is
not a product feature (Local Search is a later milestone).
"""

from __future__ import annotations

import asyncio
import copy
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from rag_engine.core.errors import EngineError
from rag_engine.core.filters import matches
from rag_engine.core.types import Document, Fields


class IndexAlreadyExists(EngineError):
    code = "INDEX_CONFLICT"


class IndexStateUnknown(EngineError):
    """The store could not be read reliably (network, permissions). Never treat as missing."""

    code = "SYSTEM_STATE_UNKNOWN"


class BulkTimeout(EngineError):
    code = "ES_BULK_TIMEOUT"


class BulkRejected(EngineError):
    code = "ES_BULK_FAILED"


@dataclass(frozen=True)
class IndexDefinition:
    name: str
    mappings: dict[str, Any]  # includes "_meta"
    settings: dict[str, Any]


@dataclass(frozen=True)
class IndexInfo:
    name: str
    meta: dict[str, Any]
    mappings: dict[str, Any]  # without "_meta"
    analysis: dict[str, Any]


@dataclass(frozen=True)
class ChunkRecord:
    es_id: str
    body: dict[str, Any]


@dataclass(frozen=True)
class SearchRoute:
    kind: Literal["fulltext", "vector"]
    target: str  # structdata field (fulltext) or vector name (vector)
    k: int
    filters: list[dict[str, Any]] = field(default_factory=list)
    text: str | None = None
    vector: list[float] | None = None


@dataclass(frozen=True)
class Hit:
    document: Document
    score: float | None


class IndexStore(Protocol):
    async def ping(self) -> bool: ...
    async def get_index(self, name: str) -> IndexInfo | None: ...
    async def create_index(self, definition: IndexDefinition) -> None: ...
    async def delete_index(self, name: str) -> bool: ...
    async def write_ids(self, name: str, document_id: str) -> set[str]: ...
    async def bulk_write(self, name: str, records: Sequence[ChunkRecord], timeout: float) -> None: ...
    async def delete_batches(self, name: str, document_id: str, write_ids: set[str]) -> int: ...
    async def document_exists(self, name: str, document_id: str) -> bool: ...
    async def list_documents(
        self, name: str, after: str | None, limit: int
    ) -> tuple[list[tuple[str, list[str]]], str | None]: ...
    async def delete_document(self, name: str, document_id: str) -> int: ...
    async def search(self, name: str, route: SearchRoute, fields: Fields) -> list[Hit]: ...


_TERM = re.compile(r"[㐀-鿿]|\w+", re.UNICODE)

# Candidate fields returned to callers; storage-only fields stay internal.
CANDIDATE_KEYS = ("document_id", "data_id", "source_revision", "structdata", "metadata")


def candidate(body: dict[str, Any]) -> Document:
    return {key: copy.deepcopy(body[key]) for key in CANDIDATE_KEYS if key in body}


@dataclass
class _MemoryIndex:
    info: IndexInfo
    docs: dict[str, dict[str, Any]] = field(default_factory=dict)


class InMemoryIndexStore:
    """Single-process store with Elasticsearch-like semantics for tests and demos."""

    def __init__(self) -> None:
        self._indices: dict[str, _MemoryIndex] = {}
        # Test hooks: make the next bulk call time out or fail.
        self.fail_next_bulk: Literal["timeout", "reject"] | None = None
        self.unreachable = False

    def _check(self) -> None:
        if self.unreachable:
            raise IndexStateUnknown("index store unreachable")

    async def ping(self) -> bool:
        return not self.unreachable

    async def get_index(self, name: str) -> IndexInfo | None:
        self._check()
        index = self._indices.get(name)
        return None if index is None else index.info

    async def create_index(self, definition: IndexDefinition) -> None:
        self._check()
        if definition.name in self._indices:
            raise IndexAlreadyExists(f"index {definition.name} already exists")
        mappings = copy.deepcopy(definition.mappings)
        meta = mappings.pop("_meta", {})
        analysis = copy.deepcopy(definition.settings.get("analysis", {}))
        self._indices[definition.name] = _MemoryIndex(IndexInfo(definition.name, meta, mappings, analysis))

    async def delete_index(self, name: str) -> bool:
        self._check()
        return self._indices.pop(name, None) is not None

    def _index(self, name: str) -> _MemoryIndex:
        self._check()
        index = self._indices.get(name)
        if index is None:
            raise IndexStateUnknown(f"index {name} is missing")
        return index

    async def write_ids(self, name: str, document_id: str) -> set[str]:
        index = self._index(name)
        return {body["write_id"] for body in index.docs.values() if body["document_id"] == document_id}

    async def bulk_write(self, name: str, records: Sequence[ChunkRecord], timeout: float) -> None:
        index = self._index(name)
        failure, self.fail_next_bulk = self.fail_next_bulk, None
        if failure == "timeout":
            # Like a lost Bulk response: part of the batch may already be stored.
            for record in records[: len(records) // 2]:
                index.docs[record.es_id] = copy.deepcopy(record.body)
            raise BulkTimeout("timed out waiting for the bulk response", module="indexing")
        if failure == "reject":
            raise BulkRejected("bulk item rejected", module="indexing")
        await asyncio.sleep(0)
        for record in records:
            index.docs[record.es_id] = copy.deepcopy(record.body)

    async def delete_batches(self, name: str, document_id: str, write_ids: set[str]) -> int:
        index = self._index(name)
        doomed = [
            key
            for key, body in index.docs.items()
            if body["document_id"] == document_id and body["write_id"] in write_ids
        ]
        for key in doomed:
            del index.docs[key]
        return len(doomed)

    async def document_exists(self, name: str, document_id: str) -> bool:
        index = self._index(name)
        return any(body["document_id"] == document_id for body in index.docs.values())

    async def list_documents(
        self, name: str, after: str | None, limit: int
    ) -> tuple[list[tuple[str, list[str]]], str | None]:
        index = self._index(name)
        revisions: dict[str, set[str]] = {}
        for body in index.docs.values():
            bucket = revisions.setdefault(body["document_id"], set())
            revision = body.get("source_revision")
            if isinstance(revision, str) and revision:
                bucket.add(revision)
        ordered = sorted(document_id for document_id in revisions if after is None or document_id > after)
        page = ordered[:limit]
        next_after = page[-1] if len(ordered) > limit else None
        return [(document_id, sorted(revisions[document_id])) for document_id in page], next_after

    async def delete_document(self, name: str, document_id: str) -> int:
        index = self._index(name)
        doomed = [key for key, body in index.docs.items() if body["document_id"] == document_id]
        for key in doomed:
            del index.docs[key]
        return len(doomed)

    async def search(self, name: str, route: SearchRoute, fields: Fields) -> list[Hit]:
        index = self._index(name)
        scored: list[tuple[float, str, dict[str, Any]]] = []
        for key, body in index.docs.items():
            if not matches(route.filters, body.get("structdata", {}), fields):
                continue
            score = self._score(route, body)
            if score is not None and score > 0:
                scored.append((score, key, body))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [Hit(candidate(body), score) for score, _, body in scored[: route.k]]

    @staticmethod
    def _score(route: SearchRoute, body: dict[str, Any]) -> float | None:
        if route.kind == "fulltext":
            value = body.get("structdata", {}).get(route.target)
            if not isinstance(value, str) or not route.text:
                return None
            terms = set(_TERM.findall(route.text.lower()))
            text_terms = _TERM.findall(value.lower())
            return float(sum(1 for term in text_terms if term in terms)) / (1 + math.log1p(len(text_terms)))
        stored = body.get("vectors", {}).get(route.target, {}).get("values")
        if stored is None or route.vector is None:
            return None
        dot = sum(a * b for a, b in zip(stored, route.vector, strict=True))
        norm = math.sqrt(sum(a * a for a in stored)) * math.sqrt(sum(b * b for b in route.vector)) or 1.0
        # Same transform as Elasticsearch cosine similarity: (1 + cos) / 2.
        return (1 + dot / norm) / 2
