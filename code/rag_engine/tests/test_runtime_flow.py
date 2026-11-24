"""End-to-end DEV flow over HTTP: publish, ingest, query, documents, detach and delete.

Every response is validated against the vendored runtime_http.schema.json.
"""

from __future__ import annotations

import uuid

from conftest import (
    INFERENCE,
    INGESTION,
    MANAGEMENT,
    SYSTEM_ID,
    RuntimeClient,
    basic,
    scenario_config,
    validate_http,
)

DOCS = [
    {
        "document_id": "guide-1",
        "structdata": {"body": "定期清潔散熱孔，避免灰塵堆積。", "title": "設備保養", "price": 350},
    },
    {
        "document_id": "guide-2",
        "structdata": {"body": "更換濾網前先關閉電源。", "title": "安全操作", "price": 120, "tags": ["safety"]},
    },
]


async def test_health_needs_no_credentials(runtime: RuntimeClient) -> None:
    for path in ("/health/live", "/health/ready"):
        response = await runtime.http.get(path)
        assert response.status_code == 200
        validate_http("health", response.json())
        assert "x-request-id" in response.headers


async def test_request_id_is_echoed_or_generated(runtime: RuntimeClient) -> None:
    response = await runtime.http.get("/health/live", headers={"X-Request-Id": "builder-action.0001"})
    assert response.headers["x-request-id"] == "builder-action.0001"
    response = await runtime.http.get("/health/live", headers={"X-Request-Id": "has space"})
    assert uuid.UUID(response.headers["x-request-id"]).version == 4


async def test_management_routes_need_management_credentials(runtime: RuntimeClient) -> None:
    for credentials in (None, INGESTION, INFERENCE):
        headers = basic(credentials) if credentials else {}
        response = await runtime.http.get("/internal/v1/catalog", headers=headers)
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == 'Basic realm="retrieval-runtime"'
        body = response.json()
        validate_http("error_response", body)
        assert body["error"]["request_id"] == response.headers["x-request-id"]


async def test_catalog_lists_only_implemented_components(runtime: RuntimeClient) -> None:
    catalog = await runtime.catalog()
    keys = {(item["module"], item["component_id"]) for item in catalog["descriptors"]}
    assert ("chunking", "recursive") in keys and ("query_transformation", "rewrite") in keys
    assert ("rerank", "model_api") not in keys


