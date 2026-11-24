"""ElasticsearchIndexStore request shapes (fake client) and an opt-in real-cluster test.

Run the real test against the PLED test cluster (ES 8.19 + IK + stconvert + smartcn):

    RAG_TEST_ES_URL=https://... RAG_TEST_ES_USERNAME=... RAG_TEST_ES_PASSWORD=... \
        uv run pytest -m es tests/test_es_store.py
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import pytest

from rag_engine.adapters.es_mapping import analysis_settings, index_mappings
from rag_engine.adapters.es_store import ElasticsearchIndexStore
from rag_engine.adapters.index_store import ChunkRecord, IndexDefinition, IndexStateUnknown, SearchRoute
from rag_engine.core.resources import EmbeddingProfile
from rag_engine.core.types import FieldSpec, VectorSpec


class _Namespace:
    def __init__(self, owner: FakeES) -> None:
        self.owner = owner

    async def create(self, **kwargs: Any) -> dict[str, Any]:
        self.owner.calls.append(("indices.create", kwargs))
        return {"acknowledged": True}

    async def get(self, **kwargs: Any) -> dict[str, Any]:
        self.owner.calls.append(("indices.get", kwargs))
        name = kwargs["index"]
        return {
            name: {
                "mappings": {"_meta": {"env": "builder"}, "properties": {}},
                "settings": {"index": {"analysis": {"analyzer": {}}}},
            }
        }

    async def delete(self, **kwargs: Any) -> dict[str, Any]:
        self.owner.calls.append(("indices.delete", kwargs))
        return {"acknowledged": True}


class FakeES:
    def __init__(self, responses: dict[str, Any] | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.responses = responses or {}
        self.indices = _Namespace(self)

    def options(self, **kwargs: Any) -> FakeES:
        self.calls.append(("options", kwargs))
        return self

    async def bulk(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("bulk", kwargs))
        return self.responses.get("bulk", {"errors": False, "items": []})

    async def search(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("search", kwargs))
        return self.responses["search"]

    async def delete_by_query(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("delete_by_query", kwargs))
        return self.responses.get("delete_by_query", {"deleted": 2})

    async def count(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("count", kwargs))
        return {"count": 1}


FIELDS = {"text": FieldSpec("string", True, searchable=True), "price": FieldSpec("number", False, filterable=True)}


async def test_bulk_uses_wait_for_refresh_and_request_options() -> None:
    fake = FakeES()
    store = ElasticsearchIndexStore(fake)  # type: ignore[arg-type]
    await store.bulk_write("idx", [ChunkRecord("id-1", {"document_id": "d"})], timeout=12)
    assert fake.calls[0] == ("options", {"request_timeout": 12})
    name, kwargs = fake.calls[1]
    assert name == "bulk" and kwargs["refresh"] == "wait_for" and kwargs["timeout"] == "12s"
    assert kwargs["operations"] == [{"index": {"_index": "idx", "_id": "id-1"}}, {"document_id": "d"}]


async def test_search_and_listing_shapes() -> None:
    hit = {"_source": {"document_id": "d", "data_id": "x", "structdata": {"text": "t"}, "write_id": "w"}, "_score": 1.5}
    fake = FakeES({"search": {"hits": {"hits": [hit]}}})
    store = ElasticsearchIndexStore(fake)  # type: ignore[arg-type]
    filters = [{"field": "structdata.price", "operator": "gte", "value": 300}]
    hits = await store.search("idx", SearchRoute("vector", "text", 5, filters, vector=[0.1, 0.2]), FIELDS)
    assert hits[0].document == {"document_id": "d", "data_id": "x", "structdata": {"text": "t"}}
    knn = fake.calls[-1][1]["knn"]
    assert knn["field"] == "vectors.text.values" and knn["k"] == 5
    assert knn["filter"] == {"bool": {"filter": [{"range": {"structdata.price": {"gte": 300}}}]}}
    await store.search("idx", SearchRoute("fulltext", "text", 5, [], text="散熱孔"), FIELDS)
    assert fake.calls[-1][1]["query"]["bool"]["must"] == [{"match": {"structdata.text": {"query": "散熱孔"}}}]

    buckets = [
        {"key": {"document_id": f"doc-{n}"}, "revisions": {"buckets": [{"key": "r1"}, {"key": ""}]}} for n in range(3)
    ]
    fake.responses["search"] = {"aggregations": {"documents": {"buckets": buckets}}}
    page, next_after = await store.list_documents("idx", None, 2)
    assert page == [("doc-0", ["r1"]), ("doc-1", ["r1"])] and next_after == "doc-1"
    assert fake.calls[-1][1]["aggs"]["documents"]["composite"]["size"] == 3


@pytest.mark.parametrize(
    "response",
    [
        {"deleted": 1, "failures": [{"cause": {"type": "es_rejected_execution_exception"}}]},
        {"deleted": 0, "timed_out": True, "failures": []},
        {"deleted": 1, "version_conflicts": 1, "failures": []},
    ],
)
async def test_partial_deletes_are_not_reported_as_done(response: dict[str, Any]) -> None:
    """Old-batch cleanup and Retire both need a delete that ES confirms in full."""
    store = ElasticsearchIndexStore(FakeES({"delete_by_query": response}))  # type: ignore[arg-type]
    with pytest.raises(IndexStateUnknown):
        await store.delete_batches("idx", "d", {"w-old"})
    with pytest.raises(IndexStateUnknown):
        await store.delete_document("idx", "d")
    complete = ElasticsearchIndexStore(FakeES({"delete_by_query": {"deleted": 2, "failures": []}}))  # type: ignore[arg-type]
    assert await complete.delete_document("idx", "d") == 2


@pytest.mark.es
@pytest.mark.skipif(not os.environ.get("RAG_TEST_ES_URL"), reason="RAG_TEST_ES_URL is not set")
async def test_real_cluster_round_trip() -> None:
    from elasticsearch import AsyncElasticsearch

    auth = (
        (os.environ["RAG_TEST_ES_USERNAME"], os.environ["RAG_TEST_ES_PASSWORD"])
        if os.environ.get("RAG_TEST_ES_USERNAME")
        else None
    )
    client = AsyncElasticsearch(
        os.environ["RAG_TEST_ES_URL"], basic_auth=auth, verify_certs=os.environ.get("RAG_TEST_ES_VERIFY", "1") == "1"
    )
    store = ElasticsearchIndexStore(client)
    name = f"rag-itest-{uuid.uuid4()}"
    fields = {"text": FieldSpec("string", True, searchable=True), "title": FieldSpec("string", True, filterable=True)}
    profile = EmbeddingProfile("p", "p", 3, "m", "1", index_options={"type": "int8_hnsw"})
    vectors = {"text": VectorSpec("text", "p", 3)}
    mappings = index_mappings(fields, vectors, {"p": profile}, "zh_ik")
    meta = {"env": "itest", "system_id": "s", "index_fingerprint": "0" * 64, "index_fingerprint_version": 1}
    await store.create_index(
        IndexDefinition(
            name,
            {**mappings, "_meta": meta},
            {"number_of_shards": 1, "number_of_replicas": 0, "analysis": analysis_settings("zh_ik")},
        )
    )
    try:
        info = await store.get_index(name)
        assert info is not None and info.meta == meta
        body = {
            "document_id": "d1",
            "data_id": "c1",
            "write_id": "w1",
            "structdata": {"text": "定期清潔散熱孔，避免灰塵堆積。", "title": "保養"},
            "vectors": {"text": {"values": [1.0, 0.0, 0.0], "embedding_profile_id": "p", "source_field": "text"}},
        }
        await store.bulk_write(name, [ChunkRecord("e1", body)], timeout=30)
        # Simplified-Chinese query must match Traditional text through stconvert t2s + IK.
        hits = await store.search(name, SearchRoute("fulltext", "text", 5, [], text="清洁散热孔"), fields)
        assert [hit.document["document_id"] for hit in hits] == ["d1"]
        hits = await store.search(
            name,
            SearchRoute(
                "vector",
                "text",
                5,
                [{"field": "structdata.title", "operator": "eq", "value": "保養"}],
                vector=[1.0, 0.0, 0.0],
            ),
            fields,
        )
        assert hits and hits[0].document["data_id"] == "c1"
        assert await store.write_ids(name, "d1") == {"w1"}
        assert (await store.list_documents(name, None, 10))[0] == [("d1", [])]
        assert await store.delete_document(name, "d1") == 1
    finally:
        await store.delete_index(name)
        await store.close()
