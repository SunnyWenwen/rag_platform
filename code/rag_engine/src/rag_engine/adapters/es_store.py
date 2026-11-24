"""Elasticsearch implementation of IndexStore (ES 8.19, official async client).

Not yet verified against a real cluster in this repository's CI. Run the ``es``-marked tests
against the PLED test cluster before relying on it (see docs/roadmap.md, task R1).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from elasticsearch import (
    ApiError,
    AsyncElasticsearch,
    BadRequestError,
    ConnectionTimeout,
    NotFoundError,
    TransportError,
)

from rag_engine.adapters.es_mapping import fulltext_query, knn_clause
from rag_engine.adapters.index_store import (
    BulkRejected,
    BulkTimeout,
    ChunkRecord,
    Hit,
    IndexAlreadyExists,
    IndexDefinition,
    IndexInfo,
    IndexStateUnknown,
    SearchRoute,
    candidate,
)
from rag_engine.core.errors import UpstreamError
from rag_engine.core.types import Fields

_SOURCE_EXCLUDES = ["vectors", "write_id"]


def _confirmed_deletes(response: Any, what: str) -> int:
    """Deleted count of a delete_by_query that ES confirms in full. Timeouts, failures and version
    conflicts leave documents behind, so the result is unknown, never success."""
    conflicts = response.get("version_conflicts", 0)
    if response.get("timed_out") or response.get("failures") or conflicts:
        raise IndexStateUnknown(
            f"{what} not confirmed: timed_out={bool(response.get('timed_out'))}, "
            f"failures={len(response.get('failures') or [])}, version_conflicts={conflicts}"
        )
    return int(response.get("deleted", 0))


class ElasticsearchIndexStore:
    def __init__(self, client: AsyncElasticsearch) -> None:
        self._es = client

    async def close(self) -> None:
        await self._es.close()

    async def ping(self) -> bool:
        try:
            return bool(await self._es.ping())
        except (ApiError, TransportError):
            return False

    async def get_index(self, name: str) -> IndexInfo | None:
        try:
            response = await self._es.indices.get(index=name)
        except NotFoundError:
            return None
        except (ApiError, TransportError) as error:
            raise IndexStateUnknown(f"cannot read index {name}: {error}") from error
        body = response[name]
        mappings = dict(body.get("mappings", {}))
        meta = mappings.pop("_meta", {})
        analysis = body.get("settings", {}).get("index", {}).get("analysis", {})
        return IndexInfo(name, meta, mappings, analysis)

    async def create_index(self, definition: IndexDefinition) -> None:
        try:
            await self._es.indices.create(
                index=definition.name, mappings=definition.mappings, settings=definition.settings
            )
        except BadRequestError as error:
            if error.error == "resource_already_exists_exception":
                raise IndexAlreadyExists(f"index {definition.name} already exists") from error
            raise UpstreamError(f"index creation rejected: {error}", module="indexing") from error
        except (ApiError, TransportError) as error:
            raise IndexStateUnknown(f"index creation result unknown: {error}") from error

    async def delete_index(self, name: str) -> bool:
        try:
            await self._es.indices.delete(index=name)
        except NotFoundError:
            return False
        except (ApiError, TransportError) as error:
            raise IndexStateUnknown(f"index deletion result unknown: {error}") from error
        return True

    async def write_ids(self, name: str, document_id: str) -> set[str]:
        try:
            response = await self._es.search(
                index=name,
                size=0,
                query={"term": {"document_id": document_id}},
                aggs={"write_ids": {"terms": {"field": "write_id", "size": 1000}}},
            )
        except (ApiError, TransportError) as error:
            raise IndexStateUnknown(f"cannot read write batches: {error}") from error
        return {bucket["key"] for bucket in response["aggregations"]["write_ids"]["buckets"]}

    async def bulk_write(self, name: str, records: Sequence[ChunkRecord], timeout: float) -> None:
        operations: list[dict[str, Any]] = []
        for record in records:
            operations.append({"index": {"_index": name, "_id": record.es_id}})
            operations.append(record.body)
        try:
            response = await self._es.options(request_timeout=timeout).bulk(
                operations=operations, refresh="wait_for", timeout=f"{int(timeout)}s"
            )
        except ConnectionTimeout as error:
            raise BulkTimeout("timed out waiting for the bulk response", module="indexing") from error
        except (ApiError, TransportError) as error:
            raise UpstreamError(f"bulk request failed: {error}", module="indexing") from error
        if response.get("errors"):
            reason = next(
                (
                    item["index"].get("error", {}).get("reason")
                    for item in response["items"]
                    if "error" in item.get("index", {})
                ),
                "bulk item rejected",
            )
            raise BulkRejected(str(reason), module="indexing")

    async def delete_batches(self, name: str, document_id: str, write_ids: set[str]) -> int:
        if not write_ids:
            return 0
        try:
            response = await self._es.delete_by_query(
                index=name,
                query={
                    "bool": {
                        "filter": [{"term": {"document_id": document_id}}, {"terms": {"write_id": sorted(write_ids)}}]
                    }
                },
                refresh=True,
                conflicts="proceed",
            )
        except (ApiError, TransportError) as error:
            raise IndexStateUnknown(f"batch cleanup result unknown: {error}") from error
        return _confirmed_deletes(response, "batch cleanup")

    async def document_exists(self, name: str, document_id: str) -> bool:
        try:
            response = await self._es.count(index=name, query={"term": {"document_id": document_id}})
        except (ApiError, TransportError) as error:
            raise UpstreamError(f"document lookup failed: {error}", module="indexing") from error
        return int(response["count"]) > 0

    async def list_documents(
        self, name: str, after: str | None, limit: int
    ) -> tuple[list[tuple[str, list[str]]], str | None]:
        composite: dict[str, Any] = {
            "size": limit + 1,
            "sources": [{"document_id": {"terms": {"field": "document_id", "order": "asc"}}}],
        }
        if after is not None:
            composite["after"] = {"document_id": after}
        try:
            response = await self._es.search(
                index=name,
                size=0,
                aggs={
                    "documents": {
                        "composite": composite,
                        "aggs": {"revisions": {"terms": {"field": "source_revision", "size": 100}}},
                    }
                },
            )
        except (ApiError, TransportError) as error:
            raise UpstreamError(f"document listing failed: {error}", module="indexing") from error
        buckets = response["aggregations"]["documents"]["buckets"]
        page = [
            (
                bucket["key"]["document_id"],
                sorted(item["key"] for item in bucket["revisions"]["buckets"] if item["key"]),
            )
            for bucket in buckets[:limit]
        ]
        next_after = page[-1][0] if len(buckets) > limit else None
        return page, next_after

    async def delete_document(self, name: str, document_id: str) -> int:
        try:
            response = await self._es.delete_by_query(
                index=name, query={"term": {"document_id": document_id}}, refresh=True, conflicts="proceed"
            )
        except (ApiError, TransportError) as error:
            raise IndexStateUnknown(f"document deletion result unknown: {error}") from error
        return _confirmed_deletes(response, "document deletion")

    async def search(self, name: str, route: SearchRoute, fields: Fields) -> list[Hit]:
        try:
            if route.kind == "fulltext":
                response = await self._es.search(
                    index=name,
                    size=route.k,
                    query=fulltext_query(route.target, route.text or "", route.filters, fields),
                    source_excludes=_SOURCE_EXCLUDES,
                )
            else:
                response = await self._es.search(
                    index=name,
                    size=route.k,
                    knn=knn_clause(route.target, route.vector or [], route.k, route.filters, fields),
                    source_excludes=_SOURCE_EXCLUDES,
                )
        except (ApiError, TransportError) as error:
            raise UpstreamError(f"search failed: {error}", module="retrieval") from error
        return [Hit(candidate(hit["_source"]), hit.get("_score")) for hit in response["hits"]["hits"]]
