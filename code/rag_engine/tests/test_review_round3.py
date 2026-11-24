"""Third review round: binding checks, DELETE headers, recovery context, split Pods,
reload with rotated credentials, duplicates during replacement, and memory held by Runs."""

from __future__ import annotations

import asyncio
import gc
import uuid
import weakref
from pathlib import Path
from typing import Any

import pytest

from conftest import MANAGEMENT, SYSTEM_ID, RuntimeClient, basic, scenario_config
from rag_engine.adapters.index_store import IndexDefinition, InMemoryIndexStore
from test_ingestion_control import doc
from test_lifecycle_rules import apply_after_preview, published_binding
from test_lifecycle_safety import SYSTEM_PATH, binding, preview, update_body


def index_name(generation: str) -> str:
    return f"rag-builder-{SYSTEM_ID}-{generation}"


async def other_owned_index(runtime: RuntimeClient, published: dict[str, Any]) -> str:
    """A second index of the same System with valid ownership (generation B)."""
    generation = str(uuid.uuid4())
    store = runtime.app.state.stores.memory
    original = await store.get_index(index_name(published["status"]["index_generation"]))
    meta = runtime.app.state.registry._expected_meta(SYSTEM_ID, published["fingerprint"], "older-operation")
    await store.create_index(IndexDefinition(index_name(generation), {**original.mappings, "_meta": meta}, {}))
    return generation  # same ownership, fingerprint and mapping as A: every index check passes


# 1. The expected binding must be the one this Runtime has loaded.
async def test_update_against_another_generation_is_refused_before_any_delete(runtime: RuntimeClient) -> None:
    published = await runtime.initialize()
    a = published["status"]["index_generation"]
    b = await other_owned_index(runtime, published)
    rebuilt = scenario_config()
    rebuilt["pipelines"]["ingestion"]["chunking"]["parameters"]["max_tokens"] = 200
    for config in (rebuilt, scenario_config()):  # rebuild and reuse
        validation, response = await apply_after_preview(
            runtime,
            config,
            f"update-{uuid.uuid4()}",
            "revision-2",
            **{**update_body(published), "expected_index_generation": b},
        )
        assert validation["index_impact"]["action"] == "blocked", validation
        assert response.status_code == 409 and response.json()["error"]["code"] == "INDEX_CONFLICT", response.text
    store = runtime.app.state.stores.memory
    assert await store.get_index(index_name(a)) is not None and await store.get_index(index_name(b)) is not None
    status = (await runtime.http.get(SYSTEM_PATH, headers=basic(MANAGEMENT))).json()
    assert status["index_generation"] == a and status["can_query"] and status["can_ingest"]


# 2. DELETE of a managed index needs the expected generation and fingerprint.
async def test_delete_without_generation_or_fingerprint_is_refused(runtime: RuntimeClient) -> None:
    published = await runtime.initialize()
    full = binding(published)
    for missing in ("X-Expected-Index-Generation", "X-Expected-Index-Fingerprint"):
        headers = {key: value for key, value in full.items() if key != missing}
        response = await runtime.http.delete(
            SYSTEM_PATH, headers={**basic(MANAGEMENT), "Idempotency-Key": f"del-{missing}", **headers}
        )
        assert response.status_code == 422 and response.json()["error"]["code"] == "REQUEST_VALIDATION_FAILED"
    store = runtime.app.state.stores.memory
    assert await store.get_index(index_name(published["status"]["index_generation"])) is not None
    assert (await runtime.http.get(SYSTEM_PATH, headers=basic(MANAGEMENT))).json()["can_query"]


# 3. recover_index must describe the published binding it recovers.
async def test_recover_index_cannot_point_away_from_the_published_binding(runtime: RuntimeClient) -> None:
    published = await runtime.initialize()
    missing = str(uuid.uuid4())
    recovery = {
        **published_binding(published),
        "recovery_from": {"config_revision": "revision-1", "index_generation": missing},
    }
    response = await runtime.http.post(
        f"{SYSTEM_PATH}/config:validate",
        json={
            **(await preview(runtime, scenario_config(), **published_binding(published)))["request"],
            "operation": "recover_index",
            **recovery,
        },
        headers=basic(MANAGEMENT),
    )
    assert response.status_code == 422 and response.json()["error"]["path"] == "/recovery_from/index_generation"
    assert (await runtime.http.get(SYSTEM_PATH, headers=basic(MANAGEMENT))).json()["can_query"]


