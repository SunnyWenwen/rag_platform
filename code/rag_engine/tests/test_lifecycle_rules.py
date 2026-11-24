"""Lifecycle clauses of rag_platform 06#system-lifecycle-api that need their own test.

Each test names the clause it covers; docs/spec_coverage.md maps the clauses to tests.
"""

from __future__ import annotations

import uuid
from typing import Any

from conftest import INFERENCE, INGESTION, MANAGEMENT, SYSTEM_ID, RuntimeClient, basic, scenario_config, validate_http
from test_lifecycle_safety import SYSTEM_PATH, binding, preview, put, update_body

DOC = {"document_id": "guide-1", "structdata": {"body": "定期清潔散熱孔。", "title": "保養", "price": 350}}


def published_binding(published: dict[str, Any]) -> dict[str, Any]:
    return {
        "expected_active_revision": "revision-1",
        "expected_index_generation": published["status"]["index_generation"],
        "expected_index_fingerprint": published["fingerprint"],
    }


async def apply_after_preview(
    runtime: RuntimeClient, config: dict[str, Any], key: str, revision: str, **body: Any
) -> Any:
    planned = await preview(runtime, config, **body)
    validation = planned["validation"]
    request = {**planned["request"], "context_revision": validation["context_revision"], "config_revision": revision}
    if validation["index_impact"]["action"] in ("create", "recover", "rebuild_required"):
        request["target_index_generation"] = str(uuid.uuid4())
    return validation, await put(runtime, request, key)


# B reload: after a restart the Builder reloads the published version onto the existing index.
async def test_reload_after_restart_reconnects_the_existing_index(runtime: RuntimeClient) -> None:
    published = await runtime.initialize()
    accepted = await runtime.ingest([DOC])
    await runtime.wait_run(accepted.json()["run_id"], {"completed"})
    runtime.app.state.registry.systems.clear()  # restart

    assert (await runtime.http.get(SYSTEM_PATH, headers=basic(MANAGEMENT))).status_code == 404
    observed = await runtime.http.get(SYSTEM_PATH, headers={**basic(MANAGEMENT), **binding(published)})
    body = observed.json()
    validate_http("system_status", body)
    assert body["loaded"] is False and body["index_ready"] is True
    assert body["created_by_operation_id"] == "initialize-001"

    validation, response = await apply_after_preview(
        runtime, scenario_config(), "reload-1", "revision-1", operation="reload", **published_binding(published)
    )
    assert validation["index_impact"]["action"] == "reuse", validation
    assert response.status_code == 200, response.text
    status = response.json()
    assert (
        status["loaded"]
        and status["can_query"]
        and status["index_generation"] == published["status"]["index_generation"]
    )
    query = await runtime.query({"query": "散熱孔"})
    assert [item["data"]["document_id"] for item in query.json()["contexts"][0]["result_sets"][0]["items"]] == [
        "guide-1"
    ]


# B reload with a Config whose index no longer matches is blocked (code example in 06).
async def test_reload_with_an_incompatible_config_is_blocked(runtime: RuntimeClient) -> None:
    published = await runtime.initialize()
    runtime.app.state.registry.systems.clear()
    changed = scenario_config()
    changed["pipelines"]["ingestion"]["chunking"]["parameters"]["max_tokens"] = 200
    impact = (await preview(runtime, changed, operation="reload", **published_binding(published)))["validation"]
    assert impact["index_impact"]["action"] == "blocked"
    assert impact["index_impact"]["code"] == "INDEX_RECONNECT_INCOMPATIBLE"


# Pipeline table: Inference cannot initialize, update or recover; it reloads after Ingestion.
async def test_inference_only_reloads(runtime: RuntimeClient) -> None:
    empty = {"expected_active_revision": None, "expected_index_generation": None, "expected_index_fingerprint": None}
    validation, response = await apply_after_preview(
        runtime,
        scenario_config(),
        "init-inference",
        "revision-1",
        operation="initialize",
        pipeline="inference",
        **empty,
    )
    assert validation["index_impact"]["code"] == "PIPELINE_OPERATION_UNSUPPORTED"
    assert response.status_code == 409 and response.json()["error"]["code"] == "PIPELINE_OPERATION_UNSUPPORTED"

    validation, response = await apply_after_preview(
        runtime,
        scenario_config(),
        "init-ingestion",
        "revision-1",
        operation="initialize",
        pipeline="ingestion",
        **empty,
    )
    assert response.status_code == 200, response.text
    status = response.json()
    assert status["pipelines"]["ingestion"]["loaded"] and not status["pipelines"]["inference"]["loaded"]
    published = {"status": status, "fingerprint": validation["index_impact"]["index_fingerprint"]}
    _, response = await apply_after_preview(
        runtime,
        scenario_config(),
        "reload-inference",
        "revision-1",
        operation="reload",
        pipeline="inference",
        **published_binding(published),
    )
    assert response.status_code == 200, response.text
    assert response.json()["pipelines"]["inference"]["loaded"]


