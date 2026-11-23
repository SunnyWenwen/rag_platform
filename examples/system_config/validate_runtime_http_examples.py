"""Verify the HTTP Mock fixtures without starting Runtime or any backing service."""
from base64 import b64decode
import json
import sys
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from validate_descriptor_draft import ConfigError, compile_local_example, validate_filters


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from contract_validation import contract_formats

SCHEMAS = {path.name: json.loads(path.read_text()) for path in (HERE.parents[1] / "schemas").glob("*.json")}
REGISTRY = Registry().with_resources((schema["$id"], Resource.from_contents(schema)) for schema in SCHEMAS.values())
SYSTEM_PATH = "/internal/v1/systems/"
DRAFT_KEYS = ("runtime_ref", "catalog_revision", "draft_revision")
HTTP_SCHEMA = SCHEMAS["runtime_http.schema.json"]
DOCUMENT_STATES = HTTP_SCHEMA["$defs"]["document_status"]["enum"]
FORMATS = contract_formats(SCHEMAS["document.schema.json"])


def schema(name):
    return Draft202012Validator(SCHEMAS[name], registry=REGISTRY, format_checker=FORMATS)


def validate_http(name, value):
    definition = {"$ref": f'{HTTP_SCHEMA["$id"]}#/$defs/{name}'}
    Draft202012Validator(
        definition, registry=REGISTRY, format_checker=FORMATS
    ).validate(value)


def identity_validator(name):
    uri = SCHEMAS["runtime_identity.schema.json"]["$id"]
    return Draft202012Validator({"$ref": f"{uri}#/$defs/{name}"}, registry=REGISTRY)


