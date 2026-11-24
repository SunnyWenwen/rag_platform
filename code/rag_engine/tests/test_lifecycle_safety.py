"""Lifecycle safety: entry closing during detach, mapping changes, rebuild recovery, unverifiable
bindings and the preview context (rag_platform 06#system-lifecycle-api)."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

from conftest import INGESTION, MANAGEMENT, SYSTEM_ID, RuntimeClient, basic, scenario_config
from rag_engine.adapters.index_store import IndexDefinition, IndexStateUnknown, InMemoryIndexStore
from rag_engine.engine.pipelines import EngineDeps
from test_ingestion_control import GatedEmbedder, _until, doc

SYSTEM_PATH = f"/internal/v1/systems/{SYSTEM_ID}"


async def preview(runtime: RuntimeClient, config: dict[str, Any], **body: Any) -> dict[str, Any]:
    catalog = await runtime.catalog()
    request = {
        "runtime_ref": catalog["runtime_ref"],
        "catalog_revision": catalog["catalog_revision"],
        "draft_revision": "draft-2",
        "config": config,
        **body,
    }
    response = await runtime.http.post(f"{SYSTEM_PATH}/config:validate", json=request, headers=basic(MANAGEMENT))
    assert response.status_code == 200, response.text
    return {"request": request, "validation": response.json()}


def update_body(published: dict[str, Any]) -> dict[str, Any]:
    return {
        "operation": "update",
        "expected_active_revision": "revision-1",
        "expected_index_generation": published["status"]["index_generation"],
        "expected_index_fingerprint": published["fingerprint"],
    }


def binding(published: dict[str, Any], revision: str = "revision-1") -> dict[str, str]:
    return {
        "X-Expected-Config-Revision": revision,
        "X-Expected-Index-Generation": published["status"]["index_generation"],
        "X-Expected-Index-Fingerprint": published["fingerprint"],
    }


# ---------------------------------------------------------------- 1. detach closes the entry first


async def test_upload_read_during_detach_is_refused(runtime: RuntimeClient) -> None:
    published = await runtime.initialize()
    released = asyncio.Event()

    async def slow_body() -> AsyncIterator[bytes]:
        yield b'{"documents": '
        await released.wait()
        yield json.dumps([doc("late", "text")]).encode() + b"}"

    upload = asyncio.create_task(
        runtime.http.post(
            f"{runtime.business}/ingestions",
            content=slow_body(),
            headers={**basic(INGESTION), "Content-Type": "application/json"},
        )
    )
    await asyncio.sleep(0.05)  # the handler passed the entry check and waits for the body
    detached = await runtime.http.post(
        f"{SYSTEM_PATH}:detach?pipeline=ingestion",
        headers={**basic(MANAGEMENT), "Idempotency-Key": "detach-1", **binding(published)},
    )
    assert detached.status_code == 204, detached.text
    released.set()
    late = await upload
    assert late.status_code == 409 and late.json()["error"]["code"] == "PIPELINE_NOT_ENABLED", late.text
    assert not runtime.app.state.ingestion.has_active_work(SYSTEM_ID)


async def test_detaching_both_pipelines_closes_ingestion_while_queries_drain(runtime: RuntimeClient) -> None:
    registry = runtime.app.state.registry
    embedder = GatedEmbedder()
    hold = asyncio.Event()
    embedder.gates["HOLD"] = hold
    registry.deps = EngineDeps(embedder=embedder, http=registry.deps.http)
    published = await runtime.initialize()

    query = asyncio.create_task(runtime.query({"query": "HOLD 問題"}))

    async def query_running() -> bool:
        return bool(runtime.app.state.queries.active(SYSTEM_ID) == 1)

    await _until(query_running)
    detach = asyncio.create_task(
        runtime.http.post(
            f"{SYSTEM_PATH}:detach", headers={**basic(MANAGEMENT), "Idempotency-Key": "detach-2", **binding(published)}
        )
    )
    await asyncio.sleep(0.05)  # detach waits for the running query
    refused = await runtime.ingest([doc("new", "text")])
    assert refused.status_code == 503 and refused.json()["error"]["code"] == "PIPELINE_NOT_READY", refused.text
    hold.set()
    assert (await query).status_code == 200
    assert (await detach).status_code == 204
    assert not runtime.app.state.ingestion.has_active_work(SYSTEM_ID)


# ---------------------------------------------------------------- 2. legal mapping changes


async def test_mapping_change_previews_as_rebuild_and_tampering_still_blocks(runtime: RuntimeClient) -> None:
    published = await runtime.initialize()
    changed = scenario_config()
    changed["pipelines"]["ingestion"]["import"]["parameters"]["structdata"]["title"]["filterable"] = False
    impact = (await preview(runtime, changed, **update_body(published)))["validation"]["index_impact"]
    assert impact["action"] == "rebuild_required", impact

    # The published index no longer matches the active mapping: still blocked.
    store = runtime.app.state.stores.memory
    name = f"rag-builder-{SYSTEM_ID}-{published['status']['index_generation']}"
    store._indices[name].info.mappings["properties"]["structdata"]["properties"].pop("title")
    for config in (scenario_config(), changed):
        impact = (await preview(runtime, config, **update_body(published)))["validation"]["index_impact"]
        assert impact["action"] == "blocked" and impact["code"] == "INDEX_OWNERSHIP_UNVERIFIED", impact


# ---------------------------------------------------------------- 3. rebuild can be resumed


class FlakyCreateStore(InMemoryIndexStore):
    def __init__(self) -> None:
        super().__init__()
        self.fail_creates = 0
        self.created: list[str] = []

    async def create_index(self, definition: IndexDefinition) -> None:
        if self.fail_creates:
            self.fail_creates -= 1
            raise IndexStateUnknown("index creation timed out")
        self.created.append(definition.name)
        await super().create_index(definition)


async def test_failed_rebuild_reports_not_ready_and_resumes_with_the_same_operation(runtime: RuntimeClient) -> None:
    store = FlakyCreateStore()
    runtime.app.state.stores._memory = store
    published = await runtime.initialize()
    old_name = f"rag-builder-{SYSTEM_ID}-{published['status']['index_generation']}"
    rebuilt = scenario_config()
    rebuilt["pipelines"]["ingestion"]["chunking"]["parameters"]["max_tokens"] = 200
    planned = await preview(runtime, rebuilt, **update_body(published))
    assert planned["validation"]["index_impact"]["action"] == "rebuild_required"
    target = str(uuid.uuid4())
    apply = {
        **planned["request"],
        "context_revision": planned["validation"]["context_revision"],
        "config_revision": "revision-2",
        "target_index_generation": target,
        "allow_rebuild": True,
    }
    store.fail_creates = 1
    failed = await runtime.http.put(
        SYSTEM_PATH, json=apply, headers={**basic(MANAGEMENT), "Idempotency-Key": "rebuild-1"}
    )
    assert failed.status_code == 503 and failed.json()["error"]["code"] == "SYSTEM_STATE_UNKNOWN", failed.text

    status = (await runtime.http.get(SYSTEM_PATH, headers=basic(MANAGEMENT))).json()
    assert status["index_ready"] is False and not status["can_ingest"] and not status["can_query"], status
    assert status["busy"] is True

    # Another operation cannot take over the half-done rebuild.
    other = {**apply, "target_index_generation": str(uuid.uuid4())}
    refused = await runtime.http.put(SYSTEM_PATH, json=other, headers={**basic(MANAGEMENT), "Idempotency-Key": "x-1"})
    assert refused.status_code == 409, refused.text

    resumed = await runtime.http.put(
        SYSTEM_PATH, json=apply, headers={**basic(MANAGEMENT), "Idempotency-Key": "rebuild-1"}
    )
    assert resumed.status_code == 200, resumed.text
    body = resumed.json()
    assert body["index_generation"] == target and body["index_ready"] is True and body["can_ingest"]
    new_name = f"rag-builder-{SYSTEM_ID}-{target}"
    assert store.created == [old_name, new_name]
    assert await store.get_index(old_name) is None and await store.get_index(new_name) is not None


# ---------------------------------------------------------------- 4. Retire with an unconfirmed delete


class UnsureDeleteStore(InMemoryIndexStore):
    def __init__(self) -> None:
        super().__init__()
        self.unsure = True

    async def delete_document(self, name: str, document_id: str) -> int:
        if self.unsure:
            raise IndexStateUnknown("delete_by_query reported failures")
        return await super().delete_document(name, document_id)


async def test_retire_reports_an_unconfirmed_delete(runtime: RuntimeClient) -> None:
    store = UnsureDeleteStore()
    runtime.app.state.stores._memory = store
    await runtime.initialize()
    path = f"{runtime.business}/documents/guide-1:retire"
    unsure = await runtime.http.post(path, headers=basic(INGESTION))
    assert unsure.status_code == 503 and unsure.json()["error"]["code"] == "SYSTEM_STATE_UNKNOWN", unsure.text
    store.unsure = False
    assert (await runtime.http.post(path, headers=basic(INGESTION))).json()["result"] == "not_found"


# ---------------------------------------------------------------- 5. unloaded System on a PLED cluster


async def test_unloaded_system_on_another_cluster_is_not_reported_missing(runtime: RuntimeClient) -> None:
    default_store, pled_store = InMemoryIndexStore(), InMemoryIndexStore()
    stores = runtime.app.state.stores
    stores.default = lambda: default_store
    stores.for_connection = lambda connection: (
        pled_store if connection["service_source"] == "pled_es" else default_store
    )
    stores.pled_configured = lambda: True
    config = scenario_config()
    config["pipelines"]["ingestion"]["indexing"]["parameters"].update(
        service_source="pled_es", es_number="007", account="rag", password="{{PLED_ES_PASSWORD}}"
    )
    config["secret"]["PLED_ES_PASSWORD"] = "es-pass"
    published = await runtime.initialize(config)
    runtime.app.state.registry.systems.clear()  # as after a Runtime restart

    observed = await runtime.http.get(SYSTEM_PATH, headers={**basic(MANAGEMENT), **binding(published)})
    assert observed.status_code == 503 and observed.json()["error"]["code"] == "SYSTEM_STATE_UNKNOWN", observed.text
    deleted = await runtime.http.delete(
        SYSTEM_PATH, headers={**basic(MANAGEMENT), "Idempotency-Key": "delete-1", **binding(published)}
    )
    assert deleted.status_code == 503, deleted.text
    name = f"rag-builder-{SYSTEM_ID}-{published['status']['index_generation']}"
    assert await pled_store.get_index(name) is not None

    # Without PLED clusters the default ES is the only place, so missing means missing.
    stores.pled_configured = lambda: False
    assert (await runtime.http.get(SYSTEM_PATH, headers={**basic(MANAGEMENT), **binding(published)})).status_code == 404


# ---------------------------------------------------------------- 6. the context binds the previewed plan


async def test_context_revision_binds_operation_and_draft(runtime: RuntimeClient) -> None:
    published = await runtime.initialize()
    query_only = scenario_config()
    query_only["pipelines"]["inference"]["retrieval"]["parameters"]["top_n"] = 1

    expected = {key: value for key, value in update_body(published).items() if key != "operation"}
    plain = await preview(runtime, query_only, **expected)  # general validation, no operation
    apply = {
        **plain["request"],
        **update_body(published),
        "context_revision": plain["validation"]["context_revision"],
        "config_revision": "revision-2",
    }
    response = await runtime.http.put(SYSTEM_PATH, json=apply, headers={**basic(MANAGEMENT), "Idempotency-Key": "u-1"})
    assert response.status_code == 409 and response.json()["error"]["code"] == "STALE_CONTEXT", response.text

    planned = await preview(runtime, query_only, **update_body(published))
    apply = {
        **planned["request"],
        "draft_revision": "draft-other",
        "context_revision": planned["validation"]["context_revision"],
        "config_revision": "revision-2",
    }
    response = await runtime.http.put(SYSTEM_PATH, json=apply, headers={**basic(MANAGEMENT), "Idempotency-Key": "u-2"})
    assert response.status_code == 409 and response.json()["error"]["code"] == "STALE_CONTEXT", response.text

    apply["draft_revision"] = "draft-2"
    response = await runtime.http.put(SYSTEM_PATH, json=apply, headers={**basic(MANAGEMENT), "Idempotency-Key": "u-3"})
    assert response.status_code == 200, response.text


# ---------------------------------------------------------------- 7. ES clients follow credentials


async def test_es_clients_follow_password_rotation() -> None:
    from conftest import make_settings
    from rag_engine.runtime.stores import StoreProvider

    provider = StoreProvider(
        make_settings(index_backend="elasticsearch", pled_es_url_template="https://es{es_number}.example:9200")
    )
    connection = {"service_source": "pled_es", "es_number": "007", "account": "rag", "password": "old"}
    first = provider.for_connection(connection)
    assert provider.for_connection(dict(connection)) is first
    rotated = provider.for_connection({**connection, "password": "new"})
    assert rotated is not first
    await provider.close()