# A initialize needs no published version and no loaded System.
async def test_initialize_twice_is_a_state_conflict(runtime: RuntimeClient) -> None:
    await runtime.initialize()
    empty = {"expected_active_revision": None, "expected_index_generation": None, "expected_index_fingerprint": None}
    validation, response = await apply_after_preview(
        runtime, scenario_config(), "init-again", "revision-9", operation="initialize", **empty
    )
    assert validation["index_impact"]["code"] == "SYSTEM_STATE_CONFLICT"
    assert response.status_code == 409 and response.json()["error"]["code"] == "SYSTEM_STATE_CONFLICT"


# Same successful PUT resent after a restart: identified by the target and the creating operation.
async def test_initialize_resent_after_a_restart_reuses_its_own_index(runtime: RuntimeClient) -> None:
    published = await runtime.initialize()
    registry = runtime.app.state.registry
    registry.systems.clear()
    registry.idempotency = type(registry.idempotency)(3600)  # the replay cache is gone too
    response = await put(runtime, published["apply"], "initialize-001")
    assert response.status_code == 200, response.text
    assert response.json()["index_generation"] == published["status"]["index_generation"]
    # Another operation must not claim that index as its own result.
    response = await put(runtime, published["apply"], "initialize-other")
    assert response.status_code == 409


# C update / detach: the expected active revision and generation must match this Runtime.
async def test_expected_binding_mismatches(runtime: RuntimeClient) -> None:
    published = await runtime.initialize()
    query_only = scenario_config()
    query_only["pipelines"]["inference"]["retrieval"]["parameters"]["top_n"] = 1
    stale = {**update_body(published), "expected_active_revision": "revision-0"}
    _, response = await apply_after_preview(runtime, query_only, "update-stale", "revision-2", **stale)
    assert response.status_code == 409 and response.json()["error"]["code"] == "REVISION_CONFLICT", response.text

    for header, code in (
        ("X-Expected-Config-Revision", "REVISION_CONFLICT"),
        ("X-Expected-Index-Generation", "INDEX_CONFLICT"),
    ):
        wrong = {**binding(published), header: "revision-0" if "Revision" in header else str(uuid.uuid4())}
        detached = await runtime.http.post(
            f"{SYSTEM_PATH}:detach", headers={**basic(MANAGEMENT), "Idempotency-Key": f"d-{code}", **wrong}
        )
        assert detached.status_code == 409 and detached.json()["error"]["code"] == code, detached.text


# recover_index: only after the old index is confirmed lost, same revision, new generation.
async def test_recover_index_after_the_index_is_lost(runtime: RuntimeClient) -> None:
    published = await runtime.initialize()
    old = published["status"]["index_generation"]
    recovery = {
        **published_binding(published),
        "recovery_from": {"config_revision": "revision-1", "index_generation": old},
    }

    present = await preview(runtime, scenario_config(), operation="recover_index", **recovery)
    assert present["validation"]["index_impact"]["code"] == "PUBLISHED_INDEX_PRESENT"

    store = runtime.app.state.stores.memory
    await store.delete_index(f"rag-builder-{SYSTEM_ID}-{old}")  # the index is lost
    lost = await runtime.http.get(SYSTEM_PATH, headers={**basic(MANAGEMENT), **binding(published)})
    assert lost.json()["index_ready"] is False and lost.json()["index_generation"] is None  # 06 GET rule
    assert not lost.json()["can_ingest"] and not lost.json()["can_query"]

    planned = await preview(runtime, scenario_config(), operation="recover_index", **recovery)
    assert planned["validation"]["index_impact"]["action"] == "recover"
    request = {
        **planned["request"],
        "context_revision": planned["validation"]["context_revision"],
        "config_revision": "revision-2",  # must equal recovery_from.config_revision
        "target_index_generation": str(uuid.uuid4()),
    }
    wrong = await put(runtime, request, "recover-wrong")
    assert wrong.status_code == 422 and wrong.json()["error"]["path"] == "/config_revision", wrong.text

    request["config_revision"] = "revision-1"
    recovered = await put(runtime, request, "recover-1")
    assert recovered.status_code == 200, recovered.text
    status = recovered.json()
    assert status["index_generation"] == request["target_index_generation"] and status["index_ready"] is True
    assert (await runtime.ingest([DOC])).status_code == 202