def verify_index_fingerprint(fields, vectors, system_id, index_generation):
    expected = json.loads((HERE / "index_fingerprint.v1.example.json").read_text())
    projection, meta = expected["projection"], expected["mapping_meta"]
    definition = SCHEMAS["index_fingerprint.v1.schema.json"]
    projection_check = schema("index_fingerprint.v1.schema.json")
    projection_check.validate(projection)
    remote_stage = {
        "kind": "remote", "module": "parsing", "through": "embedding",
        "adapter_version": "1.0.0", "contract_version": "1", "implementation_revision": "external-v1",
        "parameters": {}, "output_structdata": projection["ingestion"][-1]["output_structdata"],
    }
    remote_projection = {**projection, "ingestion": [projection["ingestion"][0], remote_stage]}
    projection_check.validate(remote_projection)
    del remote_stage["contract_version"]
    assert not projection_check.is_valid(remote_projection)
    meta_check = Draft202012Validator({"$ref": definition["$id"] + "#/$defs/mapping_meta"}, registry=REGISTRY)
    meta_check.validate(meta)
    assert meta["system_id"] == system_id
    assert meta["env"] == "builder"
    assert expected["index_generation"] == index_generation
    assert expected["index_name"] == f"rag-builder-{system_id}-{index_generation}"
    for case in expected["ownership_cases"]:
        observed = {**meta, **case.get("meta_changes", {})}
        for name in case.get("omit_meta", []):
            del observed[name]
        actual_name = case.get("index_name", expected["index_name"])
        verified = actual_name == expected["index_name"] and meta_check.is_valid(observed) and observed == meta
        code = None if verified else "INDEX_OWNERSHIP_UNVERIFIED"
        assert code == case["expected_code"], case["name"]

    def simple_jcs_fixture(value):
        # The fixture uses ASCII keys and safe integers, so sorted compact
        # Python JSON has the same encoding as JCS for these values.
        if isinstance(value, dict):
            return all(key.isascii() and simple_jcs_fixture(item) for key, item in value.items())
        if isinstance(value, list):
            return all(map(simple_jcs_fixture, value))
        return value is None or isinstance(value, (str, bool)) or type(value) is int and abs(value) < 2**53

    assert simple_jcs_fixture(projection)
    encoded = json.dumps(projection, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    assert sha256(encoded).hexdigest() == meta["index_fingerprint"]
    assert projection["version"] == meta["index_fingerprint_version"]
    index = projection["index"]
    assert set(index["vector_bindings"]) == set(index["embedding_spaces"]) == set(vectors)
    assert index["structdata"] == {name: asdict(field) for name, field in fields.items()}
    assert index["vector_bindings"] == {
        name: {"source_field": vector.source, "embedding_profile_id": vector.profile, "dimensions": vector.dimensions}
        for name, vector in vectors.items()
    }
    assert not projection_check.is_valid({**projection, "source_revision": "v1"})
    assert not projection_check.is_valid({**projection, "env": "builder"})


def verify_deployment_env():
    deployment = json.loads((HERE / "deployment.env.example.json").read_text())
    independent = identity_validator("standalone_deployment_env")
    independent.validate(deployment)
    identity_validator("uuid_v4").validate(deployment["index_generation"])
    assert not independent.is_valid({**deployment, "index_generation": "index-1"})
    independent.validate({"env": "ent"})
    independent.validate({"env": "ftest-team-a"})
    identity_validator("deployment_env").validate({"env": "builder"})
    for invalid in ("builder", "FTEST", "ftest\n", "../ent", "ftest--a", "a" * 33):
        assert not independent.is_valid({"env": invalid}), invalid
    assert not independent.is_valid({})


def assert_error_response(body, request_body, *, ingestion_conflicts=False):
    validate_http("document_busy_error_response" if ingestion_conflicts else "error_response", body)
    error = body["error"]
    if "path" in error:
        assert request_body is not None
    if ingestion_conflicts:
        schema("ingestion_request.schema.json").validate(request_body)
        document_ids = [document["document_id"] for document in request_body["documents"]]
        conflicts = error["conflicts"]
        conflict_ids = [conflict["document_id"] for conflict in conflicts]
        conflict_id_set = set(conflict_ids)
        assert conflict_ids == [document_id for document_id in document_ids if document_id in conflict_id_set]
        first = conflicts[0]
        assert error["path"] == f"/documents/{document_ids.index(first['document_id'])}/document_id"
        assert error.get("run_id") == first.get("run_id")


def assert_run(body, run_id):
    validate_http("ingestion_run_status", body)
    assert body["run_id"] == run_id
    if "counts" not in body:
        return
    counts = body["counts"]
    statuses = [item["status"] for item in body["documents"]]
    assert counts["total"] == len(statuses) == sum(counts[state] for state in DOCUMENT_STATES) > 0
    assert all(counts[state] == statuses.count(state) for state in DOCUMENT_STATES)


def assert_system_status(body, system_id):
    validate_http("system_status", body)
    assert body["system_id"] == system_id
    pipelines = body["pipelines"]
    assert body["loaded"] == any(status["loaded"] for status in pipelines.values())
    for pipeline, capability in (("ingestion", "can_ingest"), ("inference", "can_query")):
        status = pipelines[pipeline]
        assert status["ready"] == body[capability]
        if status["ready"]:
            assert body["index_ready"] is not False
            assert status["config_revision"] == body["active_config_revision"]
            assert status["index_generation"] == body["index_generation"]


def verify(scenarios):
    for definition in SCHEMAS.values():
        Draft202012Validator.check_schema(definition)
    catalog = json.loads((HERE / "runtime_catalog.response.json").read_text())
    schema("runtime_catalog.draft.schema.json").validate(catalog)
    published = {(item["module"], item["component_id"], item["component_version"]) for item in catalog["descriptors"]}
    assert len(published) == len(catalog["descriptors"])
    happy = scenarios["happy_path"]
    initialize = next(item for item in happy if item["request"]["method"] == "PUT")
    initial_config = initialize["request"]["body"]["config"]
    initial = initialize["response"]["body"]
    system_id = initial["system_id"]
    fields, vectors, index = compile_local_example({
        "system_id": system_id, "config_revision": initial["active_config_revision"],
        "config": initial_config,
    })
    verify_index_fingerprint(fields, vectors, system_id, initial["index_generation"])
    metadata = json.loads((HERE / "index_fingerprint.v1.example.json").read_text())["mapping_meta"]
    assert metadata["created_by_operation_id"] == initialize["request"]["headers"]["Idempotency-Key"]
    assert metadata["created_by_operation_id"] == initial["created_by_operation_id"]
    verify_deployment_env()
    uuid_check = identity_validator("uuid_v4")
    assert not uuid_check.is_valid("es-example")
    assert not uuid_check.is_valid(system_id.upper())

    for steps in scenarios.values():
        previews = {}
        requests_by_operation = {}
        for step in steps:
            request, response = step["request"], step["response"]
            url = urlsplit(request["path"])
            path = url.path
            method, sent = request["method"], request.get("body")
            status, body = response["status"], response.get("body")
            system_route = path.startswith(SYSTEM_PATH)
            is_detach = system_route and method == "POST" and path.endswith(":detach")
            if system_route:
                uuid_check.validate(path[len(SYSTEM_PATH):].split("/", 1)[0].removesuffix(":detach"))
            if path.startswith("/internal/systems/"):
                uuid_check.validate(path.split("/")[3])

            if status >= 400:
                ingestion_conflicts = (
                    method == "POST" and path.endswith("/ingestions")
                    and status == 409 and body["error"]["code"] == "DOCUMENT_BUSY"
                )
                assert_error_response(body, sent, ingestion_conflicts=ingestion_conflicts)
            if status == 204:
                assert "body" not in response and "body_file" not in response
            if "body_file" in response:
                assert path == "/internal/v1/catalog" and response["body_file"] == "runtime_catalog.response.json"
            if method == "GET" and status == 200:
                if path in ("/health/live", "/health/ready"):
                    validate_http("health", body)
                if path == SYSTEM_PATH.rstrip("/"):
                    validate_http("system_list", body)
                    for system in body["systems"]:
                        assert_system_status(system, system["system_id"])
                        assert system["loaded"]
                elif path.startswith(SYSTEM_PATH):
                    assert_system_status(body, path[len(SYSTEM_PATH):])
                    observation = request.get("headers", {})
                    if not body["loaded"]:
                        assert body["index_generation"] == observation["X-Expected-Index-Generation"]
                    if observation:
                        assert observation["X-Expected-Config-Revision"] == body["active_config_revision"]
                        validate_http("index_fingerprint", observation["X-Expected-Index-Fingerprint"])
            if system_route and (method in ("PUT", "DELETE") or is_detach):
                headers = request["headers"]
                key = headers["Idempotency-Key"]
                assert key
                identity = (path.removesuffix(":detach"), key)
                if identity in requests_by_operation:
                    assert request == requests_by_operation[identity]
                requests_by_operation[identity] = request
                if method == "DELETE" or is_detach:
                    assert sent is None
                    assert headers["X-Expected-Config-Revision"]
                    uuid_check.validate(headers["X-Expected-Index-Generation"])
                    validate_http("index_fingerprint", headers["X-Expected-Index-Fingerprint"])
                    query = parse_qs(url.query, keep_blank_values=True)
                    if is_detach and query:
                        assert set(query) == {"pipeline"}
                        pipeline, = query["pipeline"]
                        validate_http("pipeline", pipeline)
                    if method == "DELETE":
                        assert not query
            if system_route and (method == "PUT" or path.endswith("/config:validate")):
                system_id = path[len(SYSTEM_PATH):].removesuffix("/config:validate")
                snapshot = {"system_id": system_id, "config_revision": sent.get("config_revision", "preview"),
                            "config": sent["config"]}
                validate_http("apply_request" if method == "PUT" else "validate_request", sent)
                operation = sent.get("operation")
                pipeline_scope = sent.get("pipeline")
                if operation == "recover_index" and method == "PUT":
                    assert sent["config_revision"] == sent["recovery_from"]["config_revision"]
                if status == 422:
                    try:
                        compile_local_example(snapshot)
                    except ConfigError as error:
                        assert str(error) == "invalid selection:/mappings/*/source_field"
                    else:
                        raise AssertionError("Invalid source field passed Config validation")
                if status == 200:
                    compile_local_example(snapshot)
                    assert all(sent[key] == catalog[key] for key in DRAFT_KEYS[:2])
                    for pipeline in sent["config"]["pipelines"].values():
                        for module, config in pipeline.items():
                            if module != "fixed_filters":
                                assert (module, config["component_id"], config["component_version"]) in published
                    if method == "POST":
                        assert all(body[key] == sent[key] for key in DRAFT_KEYS)
                        validate_http("validation", body)
                        assert body.get("pipeline") == pipeline_scope
                        impact = body["index_impact"]
                        if pipeline_scope == "inference" and operation not in (None, "reload"):
                            assert impact["action"] == "blocked" and impact["code"] == "PIPELINE_OPERATION_UNSUPPORTED"
                        previews[body["context_revision"]] = (sent, body)
                    else:
                        draft, preview = previews[sent["context_revision"]]
                        assert all(sent[key] == draft[key] for key in (*DRAFT_KEYS, "config", "operation"))
                        assert pipeline_scope == draft.get("pipeline")
                        assert pipeline_scope != "inference" or operation == "reload"
                        assert sent.get("recovery_from") == draft.get("recovery_from")
                        assert all(sent[key] == draft[key] for key in (
                            "expected_active_revision", "expected_index_generation", "expected_index_fingerprint"
                        ))
                        assert preview["active_config_revision"] == sent["expected_active_revision"] or (
                            operation == "recover_index" and not preview["loaded"]
                        )
                        action = preview["index_impact"]["action"]
                        assert bool(sent.get("allow_rebuild")) == (action == "rebuild_required")
                        revision = sent["config_revision"]
                        if operation == "initialize":
                            assert sent["expected_active_revision"] is None and action in {"create", "none"}
                        elif operation == "reload":
                            assert sent["expected_active_revision"] == revision and action in {"reuse", "none"}
                        elif operation == "update":
                            assert sent["expected_active_revision"] != revision and action in {"reuse", "rebuild_required", "none"}
                        else:
                            assert action == "recover"
                            assert sent["expected_active_revision"] in {None, revision}
                            assert body["index_generation"] != sent["recovery_from"]["index_generation"]
                        assert_system_status(body, system_id)
                        assert body["active_config_revision"] == revision
                        if action in {"create", "recover", "rebuild_required"}:
                            assert body["index_generation"] == sent["target_index_generation"]
                            assert body["created_by_operation_id"] == headers["Idempotency-Key"]
                        elif action == "reuse":
                            assert "target_index_generation" not in sent
                            assert body["index_generation"] == sent["expected_index_generation"]
                        if not pipeline_scope:
                            assert body["loaded"]
                        elif operation in ("initialize", "reload"):
                            assert body["pipelines"][pipeline_scope]["loaded"]
            if path.endswith("/ingestions") and status == 202:
                schema("ingestion_request.schema.json").validate(sent)
                validate_http("ingestion_accepted", body)
                assert response["headers"]["Location"] == f"{path}/{body['run_id']}"
                assert body["documents"] == [{"document_id": doc["document_id"], "status": "queued"}
                                             for doc in sent["documents"]]
            if "/ingestions/" in path and method == "POST" and path.endswith("/cancel"):
                cancel_request = schema("ingestion_cancel_request.schema.json")
                if status == 422:
                    assert not cancel_request.is_valid(sent)
                    assert body["error"]["code"] == "REQUEST_VALIDATION_FAILED"
                else:
                    cancel_request.validate(sent)
                if status == 200:
                    validate_http("ingestion_cancel_result", body)
                    assert body["run_id"] == path.split("/")[-2]
                    assert [item["document_id"] for item in body["documents"]] == sent["document_ids"]
                if status == 404:
                    assert body["error"]["code"] == "INGESTION_RUN_NOT_FOUND"
            if "/ingestions/" in path and method == "GET" and status == 200:
                assert_run(body, path.rsplit("/", 1)[1])
            if path.endswith("/ingestion-status") and status == 200:
                validate_http("document_ingestion_status", body)
                assert body["document_id"] == path.split("/")[-2]
            if path.endswith("/exists") and status == 200:
                validate_http("document_exists", body)
                assert body["document_id"] == path.split("/")[-2]
            if path.endswith(":retire") and status == 200:
                validate_http("document_retire", body)
                assert body["document_id"] == path.rsplit("/", 1)[1].removesuffix(":retire")
            if path.endswith("/documents") and status == 200:
                validate_http("document_list", body)
                ids = [item["document_id"] for item in body["documents"]]
                assert ids == sorted(set(ids))
                limit = HTTP_SCHEMA["$defs"]["document_list_query"]["properties"]["limit"]["default"]
                query = {key: values[0] for key, values in parse_qs(url.query).items()}
                if "limit" in query:
                    query["limit"] = int(query["limit"])
                validate_http("document_list_query", query)
                assert len(ids) <= query.get("limit", limit)
            if path.endswith("/queries"):
                schema("inference_request.schema.json").validate(sent)
                if status == 200:
                    validate_filters(sent.get("filters", []), index["filters"], "/filters")
                    validate_http("inference_response", body)
                    assert body["config_revision"] == response["headers"]["X-Config-Revision"]
                    assert body["index_generation"] == response["headers"].get("X-Index-Generation")
                    if body["index_generation"] is None:
                        assert "X-Index-Generation" not in response["headers"]
                    assert body["query_variants"] == [sent["query"]]
                    for context in body["contexts"]:
                        assert context["ori_query"] == context["query"] == sent["query"]
                        assert context["filters"] == (
                            initial_config["pipelines"]["inference"].get("fixed_filters", [])
                            + sent.get("filters", [])
                        )
                        for result in context["result_sets"]:
                            for item in result["items"]:
                                assert all(name in item["data"]["structdata"] for name, field in fields.items()
                                           if field.required)

    document, = next(item["request"]["body"]["documents"] for item in happy
                     if item["request"]["path"].endswith("/ingestions"))
    query_response = next(item["response"]["body"] for item in happy if item["request"]["path"].endswith("/queries"))
    response_check = Draft202012Validator(
        {"$ref": f'{HTTP_SCHEMA["$id"]}#/$defs/inference_response'}, registry=REGISTRY
    )
    assert not response_check.is_valid(query_response["contexts"])
    assert not response_check.is_valid({k: v for k, v in query_response.items() if k != "index_generation"})
    assert not response_check.is_valid({k: v for k, v in query_response.items() if k != "query_variants"})
    assert not response_check.is_valid({**query_response, "query_variants": []})
    assert not response_check.is_valid({**query_response, "contexts": query_response["contexts"] * 2})
    final_context = query_response["contexts"][0]
    final_set = final_context["result_sets"][0]
    for result_sets in ([], [final_set, final_set], [{**final_set, "key": "retrieval"}]):
        assert not response_check.is_valid({**query_response, "contexts": [{**final_context, "result_sets": result_sets}]})
    validate_http("inference_response", {**query_response, "query_variants": ["散熱孔怎麼清潔？", "如何清理散熱孔"]})
    validate_http("inference_response", {**query_response, "index_generation": None, "warnings": []})

    document_check = schema("document.schema.json")
    document_check.validate({"document_id": "設" * 85 + "a"})
    for bad_id in ("", "設" * 86, "a\nb", "a\u0085b", "a\ud800"):
        assert not document_check.is_valid({"document_id": bad_id})
    candidate = query_response["contexts"][0]["result_sets"][0]["items"][0]["data"]
    listing = next(item["response"]["body"]["documents"] for item in happy
                   if urlsplit(item["request"]["path"]).path.endswith("/documents"))
    assert candidate["document_id"] == document["document_id"]
    assert "source_revision" not in document and "source_revision" not in candidate
    assert listing == [{"document_id": document["document_id"], "source_revisions": []}]

    (initial_preview, initialize_ingestion, query_while_disabled, blocked_initialization, inference_preview,
     attach_inference, detach_ingestion, after_detach, ingest_while_disabled,
     query_while_ingest_disabled) = scenarios["pipeline_deployment"]
    assert initial_preview["request"]["body"]["runtime_ref"] == inference_preview["request"]["body"]["runtime_ref"]
    ingestion_only = initialize_ingestion["response"]["body"]
    assert ingestion_only["can_ingest"] and not ingestion_only["can_query"]
    assert query_while_disabled["response"]["body"]["error"]["code"] == "PIPELINE_NOT_ENABLED"
    assert blocked_initialization["response"]["body"]["index_impact"]["action"] == "blocked"
    both = attach_inference["response"]["body"]
    assert both["can_ingest"] and both["can_query"]
    assert urlsplit(detach_ingestion["request"]["path"]).query == "pipeline=ingestion"
    assert detach_ingestion["response"]["status"] == 204
    inference_only = after_detach["response"]["body"]
    assert not inference_only["can_ingest"] and inference_only["can_query"]
    assert ingestion_only["index_generation"] == both["index_generation"] == inference_only["index_generation"]
    assert ingest_while_disabled["response"]["body"]["error"]["code"] == "PIPELINE_NOT_ENABLED"
    assert query_while_ingest_disabled["response"]["status"] == 200

    stale_pipeline, stale_query = scenarios["pipeline_revision_mismatch"]
    stale_status = stale_pipeline["response"]["body"]
    assert stale_status["pipelines"]["inference"]["loaded"] and not stale_status["can_query"]
    assert stale_status["pipelines"]["inference"]["config_revision"] != stale_status["active_config_revision"]
    assert stale_query["response"]["status"] == 503
    assert stale_query["response"]["body"]["error"]["code"] == "PIPELINE_NOT_READY"

    put = next(item["response"]["body"] for item in happy if item["request"]["method"] == "PUT")
    updates = [item["response"]["body"] for item in scenarios["reuse_and_rebuild"]
               if item["request"]["method"] == "PUT" and item["response"]["status"] == 200]
    assert put["index_generation"] == updates[0]["index_generation"] != updates[1]["index_generation"]
    assert updates[1] == updates[2]
    for steps, method in ((happy, "DELETE"), (scenarios["reuse_and_rebuild"], "PUT")):
        drain_index = next(i for i, step in enumerate(steps)
                           if step["request"]["path"].endswith(":detach?pipeline=inference"))
        mutation = steps[drain_index + 1]
        assert steps[drain_index]["response"]["status"] == 204
        assert mutation["request"]["method"] == method
        assert mutation["response"]["status"] == (204 if method == "DELETE" else 200)
    reload_status = scenarios["reload_existing_index"][-1]["response"]["body"]
    assert reload_status == put
    restart = scenarios["restart_ingestion_and_update"]
    assert not restart[0]["response"]["body"]["loaded"]
    assert restart[1]["request"]["body"]["runtime_ref"] == restart[2]["request"]["body"]["runtime_ref"]
    assert restart[2]["response"]["body"]["can_ingest"]
    assert restart[-1]["response"]["body"]["active_config_revision"] == "revision-2"
    assert restart[-1]["response"]["body"]["index_generation"] == restart[0]["response"]["body"]["index_generation"]
    reload_unloaded = scenarios["reload_existing_index"][0]["response"]
    assert reload_unloaded["status"] == 200 and not reload_unloaded["body"]["loaded"]
    assert reload_unloaded["body"]["index_generation"] == reload_status["index_generation"]
    before_unload, unload, after_unload = scenarios["unload_existing_index_without_config"]
    assert before_unload["response"] == reload_unloaded
    unload_headers = unload["request"]["headers"]
    assert unload_headers["X-Expected-Config-Revision"] == reload_unloaded["body"]["active_config_revision"]
    assert unload_headers["X-Expected-Index-Generation"] == reload_unloaded["body"]["index_generation"]
    assert unload["response"]["status"] == 204
    assert after_unload["response"]["status"] == 404
    unverified, = scenarios["unload_index_ownership_unverified"]
    assert unverified["request"]["path"] == unload["request"]["path"]
    assert unverified["request"]["headers"]["X-Expected-Index-Generation"] == unload_headers["X-Expected-Index-Generation"]
    assert unverified["response"]["status"] == 409
    assert unverified["response"]["body"]["error"]["code"] == "INDEX_OWNERSHIP_UNVERIFIED"

    before_detach, busy_detach, detach, detach_retry, after_detach = scenarios["detach_shared_index_runtime"]
    before_status = before_detach["response"]["body"]
    assert before_status["loaded"]
    assert busy_detach["response"]["status"] == 409
    assert busy_detach["response"]["body"]["error"]["code"] == "SYSTEM_BUSY"
    assert detach == detach_retry and detach["response"]["status"] == 204
    assert detach["request"]["headers"]["X-Expected-Config-Revision"] == before_status["active_config_revision"]
    assert detach["request"]["headers"]["X-Expected-Index-Generation"] == before_status["index_generation"]
    assert after_detach["response"]["status"] == 200
    after_status = after_detach["response"]["body"]
    assert not after_status["loaded"] and after_status["index_ready"]
    assert after_status["index_generation"] == before_status["index_generation"]
    assert after_status["active_config_revision"] == before_status["active_config_revision"]

    missing_loaded, loaded_preview, recovered_loaded, stale_delete, after_delete = scenarios["recover_index_loaded"]
    assert not missing_loaded["response"]["body"]["index_ready"]
    assert loaded_preview["response"]["body"]["loaded"]
    assert stale_delete["response"]["body"]["error"]["code"] == "INDEX_CONFLICT"
    assert stale_delete["request"]["headers"]["X-Expected-Index-Generation"] == put["index_generation"]
    assert recovered_loaded["response"] == after_delete["response"]
    missing_unloaded, unloaded_preview, recovered_unloaded, replay = scenarios["recover_index_unloaded"]
    assert missing_unloaded["response"]["status"] == 404
    assert not unloaded_preview["response"]["body"]["loaded"]
    assert unloaded_preview["response"]["body"]["active_config_revision"] is None
    assert recovered_unloaded == replay
    assert recovered_unloaded["response"] == recovered_loaded["response"]
    recovery_blocked, = scenarios["recover_index_es_unknown"]
    assert recovery_blocked["response"]["body"]["index_impact"]["code"] == "INDEX_CHECK_UNAVAILABLE"

    _, busy_ingestion, *_ = scenarios["ingestion_status_and_errors"]
    assert busy_ingestion["response"]["status"] == 409
    conflicts = busy_ingestion["response"]["body"]["error"]["conflicts"]
    assert [item["document_id"] for item in conflicts] == ["guide-1", "guide-2", "guide-retiring"]

    first_submit, file_lookup, retry_submit, retry_lookup, original_lookup = (
        scenarios["ingestion_bulk_timeout_and_retry"]
    )
    assert first_submit["request"] == retry_submit["request"]
    original_receipt, retry_receipt = (step["response"] for step in (first_submit, retry_submit))
    assert original_receipt["status"] == retry_receipt["status"] == 202
    original_result, retry_result = (step["response"]["body"] for step in (original_lookup, retry_lookup))
    assert original_receipt["body"]["run_id"] == original_result["run_id"] != retry_result["run_id"]
    assert retry_receipt["body"]["run_id"] == retry_result["run_id"]
    latest = file_lookup["response"]["body"]
    assert latest["run_id"] == original_result["run_id"]
    assert original_result["documents"] == [{key: value for key, value in latest.items() if key != "run_id"}]
    assert original_result["status"] == "failed" and latest["error"]["code"] == "ES_BULK_TIMEOUT"
    assert retry_result["status"] == "completed"
    assert [doc["document_id"] for doc in retry_result["documents"]] == [latest["document_id"]]

    (
        before_cancel, cancel, cancel_retry, after_cancel, cancelled_document,
        busy_after_cancel, after_write, missing_run, invalid_cancel,
    ) = scenarios["cancel_ingestion_documents"]
    assert cancel == cancel_retry and cancel["response"]["status"] == 200
    assert missing_run["response"]["status"] == 404 and invalid_cancel["response"]["status"] == 422
    assert before_cancel["request"] == after_cancel["request"] == after_write["request"]
    before_documents = {item["document_id"]: item for item in before_cancel["response"]["body"]["documents"]}
    after_documents = {item["document_id"]: item for item in after_cancel["response"]["body"]["documents"]}
    final_documents = {item["document_id"]: item for item in after_write["response"]["body"]["documents"]}
    assert before_documents.keys() == after_documents.keys()
    assert before_documents["guide-unselected"] == after_documents["guide-unselected"]
    # guide-running already holds the write permission, so it settles through cancelling.
    expected_results = {"guide-queued": "cancelled", "guide-prewrite": "cancelled", "guide-running": "cancelling"}
    for item in cancel["response"]["body"]["documents"]:
        document_id = item["document_id"]
        if item["result"] == "not_found":
            assert document_id not in after_documents
            continue
        assert item["status"] == after_documents[document_id]["status"]
        if document_id in expected_results:
            assert before_documents[document_id]["status"] in {"queued", "running"}
            assert item["result"] == item["status"] == expected_results[document_id]
        else:
            assert before_documents[document_id] == after_documents[document_id]
    assert cancelled_document["response"]["body"] == {
        "run_id": "ing-cancel", **after_documents["guide-running"]
    }
    assert busy_after_cancel["response"]["status"] == 409
    assert busy_after_cancel["response"]["body"]["error"]["conflicts"] == [
        {"document_id": "guide-running", "status": "cancelling", "run_id": "ing-cancel"}
    ]
    assert after_cancel["response"]["body"]["status"] == "running"
    run_check = Draft202012Validator(
        {"$ref": f'{HTTP_SCHEMA["$id"]}#/$defs/ingestion_run_status'}, registry=REGISTRY
    )
    settling = {**after_cancel["response"]["body"], "documents": [
        item for item in after_cancel["response"]["body"]["documents"] if item["status"] != "queued"
    ]}
    for status in ("partial", "failed", "unknown", "cancelled"):
        assert not run_check.is_valid({**settling, "status": status}), status
    assert after_documents.pop("guide-running")["status"] == "cancelling"
    assert final_documents.pop("guide-running")["status"] == "completed"
    assert after_documents == final_documents

    first, second, invalid = scenarios["document_pagination"]
    next_cursor = first["response"]["body"]["next_cursor"]
    assert next_cursor
    assert parse_qs(urlsplit(second["request"]["path"]).query)["cursor"] == [next_cursor]
    assert second["response"]["body"]["next_cursor"] is None
    last_id_on_first_page = first["response"]["body"]["documents"][-1]["document_id"]
    first_id_on_second_page = second["response"]["body"]["documents"][0]["document_id"]
    assert last_id_on_first_page < first_id_on_second_page
    assert invalid["response"]["status"] == 422
    assert invalid["response"]["body"]["error"]["code"] == "INVALID_CURSOR"
    print(f"PASS: {len(scenarios)} scenarios, {sum(map(len, scenarios.values()))} HTTP exchanges")


if __name__ == "__main__":
    file_request = json.loads((HERE / "file_ingestion.base64.request.json").read_text())
    schema("ingestion_request.schema.json").validate(file_request)
    content = file_request["documents"][0]["content"]
    assert content["media_type"] == "text/plain"
    assert b64decode(content["base64"], validate=True).decode("utf-8") == "定期清潔散熱孔。"
    print("PASS: DEV file upload example carries the original bytes as Base64")
    verify(json.loads((HERE / "runtime_http.examples.json").read_text())["scenarios"])
