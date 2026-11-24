"""Drive a running DEV Runtime through the Builder flow over real HTTP.

Works against `make run` on this machine and against a deployed DEV Runtime with real
Elasticsearch and bge-m3: the checks only rely on the API contract, not on scores.
Every response body is validated against the vendored runtime_http.schema.json.

    uv run python scripts/smoke_dev_runtime.py --base-url http://127.0.0.1:8080

Management credentials come from --username/--password or RAG_SMOKE_MANAGEMENT_USERNAME /
RAG_SMOKE_MANAGEMENT_PASSWORD (default mock/mock, the `make run` values). The script uses a
new random System ID and deletes the System at the end.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import secrets
import sys
import time
import uuid
from typing import Any

import httpx
import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from rag_engine.contracts import check, http_def, schema_ref

DOCUMENTS = [
    {
        "document_id": "guide-1",
        "structdata": {"body": "定期清潔散熱孔，避免灰塵堆積。", "title": "設備保養", "price": 350},
    },
    {
        "document_id": "guide-2",
        "structdata": {"body": "更換濾網前先關閉電源。", "title": "安全操作", "price": 120, "tags": ["safety"]},
    },
    {
        "document_id": "guide-3",
        "structdata": {"body": "每月檢查風扇轉速是否正常。", "title": "設備保養", "price": 800},
    },
]


def step(name: str) -> None:
    print(f"OK  {name}")


def expect(response: httpx.Response, status: int, definition: str | None = None) -> Any:
    """Assert the status code and validate the JSON body against a runtime_http definition."""
    assert response.status_code == status, f"{response.request.method} {response.request.url}: {response.text}"
    if status == 204:
        return None
    body = response.json()
    check(http_def(definition or "error_response"), body)
    return body


def build_config(catalog: dict[str, Any], ingestion: tuple[str, str], inference: tuple[str, str]) -> dict[str, Any]:
    """A small Config using the first embedding and tokenizer profiles the Catalog offers."""
    profile = next(iter(catalog["resources"]["profiles"]))
    tokenizer = next(iter(catalog["resources"]["tokenizer_profiles"]))
    return {
        "contract_version": "0.2-draft",
        "secret": {
            "INGESTION_API_USERNAME": ingestion[0],
            "INGESTION_API_PASSWORD": ingestion[1],
            "INFERENCE_API_USERNAME": inference[0],
            "INFERENCE_API_PASSWORD": inference[1],
        },
        "pipelines": {
            "ingestion": {
                "import": {
                    "component_id": "platform",
                    "component_version": "1.0.0",
                    "parameters": {
                        "structdata": {
                            "body": {"type": "string", "required": True},
                            "title": {"type": "string", "required": True, "filterable": True},
                            "price": {"type": "number", "required": False, "searchable": False, "filterable": True},
                            "tags": {"type": "string_array", "required": False, "filterable": True},
                        }
                    },
                },
                "parsing": {"component_id": "passthrough", "component_version": "1.0.0", "parameters": {}},
                "chunking": {
                    "component_id": "recursive",
                    "component_version": "1.0.0",
                    "parameters": {
                        "split_field": "body",
                        "output_field": "text",
                        "copy_fields": [
                            {"source_field": "title", "output_field": "title"},
                            {"source_field": "price", "output_field": "price"},
                            {"source_field": "tags", "output_field": "tags"},
                        ],
                        "max_tokens": 500,
                        "overlap_tokens": 50,
                        "tokenizer_profile_id": tokenizer,
                    },
                },
                "embedding": {
                    "component_id": "dense",
                    "component_version": "1.0.0",
                    "parameters": {"profile": profile, "mappings": [{"source_field": "text", "vector_name": "text"}]},
                },
                "indexing": {
                    "component_id": "elasticsearch",
                    "component_version": "1.0.0",
                    "parameters": {
                        "service_source": "dev_test",
                        "vector_name": "text",
                        "structdata_overrides": {"text": {"searchable": True}},
                    },
                },
            },
            "inference": {
                "inference_input": {
                    "component_id": "platform",
                    "component_version": "1.0.0",
                    "parameters": {
                        "request_parameters": [{"name": "TOP_N", "type": "integer", "required": False}],
                    },
                },
                "query_transformation": {"component_id": "none", "component_version": "1.0.0", "parameters": {}},
                "retrieval": {
                    "component_id": "builtin",
                    "component_version": "1.0.0",
                    "parameters": {
                        "per_route_k": 10,
                        "vector_fields": ["text"],
                        "fulltext_fields": ["structdata.text"],
                        "fusion": "rrf",
                        "top_n": "{{TOP_N}}",
                    },
                },
                "rerank": {"component_id": "none", "component_version": "1.0.0", "parameters": {}},
            },
        },
        "variable": {"TOP_N": "5"},
    }


class Smoke:
    def __init__(self, base_url: str, management: tuple[str, str]) -> None:
        self.base_url = base_url.rstrip("/")
        self.http = httpx.Client(base_url=self.base_url, timeout=30)
        self.management = management
        self.system_id = str(uuid.uuid4())
        self.ingestion = ("ingestion", secrets.token_urlsafe(12))
        self.inference = ("inference", secrets.token_urlsafe(12))
        self.business = f"/internal/systems/{self.system_id}/v1"
        self.system_path = f"/internal/v1/systems/{self.system_id}"

    # ------------------------------------------------------------------ helpers

    def manage(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        return self.http.request(method, path, auth=self.management, **kwargs)

    def ingest(self, documents: list[dict[str, Any]]) -> str:
        response = self.http.post(f"{self.business}/ingestions", json={"documents": documents}, auth=self.ingestion)
        accepted = expect(response, 202, "ingestion_accepted")
        assert response.headers["location"] == f"{self.business}/ingestions/{accepted['run_id']}"
        return str(accepted["run_id"])

    def wait_run(self, run_id: str, timeout: float = 120) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while True:
            response = self.http.get(f"{self.business}/ingestions/{run_id}", auth=self.ingestion)
            body = expect(response, 200, "ingestion_run_status")
            if body["status"] in ("completed", "partial", "failed"):
                return dict(body)
            assert time.monotonic() < deadline, f"run {run_id} did not finish: {body['status']}"
            time.sleep(0.2)

    def query(self, body: dict[str, Any], status: int = 200) -> Any:
        response = self.http.post(f"{self.business}/queries", json=body, auth=self.inference)
        return expect(response, status, "inference_response" if status == 200 else None)

    @staticmethod
    def items(result: dict[str, Any]) -> list[dict[str, Any]]:
        return list(result["contexts"][0]["result_sets"][0]["items"])

    def preview_and_apply(
        self, catalog: dict[str, Any], config: dict[str, Any], operation: str, revision: str, **expected: Any
    ) -> dict[str, Any]:
        body = {
            "runtime_ref": catalog["runtime_ref"],
            "catalog_revision": catalog["catalog_revision"],
            "draft_revision": f"draft-{revision}",
            "config": config,
            "operation": operation,
            "expected_active_revision": expected.get("active"),
            "expected_index_generation": expected.get("generation"),
            "expected_index_fingerprint": expected.get("fingerprint"),
        }
        validation = expect(self.manage("POST", f"{self.system_path}/config:validate", json=body), 200, "validation")
        apply = {**body, "context_revision": validation["context_revision"], "config_revision": revision}
        if validation["index_impact"]["action"] == "create":
            apply["target_index_generation"] = str(uuid.uuid4())
        key = f"{operation}-{revision}"
        response = self.manage("PUT", self.system_path, json=apply, headers={"Idempotency-Key": key})
        status = expect(response, 200, "system_status")
        replay = self.manage("PUT", self.system_path, json=apply, headers={"Idempotency-Key": key})
        assert expect(replay, 200, "system_status") == status, "Idempotency-Key replay changed the result"
        return {"validation": validation, "status": status}

    # ------------------------------------------------------------------ flow

    def run(self) -> None:
        for path in ("/health/live", "/health/ready"):
            expect(self.http.get(path), 200, "health")
        step("health live / ready")

        expect(self.http.get("/internal/v1/catalog"), 401)
        catalog = self.manage("GET", "/internal/v1/catalog").json()
        check(schema_ref("runtime_catalog.draft.schema.json"), catalog)
        step(f"catalog {catalog['runtime_ref']} {catalog['catalog_revision']}")

        config = build_config(catalog, self.ingestion, self.inference)
        published = self.preview_and_apply(catalog, config, "initialize", "revision-1")
        assert published["validation"]["index_impact"]["action"] == "create"
        status = published["status"]
        assert status["can_ingest"] and status["can_query"], status
        fingerprint = published["validation"]["index_impact"]["index_fingerprint"]
        binding = {
            "X-Expected-Config-Revision": "revision-1",
            "X-Expected-Index-Generation": status["index_generation"],
            "X-Expected-Index-Fingerprint": fingerprint,
        }
        expect(self.manage("GET", self.system_path, headers=binding), 200, "system_status")
        listed = expect(self.manage("GET", "/internal/v1/systems"), 200, "system_list")
        assert self.system_id in str(listed)
        step("validate → initialize → replay → GET / list systems")

        run_id = self.ingest(DOCUMENTS)
        done = self.wait_run(run_id)
        assert done["status"] == "completed", done
        latest = self.http.get(f"{self.business}/documents/guide-1/ingestion-status", auth=self.ingestion)
        expect(latest, 200, "document_ingestion_status")
        exists = expect(
            self.http.get(f"{self.business}/documents/guide-1/exists", auth=self.ingestion), 200, "document_exists"
        )
        assert exists["exists"] is True
        first = expect(
            self.http.get(f"{self.business}/documents", params={"limit": 2}, auth=self.ingestion), 200, "document_list"
        )
        second = expect(
            self.http.get(f"{self.business}/documents", params={"cursor": first["next_cursor"]}, auth=self.ingestion),
            200,
            "document_list",
        )
        ids = [doc["document_id"] for doc in first["documents"] + second["documents"]]
        assert ids == ["guide-1", "guide-2", "guide-3"], ids
        step(f"ingest {len(DOCUMENTS)} documents ({run_id}) → status / exists / paged list")

        result = self.query({"query": "散熱孔怎麼清潔？"})
        assert result["config_revision"] == "revision-1" and self.items(result), result
        filtered = self.query(
            {"query": "保養", "filters": [{"field": "structdata.title", "operator": "eq", "value": "設備保養"}]}
        )
        assert {item["data"]["structdata"]["title"] for item in self.items(filtered)} == {"設備保養"}
        assert len(self.items(self.query({"query": "保養", "parameters": {"TOP_N": 1}}))) == 1
        bad = self.query({"query": "x", "parameters": {"TOP_N": 0}}, status=422)
        assert bad["error"]["path"] == "/parameters/TOP_N"
        expect(self.http.post(f"{self.business}/queries", json={"query": "x"}, auth=self.ingestion), 401)
        step("query: plain / filter / TOP_N request value / invalid value / wrong credentials")

        asyncio.run(self.check_mcp())
        step("MCP: initialize → tools/list → tools/call")

        many = [
            {"document_id": f"bulk-{n:03d}", "structdata": {"body": f"第 {n} 份文件。" * 20, "title": "批次"}}
            for n in range(40)
        ]
        bulk_run = self.ingest(many)
        cancel_ids = [doc["document_id"] for doc in many[-5:]]
        cancelled = self.http.post(
            f"{self.business}/ingestions/{bulk_run}/cancel", json={"document_ids": cancel_ids}, auth=self.ingestion
        )
        outcome = expect(cancelled, 200, "ingestion_cancel_result")
        results = sorted({doc["result"] for doc in outcome["documents"]})
        done = self.wait_run(bulk_run)
        assert done["status"] in ("completed", "partial"), done
        step(f"cancel 5 of 40 queued documents → {results}, run {done['status']}")

        retired = self.http.post(f"{self.business}/documents/guide-2:retire", auth=self.ingestion)
        assert expect(retired, 200, "document_retire")["result"] == "deleted"
        again = self.http.post(f"{self.business}/documents/guide-2:retire", auth=self.ingestion)
        assert expect(again, 200, "document_retire")["result"] == "not_found"
        step("retire document → deleted, then not_found")

        config["variable"]["TOP_N"] = "1"
        updated = self.preview_and_apply(
            catalog,
            config,
            "update",
            "revision-2",
            active="revision-1",
            generation=status["index_generation"],
            fingerprint=fingerprint,
        )
        assert updated["validation"]["index_impact"]["action"] == "reuse"
        assert updated["status"]["index_generation"] == status["index_generation"]
        result = self.query({"query": "保養"})
        assert result["config_revision"] == "revision-2" and len(self.items(result)) == 1
        step("update query-only setting → index reused, revision-2 serves")

        binding["X-Expected-Config-Revision"] = "revision-2"
        detached = self.manage(
            "POST",
            f"{self.system_path}:detach",
            params={"pipeline": "inference"},
            headers={"Idempotency-Key": "detach-1", **binding},
        )
        expect(detached, 204)
        blocked = self.query({"query": "x"}, status=409)
        assert blocked["error"]["code"] == "PIPELINE_NOT_ENABLED"
        step("detach inference → queries refused with PIPELINE_NOT_ENABLED")

        deleted = self.manage("DELETE", self.system_path, headers={"Idempotency-Key": "delete-1", **binding})
        expect(deleted, 204)
        gone = expect(self.manage("GET", self.system_path), 404)
        assert gone["error"]["code"] == "SYSTEM_NOT_FOUND"
        step("delete System and its index → GET 404")

    async def check_mcp(self) -> None:
        url = f"{self.base_url}/internal/systems/{self.system_id}/mcp"
        async with httpx2.AsyncClient(auth=httpx2.BasicAuth(*self.inference)) as client:
            async with streamable_http_client(url, http_client=client) as streams:
                async with ClientSession(streams[0], streams[1]) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    assert [tool.name for tool in tools.tools] == ["search"]
                    result = await session.call_tool("search", {"query": "散熱孔怎麼清潔？"})
                    assert not result.is_error, result
                    assert result.structured_content is not None
                    assert result.structured_content["contexts"][0]["result_sets"][0]["key"] == "final"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--username", default=os.environ.get("RAG_SMOKE_MANAGEMENT_USERNAME", "mock"))
    parser.add_argument("--password", default=os.environ.get("RAG_SMOKE_MANAGEMENT_PASSWORD", "mock"))
    args = parser.parse_args()
    smoke = Smoke(args.base_url, (args.username, args.password))
    print(f"Runtime {smoke.base_url}, System {smoke.system_id}")
    started = time.monotonic()
    smoke.run()
    print(f"PASS in {time.monotonic() - started:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
