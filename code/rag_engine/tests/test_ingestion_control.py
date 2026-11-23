"""Pod-local Ingestion control: cancel states, occupancy conflicts, Bulk timeout and retention."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

import pytest

from conftest import INGESTION, RuntimeClient, basic, make_settings, validate_http
from rag_engine.adapters.embedding import HashEmbedder
from rag_engine.adapters.index_store import ChunkRecord, InMemoryIndexStore
from rag_engine.core.resources import EmbeddingProfile
from rag_engine.engine.pipelines import EngineDeps
from rag_engine.runtime.ingestion import aggregate
from rag_engine.runtime.settings import Settings


class GatedEmbedder(HashEmbedder):
    """Blocks embedding of texts containing a marker until the gate opens."""

    def __init__(self) -> None:
        self.gates: dict[str, asyncio.Event] = {}

    async def embed(self, texts: list[str], profile: EmbeddingProfile) -> list[list[float]]:
        for marker, gate in self.gates.items():
            if any(marker in text for text in texts):
                await gate.wait()
        return await super().embed(texts, profile)


class GatedStore(InMemoryIndexStore):
    """Blocks the Bulk write of one document until the gate opens (write permission is held)."""

    def __init__(self) -> None:
        super().__init__()
        self.gates: dict[str, asyncio.Event] = {}
        self.entered: dict[str, asyncio.Event] = {}

    async def bulk_write(self, name: str, records: Sequence[ChunkRecord], timeout: float) -> None:
        document_id = records[0].body["document_id"] if records else ""
        if document_id in self.gates:
            self.entered.setdefault(document_id, asyncio.Event()).set()
            await self.gates[document_id].wait()
        await super().bulk_write(name, records, timeout)


def doc(document_id: str, body: str) -> dict[str, Any]:
    return {"document_id": document_id, "structdata": {"body": body, "title": "t", "price": 400}}


@pytest.fixture
def settings() -> Settings:
    return make_settings(ingestion_max_concurrency_per_system=2, ingestion_max_concurrency_total=2)


async def _until(predicate: Any, timeout: float = 5.0) -> None:
    async with asyncio.timeout(timeout):
        while not await predicate():
            await asyncio.sleep(0.01)


async def test_cancel_reports_cancelled_and_cancelling(runtime: RuntimeClient) -> None:
    registry = runtime.app.state.registry
    embedder, store = GatedEmbedder(), GatedStore()
    embedder.gates["PREWRITE"] = asyncio.Event()
    store.gates["guide-running"] = asyncio.Event()
    registry.deps = EngineDeps(embedder=embedder, http=registry.deps.http)
    runtime.app.state.stores._memory = store
    await runtime.initialize()

    accepted = await runtime.ingest(
        [
            doc("guide-running", "running text"),
            doc("guide-prewrite", "PREWRITE text"),
            doc("guide-queued", "queued text"),
        ]
    )
    assert accepted.status_code == 202, accepted.text
    run_id = accepted.json()["run_id"]
    store.entered.setdefault("guide-running", asyncio.Event())
    await asyncio.wait_for(store.entered["guide-running"].wait(), 5)

    async def prewrite_running() -> bool:
        statuses = {item["document_id"]: item["status"] for item in (await runtime.run(run_id))["documents"]}
        return statuses["guide-prewrite"] == "running"

    await _until(prewrite_running)
    cancel_path = f"{runtime.business}/ingestions/{run_id}/cancel"
    body = {"document_ids": ["guide-queued", "guide-prewrite", "guide-running", "guide-missing"]}
    cancel = await runtime.http.post(cancel_path, json=body, headers=basic(INGESTION))
    assert cancel.status_code == 200, cancel.text
    validate_http("ingestion_cancel_result", cancel.json())
    assert [(item["result"], item["status"]) for item in cancel.json()["documents"]] == [
        ("cancelled", "cancelled"),
        ("cancelled", "cancelled"),
        ("cancelling", "cancelling"),
        ("not_found", None),
    ]
    retry = await runtime.http.post(cancel_path, json=body, headers=basic(INGESTION))
    assert retry.json() == cancel.json()

    in_progress = await runtime.run(run_id)
    assert in_progress["status"] == "running"
    assert in_progress["counts"]["cancelling"] == 1 and in_progress["counts"]["cancelled"] == 2

    busy = await runtime.ingest([doc("guide-prewrite", "again"), doc("guide-running", "again")])
    assert busy.status_code == 409
    error = busy.json()["error"]
    validate_http("document_busy_error_response", busy.json())
    assert error["conflicts"] == [{"document_id": "guide-running", "status": "cancelling", "run_id": run_id}]
    assert error["path"] == "/documents/1/document_id"

    store.gates["guide-running"].set()
    final = await runtime.wait_run(run_id, {"partial", "completed", "failed", "cancelled"})
    statuses = {item["document_id"]: item["status"] for item in final["documents"]}
    assert statuses == {"guide-running": "completed", "guide-prewrite": "cancelled", "guide-queued": "cancelled"}
    assert final["status"] == "partial"
    after = await runtime.http.post(cancel_path, json={"document_ids": ["guide-running"]}, headers=basic(INGESTION))
    assert after.json()["documents"] == [
        {"document_id": "guide-running", "result": "already_finished", "status": "completed"}
    ]

    embedder.gates["PREWRITE"].set()
    await asyncio.sleep(0.05)
    exists = await runtime.http.get(f"{runtime.business}/documents/guide-prewrite/exists", headers=basic(INGESTION))
    assert exists.json()["exists"] is False


async def test_bulk_timeout_fails_document_and_allows_retry(runtime: RuntimeClient) -> None:
    await runtime.initialize()
    store = runtime.app.state.stores.memory
    store.fail_next_bulk = "timeout"
    first = await runtime.ingest([doc("guide-1", "first text " * 20)])
    run_id = first.json()["run_id"]
    failed = await runtime.wait_run(run_id, {"failed", "completed"})
    assert failed["status"] == "failed"
    assert failed["documents"][0]["error"]["code"] == "ES_BULK_TIMEOUT"
    exists = await runtime.http.get(f"{runtime.business}/documents/guide-1/exists", headers=basic(INGESTION))
    assert exists.json()["exists"] is False  # the partial batch was removed by write_id

    retry = await runtime.ingest([doc("guide-1", "second text")])
    assert retry.status_code == 202
    assert (await runtime.wait_run(retry.json()["run_id"], {"completed", "failed"}))["status"] == "completed"


async def test_resubmission_replaces_previous_chunks(runtime: RuntimeClient) -> None:
    await runtime.initialize()
    store = runtime.app.state.stores.memory
    long_text = "。".join(f"第{n}段內容說明" * 20 for n in range(30))
    first = await runtime.ingest([doc("guide-1", long_text)])
    await runtime.wait_run(first.json()["run_id"], {"completed"})
    index = next(iter(store._indices.values()))
    before = len(index.docs)
    assert before > 1
    second = await runtime.ingest([doc("guide-1", "短內容")])
    await runtime.wait_run(second.json()["run_id"], {"completed"})
    assert len(index.docs) == 1
    assert len({body["write_id"] for body in index.docs.values()}) == 1


async def test_unknown_run_and_retention(runtime: RuntimeClient) -> None:
    await runtime.initialize()
    missing = await runtime.http.get(f"{runtime.business}/ingestions/ing-none", headers=basic(INGESTION))
    assert missing.json() == {"run_id": "ing-none", "status": "unknown"}
    cancel = await runtime.http.post(
        f"{runtime.business}/ingestions/ing-none/cancel", json={"document_ids": ["x"]}, headers=basic(INGESTION)
    )
    assert cancel.status_code == 404 and cancel.json()["error"]["code"] == "INGESTION_RUN_NOT_FOUND"
    accepted = await runtime.ingest([doc("guide-1", "text")])
    run_id = accepted.json()["run_id"]
    await runtime.wait_run(run_id, {"completed"})
    control = runtime.app.state.ingestion
    control._runs[(runtime.system_id, run_id)].finished_at -= 10 * 86_400
    assert control.purge_expired() == 1
    assert (await runtime.run(run_id)) == {"run_id": run_id, "status": "unknown"}
    status = await runtime.http.get(f"{runtime.business}/documents/guide-1/ingestion-status", headers=basic(INGESTION))
    assert status.json()["status"] == "unknown" and status.json()["run_id"] is None


def test_run_status_aggregation() -> None:
    assert aggregate(["queued", "queued"]) == "queued"
    assert aggregate(["queued", "completed"]) == "running"
    assert aggregate(["cancelling", "completed"]) == "running"
    assert aggregate(["unknown", "completed"]) == "unknown"
    assert aggregate(["completed", "completed"]) == "completed"
    assert aggregate(["cancelled", "cancelled"]) == "cancelled"
    assert aggregate(["failed", "cancelled"]) == "failed"
    assert aggregate(["completed", "failed"]) == "partial"
    assert aggregate(["completed", "cancelled"]) == "partial"