# GET /internal/v1/systems lists the Systems loaded on this Runtime.
async def test_list_systems(runtime: RuntimeClient) -> None:
    listed = await runtime.http.get("/internal/v1/systems", headers=basic(MANAGEMENT))
    validate_http("system_list", listed.json())
    assert listed.json()["systems"] == []
    await runtime.initialize()
    listed = (await runtime.http.get("/internal/v1/systems", headers=basic(MANAGEMENT))).json()
    validate_http("system_list", listed)
    assert [item["system_id"] for item in listed["systems"]] == [SYSTEM_ID]


# Request limits: body size and media type (06 error table 413 / 415).
async def test_body_size_and_media_type(runtime: RuntimeClient) -> None:
    await runtime.initialize()
    limit = runtime.app.state.settings.max_body_bytes
    big = {"documents": [DOC], "padding": "x" * (limit + 1)}
    too_large = await runtime.http.post(f"{runtime.business}/ingestions", json=big, headers=basic(INGESTION))
    assert too_large.status_code == 413 and too_large.json()["error"]["code"] == "BODY_TOO_LARGE"
    wrong_type = await runtime.http.post(
        f"{runtime.business}/queries",
        content=b'{"query": "x"}',
        headers={**basic(INFERENCE), "Content-Type": "text/plain"},
    )
    assert wrong_type.status_code == 415 and wrong_type.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


# Same operation resent while this Runtime still runs it: wait for its result (06 line 134).
async def test_resend_during_the_operation_waits_for_its_result(runtime: RuntimeClient) -> None:
    import asyncio

    from rag_engine.adapters.index_store import IndexDefinition, InMemoryIndexStore

    class SlowCreateStore(InMemoryIndexStore):
        def __init__(self) -> None:
            super().__init__()
            self.entered, self.release = asyncio.Event(), asyncio.Event()

        async def create_index(self, definition: IndexDefinition) -> None:
            self.entered.set()
            await self.release.wait()
            await super().create_index(definition)

    store = SlowCreateStore()
    runtime.app.state.stores._memory = store
    catalog = await runtime.catalog()
    empty = {"expected_active_revision": None, "expected_index_generation": None, "expected_index_fingerprint": None}
    planned = await preview(runtime, scenario_config(), operation="initialize", **empty)
    request = {
        **planned["request"],
        "runtime_ref": catalog["runtime_ref"],
        "context_revision": planned["validation"]["context_revision"],
        "config_revision": "revision-1",
        "target_index_generation": str(uuid.uuid4()),
    }
    first = asyncio.create_task(put(runtime, request, "init-slow"))
    await asyncio.wait_for(store.entered.wait(), 5)
    resend = asyncio.create_task(put(runtime, request, "init-slow"))
    other = await put(runtime, {**request, "config_revision": "revision-x"}, "init-other")
    assert other.status_code == 409 and other.json()["error"]["code"] == "SYSTEM_BUSY"  # a different operation
    store.release.set()
    original, repeated = await first, await resend
    assert original.status_code == repeated.status_code == 200, repeated.text
    assert original.json() == repeated.json()


