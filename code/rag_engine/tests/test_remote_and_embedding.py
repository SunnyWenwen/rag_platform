"""Remote API adapter, Remote Ingestion through the Runtime, and the OpenAI-compatible embedder."""

from __future__ import annotations

import json
import time

import httpx
import pytest

from conftest import INGESTION, RuntimeClient, basic, scenario_config
from rag_engine.adapters.embedding import OpenAICompatibleEmbedder
from rag_engine.components.remote import RemoteCall, call_remote
from rag_engine.core.errors import UpstreamError
from rag_engine.core.resources import EmbeddingProfile
from rag_engine.engine.pipelines import EngineDeps
from test_engine_units import remote_parsing_config

CALL = RemoteCall("parsing", "parsing", "1", "https://parser.example/v1", 5.0, {"X-Tenant": "t"}, "secret-token")


def client(handler: object) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))  # type: ignore[arg-type]


async def test_remote_call_envelope_and_headers() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"output": [{"document_id": "d"}]})

    async with client(handler) as http:
        output = await call_remote(
            http,
            CALL,
            {"document_id": "d"},
            {"language": "zh-TW"},
            upstream_request_id="req-1",
            deadline=time.monotonic() + 5,
        )
    assert output == [{"document_id": "d"}]
    body = json.loads(seen[0].content)
    assert body == {
        "contract_version": "1",
        "segment": {"module": "parsing", "through": "parsing"},
        "input": {"document_id": "d"},
        "parameters": {"language": "zh-TW"},
    }
    assert seen[0].headers["authorization"] == "Bearer secret-token"
    assert seen[0].headers["x-tenant"] == "t"
    assert seen[0].headers["x-request-id"]


async def test_remote_retries_retryable_errors_with_the_same_request_id() -> None:
    ids: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        ids.append(request.headers["x-request-id"])
        if len(ids) == 1:
            return httpx.Response(503, json={"error": {"code": "BUSY", "message": "busy", "retryable": True}})
        return httpx.Response(200, json={"output": []})

    async with client(handler) as http:
        assert await call_remote(http, CALL, {}, {}, upstream_request_id=None, deadline=time.monotonic() + 5) == []
    assert len(ids) == 2 and ids[0] == ids[1]


async def test_remote_non_retryable_and_invalid_envelopes_fail() -> None:
    calls = 0

    def refuse(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(415, json={"error": {"code": "UNSUPPORTED", "message": "pdf only", "retryable": False}})

    async with client(refuse) as http:
        with pytest.raises(UpstreamError) as raised:
            await call_remote(http, CALL, {}, {}, upstream_request_id=None, deadline=time.monotonic() + 5)
    assert calls == 1 and "UNSUPPORTED" in raised.value.message

    async with client(lambda request: httpx.Response(200, json={"result": []})) as http:
        with pytest.raises(UpstreamError):
            await call_remote(http, CALL, {}, {}, upstream_request_id=None, deadline=time.monotonic() + 5)


async def test_remote_parsing_runs_inside_ingestion(runtime: RuntimeClient) -> None:
    requests: list[dict] = []

    def parser(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        document = dict(body["input"])
        document["structdata"] = {**document["structdata"], "body": document["structdata"]["body"].upper()}
        return httpx.Response(200, json={"output": [document]})

    registry = runtime.app.state.registry
    registry.deps = EngineDeps(embedder=registry.deps.embedder, http=client(parser))
    await runtime.initialize(remote_parsing_config())
    accepted = await runtime.ingest(
        [{"document_id": "doc-1", "structdata": {"body": "abc text", "title": "t", "price": 400}}],
        parameters={"trace_label": "request-label"},
    )
    assert accepted.status_code == 202, accepted.text
    done = await runtime.wait_run(accepted.json()["run_id"], {"completed", "failed"})
    assert done["status"] == "completed", done
    assert requests[0]["parameters"] == {"language": "zh-TW", "trace_label": "request-label"}
    page = await runtime.http.get(f"{runtime.business}/documents", headers=basic(INGESTION))
    assert page.json()["documents"][0]["document_id"] == "doc-1"


async def test_remote_rerank_receives_request_parameters(runtime: RuntimeClient) -> None:
    """Request values bound by the input node must reach later Remote Inference nodes."""
    seen: list[dict] = []

    def reranker(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        contexts = body["input"]
        for context in contexts:
            items = context["result_sets"][0]["items"][: body["parameters"]["limit"]]
            context["result_sets"] = [{"key": "rerank", "items": items}]
        return httpx.Response(200, json={"output": contexts})

    config = scenario_config()
    inference = config["pipelines"]["inference"]
    inference["fixed_filters"] = []
    inference["inference_input"]["parameters"]["request_parameters"] = [
        {"name": "LIMIT", "type": "integer", "required": False, "default_value": "5"}
    ]
    inference["rerank"] = {
        "component_id": "remote_api",
        "component_version": "1.0.0",
        "contract_version": "1",
        "through": "rerank",
        "connection": {"url": "{{REMOTE_RERANK_URL}}", "timeout_seconds": 10},
        "parameters": {"limit": "{{LIMIT}}", "mode": "fast"},
    }
    config["variable"] = {"REMOTE_RERANK_URL": "https://rerank.dev.example/v1/rerank"}
    registry = runtime.app.state.registry
    registry.deps = EngineDeps(embedder=registry.deps.embedder, http=client(reranker))
    await runtime.initialize(config)
    accepted = await runtime.ingest(
        [
            {"document_id": "a", "structdata": {"body": "清潔散熱孔", "title": "t", "price": 1}},
            {"document_id": "b", "structdata": {"body": "更換濾網", "title": "t", "price": 2}},
        ]
    )
    done = await runtime.wait_run(accepted.json()["run_id"], {"completed", "failed"})
    assert done["status"] == "completed", done

    response = await runtime.query({"query": "清潔", "parameters": {"LIMIT": 1}})
    assert response.status_code == 200, response.text
    assert seen[-1]["parameters"] == {"limit": 1, "mode": "fast"}
    assert len(response.json()["contexts"][0]["result_sets"][0]["items"]) == 1
    response = await runtime.query({"query": "清潔"})
    assert response.status_code == 200, response.text
    assert seen[-1]["parameters"] == {"limit": 5, "mode": "fast"}  # declared default


async def test_openai_compatible_embedder_batches_and_validates() -> None:
    profile = EmbeddingProfile(
        "bge-m3", "BGE-M3", 3, "BAAI/bge-m3", "rev", endpoint="http://emb/v1", request_model="BAAI/bge-m3", batch_size=2
    )
    batches: list[list[str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("http://emb/v1/embeddings")
        body = json.loads(request.content)
        assert body["model"] == "BAAI/bge-m3"
        batches.append(body["input"])
        data = [{"index": i, "embedding": [0.1, 0.2, 0.3]} for i in reversed(range(len(body["input"])))]
        return httpx.Response(200, json={"data": data})

    async with client(handler) as http:
        vectors = await OpenAICompatibleEmbedder(http).embed(["a", "b", "c"], profile)
    assert batches == [["a", "b"], ["c"]] and len(vectors) == 3

    async with client(lambda request: httpx.Response(200, json={"data": [{"index": 0, "embedding": [1.0]}]})) as http:
        with pytest.raises(UpstreamError):
            await OpenAICompatibleEmbedder(http).embed(["a"], profile)
