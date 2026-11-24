"""Rewrite Query Transformation (rag_platform 03#rewrite-rules) with a fake LLM service."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from conftest import RuntimeClient, scenario_config, validate_http
from rag_engine.components.rewrite import final_queries, parse_rewrites, render_prompt, rewrite_queries
from rag_engine.core.errors import ConfigInvalid, RequestInvalid, UpstreamError
from rag_engine.core.resources import ModelResource, fixture_resources
from rag_engine.engine.catalog import build_catalog
from rag_engine.engine.compiler import compile_system
from rag_engine.engine.pipelines import EngineDeps

LLM_URL = "http://llm.fixture.invalid/v1/chat/completions"
MODEL = ModelResource("default-llm", "DEV LLM", endpoint="http://llm.fixture.invalid/v1", request_model="chat-model")


def chat(content: Any = None, *, refusal: str | None = None, finish_reason: str = "stop") -> httpx.Response:
    text = content if isinstance(content, str) or content is None else json.dumps(content, ensure_ascii=False)
    message = {"role": "assistant", "content": None if refusal else text, "refusal": refusal}
    return httpx.Response(200, json={"choices": [{"message": message, "finish_reason": finish_reason}]})


def llm(*replies: Callable[[], httpx.Response] | httpx.Response) -> tuple[httpx.AsyncClient, list[dict[str, Any]]]:
    """A client whose LLM answers with ``replies`` in order; it records each request body."""
    calls: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append({"body": json.loads(request.content), "headers": dict(request.headers)})
        reply = replies[min(len(calls), len(replies)) - 1]
        return reply() if callable(reply) else reply

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), calls


async def run(client: httpx.AsyncClient, count: int = 2, include_original: bool = True, **kwargs: Any) -> list[str]:
    deadline = kwargs.pop("deadline", time.monotonic() + 30)
    model = kwargs.pop("model", MODEL)
    async with client:
        return await rewrite_queries(
            client, model, "改寫：散熱孔", "散熱孔怎麼清潔？", count, include_original, deadline
        )


# ---------------------------------------------------------------- answer rules


def test_parse_rewrites_enforces_the_format() -> None:
    assert parse_rewrites('{"queries": [" 清潔散熱孔 ", "散熱孔保養"]}', 2) == ["清潔散熱孔", "散熱孔保養"]
    for bad in (
        "not json",
        '["a", "b"]',
        '{"queries": ["a"]}',  # fewer than count
        '{"queries": ["a", "b", "c"]}',  # more than count
        '{"queries": ["a", "  "]}',  # empty after trimming
        '{"queries": ["a", " a"]}',  # duplicate after trimming
        '{"queries": ["a", 1]}',
        '{"queries": ["a", "b"], "note": "x"}',  # extra key
        None,
    ):
        assert parse_rewrites(bad, 2) is None, bad


def test_final_queries_put_the_original_first_and_drop_exact_duplicates() -> None:
    assert final_queries("原問題", ["改寫一", "原問題"], include_original=True) == ["原問題", "改寫一"]
    assert final_queries("原問題", ["原問題", "改寫一"], include_original=False) == ["原問題", "改寫一"]
    assert final_queries("原問題", None, include_original=False) == ["原問題"]  # the fallback


def test_render_prompt_fills_builtins_then_request_then_variable() -> None:
    template = "為 {{query}} 產生 {{count}} 筆，語言 {{LANG}}，標籤 {{TAGS}}，區域 {{ REGION }}"
    text = render_prompt(template, "散熱孔", 2, {"LANG": "zh-TW", "TAGS": ["a", "b"]}, {"LANG": "en", "REGION": "tw"})
    assert text == '為 散熱孔 產生 2 筆，語言 zh-TW，標籤 ["a", "b"]，區域 tw'
    with pytest.raises(RequestInvalid) as raised:
        render_prompt("{{MISSING}}", "q", 1, {}, {})
    assert raised.value.path == "/parameters/MISSING"


# ---------------------------------------------------------------- calls, retry and fallback


async def test_request_shape_and_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAG_LLM_API_KEY", "llm-token")
    model = ModelResource("m", "M", endpoint="http://llm.fixture.invalid/v1", api_key_env="RAG_LLM_API_KEY")
    client, calls = llm(chat({"queries": ["清潔散熱孔", "散熱孔保養"]}))
    assert await run(client, model=model) == ["散熱孔怎麼清潔？", "清潔散熱孔", "散熱孔保養"]
    body = calls[0]["body"]
    assert body["model"] == "m" and body["temperature"] == 0
    assert [message["role"] for message in body["messages"]] == ["system", "user"]
    assert body["messages"][1]["content"] == "改寫：散熱孔"
    schema = body["response_format"]["json_schema"]
    assert body["response_format"]["type"] == "json_schema" and schema["strict"] is True
    assert (
        schema["schema"]["properties"]["queries"]["minItems"]
        == 2
        == schema["schema"]["properties"]["queries"]["maxItems"]
    )
    assert calls[0]["headers"]["authorization"] == "Bearer llm-token"


async def test_format_error_is_retried_once() -> None:
    client, calls = llm(chat({"queries": ["只有一筆"]}), chat({"queries": ["甲", "乙"]}))
    assert await run(client, include_original=False) == ["甲", "乙"]
    assert len(calls) == 2


async def test_still_invalid_after_retry_falls_back_to_the_original(caplog: pytest.LogCaptureFixture) -> None:
    client, calls = llm(chat("not json"), chat({"queries": ["重複", "重複"]}))
    assert await run(client, include_original=False) == ["散熱孔怎麼清潔？"]
    assert len(calls) == 2
    assert "rewrite fell back to the original query" in caplog.text


async def test_refusal_and_truncation_fall_back_without_retry() -> None:
    client, calls = llm(chat(refusal="I can't help with that."))
    assert await run(client) == ["散熱孔怎麼清潔？"] and len(calls) == 1
    client, calls = llm(chat('{"queries": ["甲", "', finish_reason="length"))
    assert await run(client) == ["散熱孔怎麼清潔？"] and len(calls) == 1


async def test_service_errors_retry_once_then_fail() -> None:
    client, calls = llm(httpx.Response(503), chat({"queries": ["甲", "乙"]}))
    assert await run(client, include_original=False) == ["甲", "乙"] and len(calls) == 2

    client, calls = llm(httpx.Response(503))
    with pytest.raises(UpstreamError) as raised:
        await run(client)
    assert raised.value.code == "UPSTREAM_ERROR" and raised.value.module == "query_transformation" and len(calls) == 2

    client, calls = llm(httpx.Response(400))
    with pytest.raises(UpstreamError):
        await run(client)
    assert len(calls) == 1  # 4xx other than 429 is not retried


async def test_timeouts_end_as_deadline_exceeded() -> None:
    def timeout() -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    client, calls = llm(timeout)
    with pytest.raises(UpstreamError) as raised:
        await run(client)
    assert raised.value.code == "DEADLINE_EXCEEDED" and len(calls) == 2

    client, calls = llm(chat({"queries": ["甲", "乙"]}))
    with pytest.raises(UpstreamError) as raised:
        await run(client, deadline=time.monotonic() - 1)
    assert raised.value.code == "DEADLINE_EXCEEDED" and calls == []


# ---------------------------------------------------------------- Config


def rewrite_config(**parameters: Any) -> dict[str, Any]:
    config = scenario_config()
    inference = config["pipelines"]["inference"]
    inference["fixed_filters"] = []
    inference["query_transformation"] = {
        "component_id": "rewrite",
        "component_version": "1.0.0",
        "parameters": {
            "llm_ref": "default-llm",
            "prompt": "為 {{query}} 產生 {{count}} 個檢索問題。",
            "count": 2,
            "include_original": True,
            **parameters,
        },
    }
    return config


@pytest.mark.parametrize(
    ("parameters", "location"),
    [
        ({"llm_ref": "unknown-llm"}, "llm_ref"),
        ({"llm_ref": "{{MODEL}}"}, "llm_ref"),  # a fixed choice, not a reference
        ({"prompt": "語言 {{LANG}}：{{query}}"}, "prompt"),  # LANG is not declared
        ({"cross_query_group_by": ["price"]}, "cross_query_group_by/0"),  # not a string field
    ],
)
def test_rewrite_config_errors_are_located(parameters: dict[str, Any], location: str) -> None:
    config = rewrite_config(**parameters)
    config["variable"] = {"MODEL": "default-llm"}
    with pytest.raises(ConfigInvalid) as raised:
        compile_system(config, build_catalog("dev-runtime", fixture_resources()))
    assert raised.value.path == f"/config/pipelines/inference/query_transformation/parameters/{location}"


def test_rewrite_parameters_may_reference_request_values() -> None:
    config = rewrite_config(count="{{N}}", prompt="{{query}}，語言 {{LANG}}")
    config["pipelines"]["inference"]["inference_input"]["parameters"]["request_parameters"] = [
        {"name": "N", "type": "integer", "required": False, "default_value": "3"}
    ]
    config["variable"] = {"LANG": "zh-TW"}
    compiled = compile_system(config, build_catalog("dev-runtime", fixture_resources()))
    assert compiled.inference.references["query_transformation"].references == {"count": "N"}


# ---------------------------------------------------------------- over HTTP

DOCS = [
    {"document_id": "a", "structdata": {"body": "定期清潔散熱孔。", "title": "保養", "price": 1}},
    {"document_id": "b", "structdata": {"body": "更換濾網。", "title": "保養", "price": 2}},
    {"document_id": "c", "structdata": {"body": "檢查風扇。", "title": "檢查", "price": 3}},
]


async def publish(
    runtime: RuntimeClient, config: dict[str, Any], handler: Callable[[httpx.Request], httpx.Response]
) -> None:
    registry = runtime.app.state.registry
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    registry.deps = EngineDeps(embedder=registry.deps.embedder, http=client)
    await runtime.initialize(config)
    accepted = await runtime.ingest(DOCS)
    done = await runtime.wait_run(accepted.json()["run_id"], {"completed", "partial", "failed"})
    assert done["status"] == "completed", done


async def test_rewrite_over_http_merges_queries(runtime: RuntimeClient) -> None:
    await publish(runtime, rewrite_config(cross_query_top_n=2), lambda request: chat({"queries": ["清潔", "保養"]}))
    response = await runtime.query({"query": "散熱孔怎麼清潔？"})
    assert response.status_code == 200, response.text
    body = response.json()
    validate_http("inference_response", body)
    assert body["query_variants"] == ["散熱孔怎麼清潔？", "清潔", "保養"]
    assert len(body["contexts"]) == 1 and len(body["contexts"][0]["result_sets"][0]["items"]) == 2


async def test_rewrite_over_http_falls_back_or_fails(runtime: RuntimeClient) -> None:
    replies = iter([chat("not json"), chat("still not json"), httpx.Response(503), httpx.Response(503)])
    await publish(runtime, rewrite_config(), lambda request: next(replies))
    fallback = await runtime.query({"query": "散熱孔怎麼清潔？"})
    assert fallback.status_code == 200, fallback.text
    assert fallback.json()["query_variants"] == ["散熱孔怎麼清潔？"]

    failed = await runtime.query({"query": "散熱孔怎麼清潔？"})
    assert failed.status_code == 502
    validate_http("error_response", failed.json())
    assert failed.json()["error"]["code"] == "UPSTREAM_ERROR"
    assert failed.json()["error"]["module"] == "query_transformation"


@pytest.mark.parametrize(("cross_query_at", "contexts_at_rerank"), [("after_retrieval", 1), ("after_rerank", 3)])
async def test_cross_query_merge_point_with_a_remote_rerank(
    runtime: RuntimeClient, cross_query_at: str, contexts_at_rerank: int
) -> None:
    reranked: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url == httpx.URL(LLM_URL):
            return chat({"queries": ["清潔", "保養"]})
        contexts = json.loads(request.content)["input"]
        reranked.append(len(contexts))
        for context in contexts:
            context["result_sets"] = [{"key": "rerank", "items": context["result_sets"][0]["items"][:2]}]
        return httpx.Response(200, json={"output": contexts})

    config = rewrite_config(cross_query_at=cross_query_at)
    config["pipelines"]["inference"]["rerank"] = {
        "component_id": "remote_api",
        "component_version": "1.0.0",
        "contract_version": "1",
        "through": "rerank",
        "connection": {"url": "{{REMOTE_RERANK_URL}}", "timeout_seconds": 10},
        "parameters": {},
    }
    config["variable"] = {"REMOTE_RERANK_URL": "https://rerank.dev.example/v1/rerank"}
    await publish(runtime, config, handler)
    response = await runtime.query({"query": "散熱孔怎麼清潔？"})
    assert response.status_code == 200, response.text
    assert reranked == [contexts_at_rerank]
    assert response.json()["contexts"][0]["result_sets"][0]["key"] == "final"
