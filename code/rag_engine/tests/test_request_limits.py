"""Query limits of rag_platform 06#inference-api (D-64): reject at once, no waiting queue.

Per-System rate and concurrency answer 429 RATE_LIMITED with Retry-After; the Runtime-wide
concurrency answers 503 RUNTIME_CAPACITY_EXHAUSTED.
"""

from __future__ import annotations

import asyncio

import pytest

from conftest import RuntimeClient, make_settings
from rag_engine.engine.pipelines import EngineDeps
from rag_engine.runtime.errors import ApiError
from rag_engine.runtime.inference import QueryService
from test_ingestion_control import GatedEmbedder, _until


@pytest.mark.parametrize("settings", [make_settings(inference_rate_limit_per_system_rps=1)])
async def test_per_system_rate_limit(runtime: RuntimeClient) -> None:
    await runtime.initialize()
    assert (await runtime.query({"query": "第一次"})).status_code == 200
    limited = await runtime.query({"query": "馬上第二次"})
    assert limited.status_code == 429 and limited.json()["error"]["code"] == "RATE_LIMITED"
    assert limited.headers["retry-after"] == "1"


@pytest.mark.parametrize(
    "settings", [make_settings(inference_rate_limit_per_system_rps=100, inference_max_concurrency_per_system=1)]
)
async def test_per_system_concurrency_rejects_at_once(runtime: RuntimeClient) -> None:
    registry = runtime.app.state.registry
    embedder = GatedEmbedder()
    hold = asyncio.Event()
    embedder.gates["HOLD"] = hold
    registry.deps = EngineDeps(embedder=embedder, http=registry.deps.http)
    await runtime.initialize()
    running = asyncio.create_task(runtime.query({"query": "HOLD"}))

    async def one_running() -> bool:
        return bool(runtime.app.state.queries.active(runtime.system_id) == 1)

    await _until(one_running)
    busy = await runtime.query({"query": "第二個"})
    assert busy.status_code == 429 and busy.json()["error"]["code"] == "RATE_LIMITED"
    hold.set()
    assert (await running).status_code == 200


def test_runtime_wide_concurrency_is_503() -> None:
    service = QueryService(make_settings(inference_max_concurrency_per_system=1, inference_max_concurrency_total=1), {})
    service._enter("system-a")
    with pytest.raises(ApiError) as raised:
        service._enter("system-b")
    assert raised.value.code == "RUNTIME_CAPACITY_EXHAUSTED" and raised.value.status == 503


@pytest.mark.parametrize("settings", [make_settings(inference_timeout_seconds=0.2)])
async def test_query_deadline(runtime: RuntimeClient) -> None:
    registry = runtime.app.state.registry
    embedder = GatedEmbedder()
    embedder.gates["HOLD"] = asyncio.Event()  # never released
    registry.deps = EngineDeps(embedder=embedder, http=registry.deps.http)
    await runtime.initialize()
    late = await runtime.query({"query": "HOLD"})
    assert late.status_code == 504 and late.json()["error"]["code"] == "DEADLINE_EXCEEDED"
    assert runtime.app.state.queries.active(runtime.system_id) == 0  # the slot is returned