# 4. An Inference-only standalone Pod needs only the Inference credentials (05 System API 認證欄位).
async def test_inference_only_pod_needs_only_inference_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import httpx

    from conftest import running
    from rag_engine.runtime.app import create_app
    from test_standalone import ENVIRONMENT, create_index, standalone_settings

    for key in ENVIRONMENT:
        monkeypatch.setenv(key, ENVIRONMENT[key])
    monkeypatch.delenv("INGESTION_API_USERNAME")
    monkeypatch.delenv("INGESTION_API_PASSWORD")
    app = create_app(standalone_settings(tmp_path, pipeline="inference"))
    await create_index(app)
    async with running(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://runtime") as client:
            assert (await client.get("/health/ready")).status_code == 200
            query = await client.post("/v1/queries", json={"query": "x"}, headers=basic(("infer-user", "infer-pass")))
            assert query.status_code == 200, query.text
            ingest = await client.post("/v1/ingestions", json={"documents": []}, headers=basic(("a", "b")))
            assert ingest.status_code in (401, 409)


# 5. A standalone index whose real mapping differs is not served.
async def test_standalone_index_with_a_wrong_mapping_is_not_ready(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import httpx

    from conftest import running
    from rag_engine.runtime.app import create_app
    from test_standalone import ENVIRONMENT, GENERATION, create_index, standalone_settings

    for key in ENVIRONMENT:
        monkeypatch.setenv(key, ENVIRONMENT[key])
    app = create_app(standalone_settings(tmp_path))
    await create_index(app)
    stored = app.state.stores.memory._indices[f"rag-ftest-{SYSTEM_ID}-{GENERATION}"]
    stored.info.mappings["properties"]["structdata"]["properties"].pop("title")
    async with running(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://runtime") as client:
            assert (await client.get("/health/ready")).status_code == 503
            query = await client.post("/v1/queries", json={"query": "x"}, headers=basic(("infer-user", "infer-pass")))
            assert query.json()["error"]["code"] == "INDEX_NOT_READY"


# 6. reload with the same revision and generation but rotated credentials uses the new values.
async def test_reload_after_detach_uses_rotated_credentials(runtime: RuntimeClient) -> None:
    config = scenario_config()
    config["pipelines"]["ingestion"]["indexing"]["parameters"].update(
        service_source="pled_es", es_number="007", account="rag", password="{{PLED_ES_PASSWORD}}"
    )
    config["secret"]["PLED_ES_PASSWORD"] = "old-pass"
    published = await runtime.initialize(config)
    detached = await runtime.http.post(
        f"{SYSTEM_PATH}:detach", headers={**basic(MANAGEMENT), "Idempotency-Key": "d-all", **binding(published)}
    )
    assert detached.status_code == 204
    config["secret"]["PLED_ES_PASSWORD"] = "new-pass"
    _, response = await apply_after_preview(
        runtime, config, "reload-rotated", "revision-1", operation="reload", **published_binding(published)
    )
    assert response.status_code == 200, response.text
    connection = runtime.app.state.registry.systems[SYSTEM_ID].snapshot.compiled.index.connection
    assert connection["password"] == "new-pass"


# 7. While a re-ingested document has both batches visible, one list never repeats a data_id.
class SlowCleanupStore(InMemoryIndexStore):
    def __init__(self) -> None:
        super().__init__()
        self.hold = asyncio.Event()
        self.entered = asyncio.Event()

    async def delete_batches(self, name: str, document_id: str, write_ids: Any) -> int:
        if write_ids:
            self.entered.set()
            await self.hold.wait()
        return await super().delete_batches(name, document_id, write_ids)


async def test_no_duplicate_data_id_while_old_and_new_batches_are_visible(runtime: RuntimeClient) -> None:
    store = SlowCleanupStore()
    runtime.app.state.stores._memory = store
    config = scenario_config()
    config["pipelines"]["inference"]["fixed_filters"] = []
    config["pipelines"]["inference"]["retrieval"]["parameters"] = {
        "per_route_k": 10,
        "fulltext_fields": ["structdata.text"],
    }
    await runtime.initialize(config)
    first = await runtime.ingest([doc("guide-1", "清潔散熱孔")])
    await runtime.wait_run(first.json()["run_id"], {"completed"})
    again = await runtime.ingest([doc("guide-1", "清潔散熱孔")])
    await asyncio.wait_for(store.entered.wait(), 5)  # both batches are visible now
    result = await runtime.query({"query": "清潔散熱孔"})
    ids = [item["data"]["data_id"] for item in result.json()["contexts"][0]["result_sets"][0]["items"]]
    assert ids and len(ids) == len(set(ids)), ids
    store.hold.set()
    await runtime.wait_run(again.json()["run_id"], {"completed"})


# 8. A finished Run does not keep its Config version (Snapshot and LangGraphs) alive.
async def test_finished_runs_release_the_old_snapshot(runtime: RuntimeClient) -> None:
    published = await runtime.initialize()
    accepted = await runtime.ingest([doc("guide-1", "text")])
    await runtime.wait_run(accepted.json()["run_id"], {"completed"})
    old = weakref.ref(runtime.app.state.registry.systems[SYSTEM_ID].snapshot)
    query_only = scenario_config()
    query_only["pipelines"]["inference"]["retrieval"]["parameters"]["top_n"] = 1
    _, updated = await apply_after_preview(runtime, query_only, "update-1", "revision-2", **update_body(published))
    assert updated.status_code == 200
    gc.collect()
    assert old() is None
    run = await runtime.run(accepted.json()["run_id"])
    assert run["status"] == "completed" and run["config_revision"] == "revision-1"
