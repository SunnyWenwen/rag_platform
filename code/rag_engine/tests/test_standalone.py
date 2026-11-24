"""FTEST/ENT standalone mode: one System from RAG_CONFIG_FILE, values from env vars, business API at /v1.

The physical index must already exist (Q-021). The tests create it the way a DEV Runtime would,
then start a standalone Runtime on the same in-memory store.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest

from conftest import SYSTEM_ID, basic, make_settings, running, scenario_config, validate_http
from rag_engine.engine.compiler import compile_system
from rag_engine.runtime.app import create_app
from rag_engine.runtime.settings import Settings

GENERATION = "4f0c2a8e-7d51-4f3b-9a64-2b8e5c1d0a77"
REVISION = "revision-7"
INGESTION = ("ingest-user", "ingest-pass")
INFERENCE = ("infer-user", "infer-pass")
ENVIRONMENT = {
    "PLED_ES_NUMBER": "007",
    "PLED_ES_ACCOUNT": "rag-ftest",
    "PLED_ES_PASSWORD": "es-pass",
    "INGESTION_API_USERNAME": INGESTION[0],
    "INGESTION_API_PASSWORD": INGESTION[1],
    "INFERENCE_API_USERNAME": INFERENCE[0],
    "INFERENCE_API_PASSWORD": INFERENCE[1],
}
DOCS = [
    {"document_id": "guide-1", "structdata": {"body": "定期清潔散熱孔。", "title": "設備保養", "price": 350}},
]


@pytest.fixture(autouse=True)
def system_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """Standalone Runtimes read Secret and Variable values from same-named environment variables."""
    for key, value in ENVIRONMENT.items():
        monkeypatch.setenv(key, value)


def standalone_settings(tmp_path: Path, **overrides: Any) -> Settings:
    # Export form (05#elasticsearch-service-source): dev_test becomes pled_es with Secret references,
    # and every Secret keeps its key with a null value. Values come from the environment.
    config = scenario_config()
    config["pipelines"]["ingestion"]["indexing"]["parameters"].update(
        service_source="pled_es",
        es_number="{{PLED_ES_NUMBER}}",
        account="{{PLED_ES_ACCOUNT}}",
        password="{{PLED_ES_PASSWORD}}",
    )
    config["secret"] = {
        key: None for key in [*config["secret"], "PLED_ES_NUMBER", "PLED_ES_ACCOUNT", "PLED_ES_PASSWORD"]
    }
    path = tmp_path / "system.json"
    path.write_text(json.dumps({"system_id": SYSTEM_ID, "config_revision": REVISION, "config": config}))
    values: dict[str, Any] = {
        "mode": "standalone",
        "env": "ftest",
        "config_file": str(path),
        "index_generation": GENERATION,
    }
    values.update(overrides)
    return make_settings(**values)


def read_system_file(path: str) -> dict[str, Any]:
    return dict(json.loads(Path(path).read_text()))


async def create_index(app: Any) -> None:
    """Create the index the standalone Runtime will bind, as a DEV Runtime would have."""
    registry = app.state.registry
    body = read_system_file(registry.settings.config_file)
    compiled = compile_system(body["config"], registry.catalog, environment=ENVIRONMENT)
    snapshot = registry._build(SYSTEM_ID, REVISION, compiled, GENERATION)
    await registry._create_index(snapshot, "op-initialize")


@contextlib.asynccontextmanager
async def standalone(settings: Settings, with_index: bool = True) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(settings)
    if with_index:
        await create_index(app)
    async with running(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://runtime") as client:
            yield client


async def wait_run(client: httpx.AsyncClient, run_id: str) -> dict[str, Any]:
    async with asyncio.timeout(5):
        while True:
            response = await client.get(f"/v1/ingestions/{run_id}", headers=basic(INGESTION))
            body = response.json()
            if body["status"] in ("completed", "partial", "failed"):
                return body
            await asyncio.sleep(0.01)


async def test_standalone_serves_one_system_under_v1(tmp_path: Path) -> None:
    async with standalone(standalone_settings(tmp_path)) as client:
        ready = await client.get("/health/ready")
        assert ready.status_code == 200
        # No DEV management API in standalone mode.
        assert (await client.get("/internal/v1/catalog", headers=basic(("mock", "mock")))).status_code == 404

        accepted = await client.post("/v1/ingestions", json={"documents": DOCS}, headers=basic(INGESTION))
        assert accepted.status_code == 202, accepted.text
        run_id = accepted.json()["run_id"]
        assert accepted.headers["location"] == f"/v1/ingestions/{run_id}"
        done = await wait_run(client, run_id)
        validate_http("ingestion_run_status", done)
        assert done["status"] == "completed", done

        query = await client.post("/v1/queries", json={"query": "散熱孔"}, headers=basic(INFERENCE))
        assert query.status_code == 200, query.text
        body = query.json()
        validate_http("inference_response", body)
        assert body["config_revision"] == REVISION and body["index_generation"] == GENERATION
        assert [item["data"]["document_id"] for item in body["contexts"][0]["result_sets"][0]["items"]] == ["guide-1"]

        # Each pipeline accepts only its own credentials from the environment.
        wrong = await client.post("/v1/queries", json={"query": "x"}, headers=basic(INGESTION))
        assert wrong.status_code == 401
        assert (await client.post("/mcp", json={})).status_code == 401


async def test_standalone_can_serve_a_single_pipeline(tmp_path: Path) -> None:
    async with standalone(standalone_settings(tmp_path, pipeline="inference")) as client:
        blocked = await client.post("/v1/ingestions", json={"documents": DOCS}, headers=basic(INGESTION))
        assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "PIPELINE_NOT_ENABLED"
        query = await client.post("/v1/queries", json={"query": "x"}, headers=basic(INFERENCE))
        assert query.status_code == 200, query.text


async def test_standalone_is_not_ready_without_its_index(tmp_path: Path) -> None:
    async with standalone(standalone_settings(tmp_path), with_index=False) as client:
        ready = await client.get("/health/ready")
        assert ready.status_code == 503 and ready.json()["error"]["code"] == "RUNTIME_NOT_READY"
        query = await client.post("/v1/queries", json={"query": "x"}, headers=basic(INFERENCE))
        assert query.json()["error"]["code"] == "INDEX_NOT_READY"


async def test_standalone_startup_rejects_missing_values_and_wrong_fingerprint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = create_app(standalone_settings(tmp_path, index_fingerprint="0" * 64))
    with pytest.raises(RuntimeError, match="RAG_INDEX_FINGERPRINT"):
        async with app.router.lifespan_context(app):
            pass

    app = create_app(standalone_settings(tmp_path, index_generation="gen-0001"))
    with pytest.raises(RuntimeError, match="RAG_INDEX_GENERATION"):
        async with app.router.lifespan_context(app):
            pass

    monkeypatch.delenv("INFERENCE_API_PASSWORD")
    app = create_app(standalone_settings(tmp_path))
    with pytest.raises(RuntimeError, match="INFERENCE_API_PASSWORD"):
        async with app.router.lifespan_context(app):
            pass