# detach / DELETE: queued or running Ingestion or Retire work answers 409 SYSTEM_BUSY; Retire of
# a document still being ingested answers 409 DOCUMENT_BUSY; a resent detach answers 204.
async def test_work_in_progress_blocks_detach_delete_and_retire(runtime: RuntimeClient) -> None:
    import asyncio

    from rag_engine.engine.pipelines import EngineDeps
    from test_ingestion_control import GatedEmbedder, doc

    registry = runtime.app.state.registry
    embedder = GatedEmbedder()
    hold = asyncio.Event()
    embedder.gates["HOLD"] = hold
    registry.deps = EngineDeps(embedder=embedder, http=registry.deps.http)
    published = await runtime.initialize()
    accepted = await runtime.ingest([doc("busy-doc", "HOLD text")])
    headers = {**basic(MANAGEMENT), **binding(published)}

    detached = await runtime.http.post(f"{SYSTEM_PATH}:detach", headers={**headers, "Idempotency-Key": "d-1"})
    assert detached.status_code == 409 and detached.json()["error"]["code"] == "SYSTEM_BUSY"
    deleted = await runtime.http.delete(SYSTEM_PATH, headers={**headers, "Idempotency-Key": "del-1"})
    assert deleted.status_code == 409 and deleted.json()["error"]["code"] == "SYSTEM_BUSY"
    retired = await runtime.http.post(f"{runtime.business}/documents/busy-doc:retire", headers=basic(INGESTION))
    assert retired.status_code == 409 and retired.json()["error"]["code"] == "DOCUMENT_BUSY"
    status = (await runtime.http.get(SYSTEM_PATH, headers=basic(MANAGEMENT))).json()
    assert status["busy"] is True and status["can_ingest"] and status["can_query"]  # refusals reopened nothing

    hold.set()
    await runtime.wait_run(accepted.json()["run_id"], {"completed"})
    first = await runtime.http.post(
        f"{SYSTEM_PATH}:detach?pipeline=ingestion", headers={**headers, "Idempotency-Key": "d-2"}
    )
    again = await runtime.http.post(
        f"{SYSTEM_PATH}:detach?pipeline=ingestion", headers={**headers, "Idempotency-Key": "d-2"}
    )
    assert first.status_code == again.status_code == 204


# detach of Inference waits for accepted queries up to the query deadline; on timeout it answers
# 504 DEADLINE_EXCEEDED and the entry opens again.
async def test_detach_inference_times_out_and_reopens(runtime: RuntimeClient) -> None:
    import asyncio

    from rag_engine.engine.pipelines import EngineDeps
    from test_ingestion_control import GatedEmbedder, _until

    registry = runtime.app.state.registry
    embedder = GatedEmbedder()
    hold = asyncio.Event()
    embedder.gates["HOLD"] = hold
    registry.deps = EngineDeps(embedder=embedder, http=registry.deps.http)
    published = await runtime.initialize()
    query = asyncio.create_task(runtime.query({"query": "HOLD"}))

    async def running() -> bool:
        return bool(runtime.app.state.queries.active(SYSTEM_ID) == 1)

    await _until(running)
    registry.settings = registry.settings.model_copy(update={"inference_timeout_seconds": 0.1})
    detached = await runtime.http.post(
        f"{SYSTEM_PATH}:detach?pipeline=inference",
        headers={**basic(MANAGEMENT), "Idempotency-Key": "d-timeout", **binding(published)},
    )
    assert detached.status_code == 504 and detached.json()["error"]["code"] == "DEADLINE_EXCEEDED"
    status = (await runtime.http.get(SYSTEM_PATH, headers=basic(MANAGEMENT))).json()
    assert status["pipelines"]["inference"]["ready"] is True and status["can_query"]
    hold.set()
    assert (await query).status_code == 200


# C update: a query already running keeps the old version to the end.
async def test_running_query_keeps_the_old_version(runtime: RuntimeClient) -> None:
    import asyncio

    from rag_engine.engine.pipelines import EngineDeps
    from test_ingestion_control import GatedEmbedder, _until

    registry = runtime.app.state.registry
    embedder = GatedEmbedder()
    hold = asyncio.Event()
    embedder.gates["HOLD"] = hold
    registry.deps = EngineDeps(embedder=embedder, http=registry.deps.http)
    published = await runtime.initialize()
    query = asyncio.create_task(runtime.query({"query": "HOLD"}))

    async def running() -> bool:
        return bool(runtime.app.state.queries.active(SYSTEM_ID) == 1)

    await _until(running)
    query_only = scenario_config()
    query_only["pipelines"]["inference"]["retrieval"]["parameters"]["top_n"] = 1
    _, updated = await apply_after_preview(runtime, query_only, "update-1", "revision-2", **update_body(published))
    assert updated.status_code == 200, updated.text
    hold.set()
    old = await query
    assert old.status_code == 200 and old.json()["config_revision"] == "revision-1"
    assert (await runtime.query({"query": "新查詢"})).json()["config_revision"] == "revision-2"
