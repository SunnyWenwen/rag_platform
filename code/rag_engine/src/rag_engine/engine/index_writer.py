"""Replace one document's chunks in the managed index (06_runtime_api_and_deployment.md#es-write-control-record).

1. Fix the cleanup scope: the write batches currently visible for the document.
2. Bulk-write the new batch under a fresh ``write_id`` (refresh=wait_for).
3. Only after the new batch is searchable, delete the old batches.
"""

from __future__ import annotations

import contextlib
import uuid
from dataclasses import dataclass

from rag_engine.adapters.index_store import BulkRejected, BulkTimeout, ChunkRecord, IndexStateUnknown, IndexStore
from rag_engine.core.canonical import es_document_id
from rag_engine.core.errors import DocumentFailed, EngineError
from rag_engine.core.types import Document, Vectors


class CleanupUnknown(EngineError):
    """The new batch is live but removing old batches could not be confirmed (status ``unknown``)."""

    code = "ES_CLEANUP_UNKNOWN"


@dataclass(frozen=True)
class PreparedWrite:
    document_id: str
    write_id: str
    old_write_ids: frozenset[str]
    records: tuple[ChunkRecord, ...]


def to_records(chunks: list[Document], write_id: str, vectors: Vectors) -> tuple[ChunkRecord, ...]:
    records = []
    for chunk in chunks:
        body = {
            "document_id": chunk["document_id"],
            "data_id": chunk["data_id"],
            "write_id": write_id,
            "structdata": chunk["structdata"],
            # Only vectors selected into the index are stored; the mapping is strict.
            "vectors": {name: value for name, value in chunk.get("vectors", {}).items() if name in vectors},
        }
        if "source_revision" in chunk:
            body["source_revision"] = chunk["source_revision"]
        if "metadata" in chunk:
            body["metadata"] = chunk["metadata"]
        records.append(ChunkRecord(es_document_id(chunk["document_id"], write_id, chunk["data_id"]), body))
    return tuple(records)


class IndexWriter:
    def __init__(self, store: IndexStore, index_name: str, vectors: Vectors, bulk_timeout: float) -> None:
        self._store = store
        self._index = index_name
        self._vectors = vectors
        self._timeout = bulk_timeout

    async def prepare(self, document_id: str, chunks: list[Document]) -> PreparedWrite:
        old = await self._store.write_ids(self._index, document_id)
        write_id = str(uuid.uuid4())
        return PreparedWrite(document_id, write_id, frozenset(old), to_records(chunks, write_id, self._vectors))

    async def commit(self, prepared: PreparedWrite) -> None:
        """Write the batch and retire old batches. Raises DocumentFailed or CleanupUnknown."""
        try:
            await self._store.bulk_write(self._index, prepared.records, self._timeout)
        except BulkTimeout as error:
            await self._discard(prepared)
            raise DocumentFailed(error.message, code="ES_BULK_TIMEOUT", module="indexing") from error
        except (BulkRejected, EngineError) as error:
            await self._discard(prepared)
            raise DocumentFailed(error.message, code="ES_BULK_FAILED", module="indexing") from error
        stale = set(prepared.old_write_ids) - {prepared.write_id}
        try:
            await self._store.delete_batches(self._index, prepared.document_id, stale)
        except IndexStateUnknown as error:
            raise CleanupUnknown(error.message, module="indexing") from error

    async def _discard(self, prepared: PreparedWrite) -> None:
        """Best effort: remove whatever part of this batch reached the index."""
        # A late or partial batch stays identifiable by its write_id if this cleanup fails.
        with contextlib.suppress(EngineError):
            await self._store.delete_batches(self._index, prepared.document_id, {prepared.write_id})