async def test_publish_ingest_query_and_manage_documents(runtime: RuntimeClient) -> None:
    published = await runtime.initialize()
    status = published["status"]
    assert status["can_ingest"] and status["can_query"] and not status["busy"]

    accepted = await runtime.ingest(DOCS)
    assert accepted.status_code == 202, accepted.text
    validate_http("ingestion_accepted", accepted.json())
    run_id = accepted.json()["run_id"]
    assert accepted.headers["location"] == f"{runtime.business}/ingestions/{run_id}"
    done = await runtime.wait_run(run_id, {"completed", "partial", "failed"})
    assert done["status"] == "completed", done
    assert done["counts"] == {
        "total": 2,
        "queued": 0,
        "running": 0,
        "cancelling": 0,
        "completed": 2,
        "cancelled": 0,
        "failed": 0,
        "unknown": 0,
    }

    latest = await runtime.http.get(f"{runtime.business}/documents/guide-1/ingestion-status", headers=basic(INGESTION))
    validate_http("document_ingestion_status", latest.json())
    assert latest.json()["run_id"] == run_id and latest.json()["status"] == "completed"

    response = await runtime.query(
        {"query": "散熱孔怎麼清潔？", "filters": [{"field": "structdata.price", "operator": "lt", "value": 500}]}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    validate_http("inference_response", body)
    assert body["query_variants"] == ["散熱孔怎麼清潔？"]
    context = body["contexts"][0]
    assert context["query"] == context["ori_query"]
    assert context["filters"][0] == {"field": "structdata.price", "operator": "gte", "value": 300}
    assert [item["data"]["document_id"] for item in context["result_sets"][0]["items"]] == ["guide-1"]
    assert response.headers["x-config-revision"] == body["config_revision"] == "revision-1"
    assert response.headers["x-index-generation"] == body["index_generation"]

    invalid = await runtime.query(
        {"query": "x", "filters": [{"field": "structdata.body", "operator": "eq", "value": "x"}]}
    )
    assert invalid.status_code == 422 and invalid.json()["error"]["path"] == "/filters/0/field"

    exists = await runtime.http.get(f"{runtime.business}/documents/guide-1/exists", headers=basic(INGESTION))
    assert exists.json() == {"document_id": "guide-1", "exists": True}
    page = await runtime.http.get(f"{runtime.business}/documents?limit=1", headers=basic(INGESTION))
    validate_http("document_list", page.json())
    assert page.json()["documents"] == [{"document_id": "guide-1", "source_revisions": []}]
    second = await runtime.http.get(
        f"{runtime.business}/documents", params={"cursor": page.json()["next_cursor"]}, headers=basic(INGESTION)
    )
    assert [item["document_id"] for item in second.json()["documents"]] == ["guide-2"]
    assert second.json()["next_cursor"] is None
    bad_cursor = await runtime.http.get(f"{runtime.business}/documents?cursor=bogus", headers=basic(INGESTION))
    assert bad_cursor.status_code == 422 and bad_cursor.json()["error"]["code"] == "INVALID_CURSOR"

    retired = await runtime.http.post(f"{runtime.business}/documents/guide-1:retire", headers=basic(INGESTION))
    assert retired.json() == {"document_id": "guide-1", "result": "deleted"}
    again = await runtime.http.post(f"{runtime.business}/documents/guide-1:retire", headers=basic(INGESTION))
    assert again.json() == {"document_id": "guide-1", "result": "not_found"}

    binding = {
        "X-Expected-Config-Revision": "revision-1",
        "X-Expected-Index-Generation": status["index_generation"],
        "X-Expected-Index-Fingerprint": published["fingerprint"],
    }
    detached = await runtime.http.post(
        f"/internal/v1/systems/{SYSTEM_ID}:detach?pipeline=inference",
        headers={**basic(MANAGEMENT), "Idempotency-Key": "detach-1", **binding},
    )
    assert detached.status_code == 204, detached.text
    blocked = await runtime.query({"query": "x"})
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "PIPELINE_NOT_ENABLED"

    observed = await runtime.http.get(f"/internal/v1/systems/{SYSTEM_ID}", headers={**basic(MANAGEMENT), **binding})
    validate_http("system_status", observed.json())
    assert observed.json()["pipelines"]["inference"]["loaded"] is False

    deleted = await runtime.http.delete(
        f"/internal/v1/systems/{SYSTEM_ID}", headers={**basic(MANAGEMENT), "Idempotency-Key": "delete-1", **binding}
    )
    assert deleted.status_code == 204, deleted.text
    gone = await runtime.http.get(f"/internal/v1/systems/{SYSTEM_ID}", headers=basic(MANAGEMENT))
    assert gone.status_code == 404 and gone.json()["error"]["code"] == "SYSTEM_NOT_FOUND"


async def test_business_routes_check_pipeline_credentials(runtime: RuntimeClient) -> None:
    await runtime.initialize()
    wrong = await runtime.http.post(f"{runtime.business}/queries", json={"query": "x"}, headers=basic(INGESTION))
    assert wrong.status_code == 401
    wrong = await runtime.http.post(
        f"{runtime.business}/ingestions", json={"documents": DOCS}, headers=basic(MANAGEMENT)
    )
    assert wrong.status_code == 401


async def test_ingestion_rejects_invalid_documents(runtime: RuntimeClient) -> None:
    await runtime.initialize()
    response = await runtime.ingest([{"document_id": "x", "structdata": {"title": "no body"}}])
    assert response.status_code == 422
    assert response.json()["error"]["path"] == "/documents/0/structdata/body"
    response = await runtime.ingest([DOCS[0], DOCS[0]])
    assert response.json()["error"]["path"] == "/documents/1/document_id"
    raw = await runtime.http.post(
        f"{runtime.business}/ingestions", content=b"{", headers={**basic(INGESTION), "Content-Type": "application/json"}
    )
    assert raw.status_code == 400 and raw.json()["error"]["code"] == "INVALID_JSON"


async def test_apply_is_idempotent_and_rejects_stale_context(runtime: RuntimeClient) -> None:
    published = await runtime.initialize()
    replay = await runtime.http.put(
        f"/internal/v1/systems/{SYSTEM_ID}",
        json=published["apply"],
        headers={**basic(MANAGEMENT), "Idempotency-Key": "initialize-001"},
    )
    assert replay.status_code == 200 and replay.json() == published["status"]
    changed = {**published["apply"], "draft_revision": "draft-2"}
    conflict = await runtime.http.put(
        f"/internal/v1/systems/{SYSTEM_ID}",
        json=changed,
        headers={**basic(MANAGEMENT), "Idempotency-Key": "initialize-001"},
    )
    assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    stale = await runtime.http.put(
        f"/internal/v1/systems/{SYSTEM_ID}",
        json=published["apply"],
        headers={**basic(MANAGEMENT), "Idempotency-Key": "initialize-002"},
    )
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "STALE_CONTEXT"


async def test_update_reuses_or_requires_rebuild_confirmation(runtime: RuntimeClient) -> None:
    published = await runtime.initialize()
    catalog = await runtime.catalog()
    generation = published["status"]["index_generation"]

    async def preview(config: dict, active: str) -> dict:
        body = {
            "runtime_ref": catalog["runtime_ref"],
            "catalog_revision": catalog["catalog_revision"],
            "draft_revision": "draft-2",
            "config": config,
            "operation": "update",
            "expected_active_revision": active,
            "expected_index_generation": generation,
            "expected_index_fingerprint": published["fingerprint"],
        }
        response = await runtime.http.post(
            f"/internal/v1/systems/{SYSTEM_ID}/config:validate", json=body, headers=basic(MANAGEMENT)
        )
        assert response.status_code == 200, response.text
        return {"body": body, "validation": response.json()}

    query_only = published["apply"]["config"]
    query_only["pipelines"]["inference"]["retrieval"]["parameters"]["top_n"] = 1
    reuse = await preview(query_only, "revision-1")
    assert reuse["validation"]["index_impact"]["action"] == "reuse"
    apply = {
        **reuse["body"],
        "context_revision": reuse["validation"]["context_revision"],
        "config_revision": "revision-2",
    }
    response = await runtime.http.put(
        f"/internal/v1/systems/{SYSTEM_ID}", json=apply, headers={**basic(MANAGEMENT), "Idempotency-Key": "update-1"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["index_generation"] == generation
    assert response.json()["active_config_revision"] == "revision-2"

    rebuilt = published["apply"]["config"]
    rebuilt["pipelines"]["ingestion"]["chunking"]["parameters"]["max_tokens"] = 200
    change = await preview(rebuilt, "revision-2")
    assert change["validation"]["index_impact"]["action"] == "rebuild_required"
    apply = {
        **change["body"],
        "context_revision": change["validation"]["context_revision"],
        "config_revision": "revision-3",
        "target_index_generation": str(uuid.uuid4()),
    }
    response = await runtime.http.put(
        f"/internal/v1/systems/{SYSTEM_ID}", json=apply, headers={**basic(MANAGEMENT), "Idempotency-Key": "update-2"}
    )
    assert response.status_code == 409 and response.json()["error"]["code"] == "REBUILD_CONFIRMATION_REQUIRED"
    response = await runtime.http.put(
        f"/internal/v1/systems/{SYSTEM_ID}",
        json={**apply, "allow_rebuild": True},
        headers={**basic(MANAGEMENT), "Idempotency-Key": "update-3"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["index_generation"] == apply["target_index_generation"]
    assert response.json()["active_config_revision"] == "revision-3"


async def test_config_errors_are_located(runtime: RuntimeClient) -> None:
    catalog = await runtime.catalog()
    config = {"contract_version": "0.2-draft", "pipelines": {"ingestion": {}, "inference": {}}}
    body = {
        "runtime_ref": catalog["runtime_ref"],
        "catalog_revision": catalog["catalog_revision"],
        "draft_revision": "d",
        "config": config,
        "expected_active_revision": None,
        "expected_index_generation": None,
        "expected_index_fingerprint": None,
    }
    response = await runtime.http.post(
        f"/internal/v1/systems/{SYSTEM_ID}/config:validate", json=body, headers=basic(MANAGEMENT)
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "CONFIG_VALIDATION_FAILED"
    assert response.json()["error"]["path"].startswith("/config/pipelines/")
    stale = await runtime.http.post(
        f"/internal/v1/systems/{SYSTEM_ID}/config:validate",
        json={**body, "catalog_revision": "catalog-0"},
        headers=basic(MANAGEMENT),
    )
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "STALE_CATALOG"


async def test_retrieval_parameter_references_over_http(runtime: RuntimeClient) -> None:
    config = scenario_config()
    inference = config["pipelines"]["inference"]
    inference["fixed_filters"] = []
    inference["inference_input"]["parameters"]["request_parameters"] = [
        {"name": "TOP_N", "type": "integer", "required": False}
    ]
    inference["retrieval"]["parameters"]["top_n"] = "{{TOP_N}}"
    config["variable"] = {"TOP_N": "1"}
    await runtime.initialize(config)
    accepted = await runtime.ingest(DOCS)
    done = await runtime.wait_run(accepted.json()["run_id"], {"completed", "partial", "failed"})
    assert done["status"] == "completed", done

    def items(response: object) -> list[str]:
        body = response.json()  # type: ignore[attr-defined]
        validate_http("inference_response", body)
        return [item["data"]["document_id"] for item in body["contexts"][0]["result_sets"][0]["items"]]

    by_variable = await runtime.query({"query": "保養"})
    assert by_variable.status_code == 200, by_variable.text
    assert len(items(by_variable)) == 1
    by_request = await runtime.query({"query": "保養", "parameters": {"TOP_N": 2}})
    assert by_request.status_code == 200, by_request.text
    assert len(items(by_request)) == 2

    invalid = await runtime.query({"query": "保養", "parameters": {"TOP_N": 0}})
    assert invalid.status_code == 422
    error = invalid.json()["error"]
    validate_http("error_response", invalid.json())
    assert error["code"] == "REQUEST_VALIDATION_FAILED" and error["path"] == "/parameters/TOP_N"


async def test_header_aware_chunking_over_http(runtime: RuntimeClient) -> None:
    config = scenario_config()
    chunking = config["pipelines"]["ingestion"]["chunking"]
    chunking["component_id"] = "header_aware"
    chunking["parameters"]["header_levels"] = [1, 2]
    await runtime.initialize(config)
    body = "簡介。\n# 安裝\n先關閉電源。\n## 檢查\n確認風扇轉動。\n### 細節\n用手轉動。"
    accepted = await runtime.ingest(
        [{"document_id": "manual", "structdata": {"body": body, "title": "手冊", "price": 400}}]
    )
    done = await runtime.wait_run(accepted.json()["run_id"], {"completed", "partial", "failed"})
    assert done["status"] == "completed", done

    response = await runtime.query({"query": "風扇"})
    assert response.status_code == 200, response.text
    texts = {item["data"]["structdata"]["text"] for item in response.json()["contexts"][0]["result_sets"][0]["items"]}
    assert texts == {"簡介。", "# 安裝\n先關閉電源。", "## 檢查\n確認風扇轉動。\n### 細節\n用手轉動。"}
