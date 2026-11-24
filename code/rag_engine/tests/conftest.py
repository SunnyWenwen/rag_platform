"""Shared fixtures: a DEV Runtime on the in-memory index store with the hash embedder."""

from __future__ import annotations

import asyncio
import base64
import contextlib
import copy
import json
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest

from rag_engine.contracts import check, http_def, schema_ref
from rag_engine.runtime.app import create_app
from rag_engine.runtime.settings import Settings

FIXTURES = Path(__file__).parent / "fixtures"
SYSTEM_ID = "7b38858b-6f26-4647-9dfb-84044000413a"
MANAGEMENT = ("mock", "mock")
INGESTION = ("ingestion", "mock-ingestion")
INFERENCE = ("inference", "mock-inference")


def basic(credentials: tuple[str, str]) -> dict[str, str]:
    token = base64.b64encode(":".join(credentials).encode()).decode()
    return {"Authorization": f"Basic {token}"}


def scenario_config() -> dict[str, Any]:
    """The System Config of the rag_platform ``happy_path`` scenario."""
    data = json.loads((FIXTURES / "runtime_http.examples.json").read_text())
    put = next(step for step in data["scenarios"]["happy_path"] if step["request"]["method"] == "PUT")
    return copy.deepcopy(put["request"]["body"]["config"])


def validate_http(name: str, body: Any) -> None:
    check(http_def(name), body)


def validate_schema(file_name: str, body: Any) -> None:
    check(schema_ref(file_name), body)


def make_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "management_username": MANAGEMENT[0],
        "management_password": MANAGEMENT[1],
        "embedding_backend": "hash",
        "index_backend": "memory",
        "status_cleanup_interval_seconds": 3600,
    }
    values.update(overrides)
    return Settings(**values)


class RuntimeClient:
    """Thin helper around an in-process Runtime with typed calls used by the tests."""

    def __init__(self, client: httpx.AsyncClient, app: Any) -> None:
        self.http = client
        self.app = app
        self.system_id = SYSTEM_ID
        self.business = f"/internal/systems/{SYSTEM_ID}/v1"

    async def catalog(self) -> dict[str, Any]:
        response = await self.http.get("/internal/v1/catalog", headers=basic(MANAGEMENT))
        assert response.status_code == 200, response.text
        return response.json()

    async def initialize(self, config: dict[str, Any] | None = None) -> dict[str, Any]:
        catalog = await self.catalog()
        body = {
            "runtime_ref": catalog["runtime_ref"],
            "catalog_revision": catalog["catalog_revision"],
            "draft_revision": "draft-1",
            "config": config or scenario_config(),
            "operation": "initialize",
            "expected_active_revision": None,
            "expected_index_generation": None,
            "expected_index_fingerprint": None,
        }
        preview = await self.http.post(
            f"/internal/v1/systems/{SYSTEM_ID}/config:validate", json=body, headers=basic(MANAGEMENT)
        )
        assert preview.status_code == 200, preview.text
        validation = preview.json()
        validate_http("validation", validation)
        assert validation["index_impact"]["action"] == "create"
        apply = {
            **body,
            "context_revision": validation["context_revision"],
            "config_revision": "revision-1",
            "target_index_generation": str(uuid.uuid4()),
        }
        response = await self.http.put(
            f"/internal/v1/systems/{SYSTEM_ID}",
            json=apply,
            headers={**basic(MANAGEMENT), "Idempotency-Key": "initialize-001"},
        )
        assert response.status_code == 200, response.text
        status = response.json()
        validate_http("system_status", status)
        return {"status": status, "apply": apply, "fingerprint": validation["index_impact"]["index_fingerprint"]}

    async def ingest(self, documents: list[dict[str, Any]], **extra: Any) -> httpx.Response:
        return await self.http.post(
            f"{self.business}/ingestions", json={"documents": documents, **extra}, headers=basic(INGESTION)
        )

    async def run(self, run_id: str) -> dict[str, Any]:
        response = await self.http.get(f"{self.business}/ingestions/{run_id}", headers=basic(INGESTION))
        assert response.status_code == 200, response.text
        body = response.json()
        validate_http("ingestion_run_status", body)
        return body

    async def wait_run(self, run_id: str, until: set[str], timeout: float = 5.0) -> dict[str, Any]:
        async with asyncio.timeout(timeout):
            while True:
                body = await self.run(run_id)
                if body["status"] in until:
                    return body
                await asyncio.sleep(0.01)

    async def query(self, body: dict[str, Any]) -> httpx.Response:
        return await self.http.post(f"{self.business}/queries", json=body, headers=basic(INFERENCE))


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@contextlib.asynccontextmanager
async def running(app: Any) -> AsyncIterator[None]:
    """Run the app lifespan in its own task: the MCP SDK's task group must exit where it entered."""
    started, stop = asyncio.Event(), asyncio.Event()

    async def serve() -> None:
        async with app.router.lifespan_context(app):
            started.set()
            await stop.wait()

    task = asyncio.create_task(serve())
    waiter = asyncio.create_task(started.wait())
    await asyncio.wait({task, waiter}, return_when=asyncio.FIRST_COMPLETED)
    if not started.is_set():  # startup failed: raise its error instead of waiting forever
        waiter.cancel()
        await task
    try:
        yield
    finally:
        stop.set()
        await task


@pytest.fixture
async def runtime(settings: Settings) -> AsyncIterator[RuntimeClient]:
    app = create_app(settings)
    async with running(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://runtime") as client:
            yield RuntimeClient(client, app)
