"""Verify the HTTP Mock fixtures without starting Runtime or any backing service."""
import json
from dataclasses import asdict
from hashlib import sha256
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from validate_descriptor_draft import ConfigError, compile_local_example, validate_filters


HERE = Path(__file__).resolve().parent
SCHEMAS = {path.name: json.loads(path.read_text()) for path in (HERE.parents[1] / "schemas").glob("*.json")}
REGISTRY = Registry().with_resources((schema["$id"], Resource.from_contents(schema)) for schema in SCHEMAS.values())
SYSTEM_PATH = "/internal/v1/systems/"
DRAFT_KEYS = ("runtime_ref", "catalog_revision", "draft_revision")
APPLY_OPERATIONS = ("initialize", "reload", "update", "recover_index")
DOCUMENT_STATES = ("queued", "running", "completed", "cancelled", "failed", "unknown")
CANCEL_RESULT_STATES = {
    "cancelled": {"cancelled"},
    "already_finished": {"completed", "failed"},
    "not_cancellable": {"unknown"},
    "not_found": {None},
}


def schema(name):
    return Draft202012Validator(SCHEMAS[name], registry=REGISTRY)


def verify_index_fingerprint(fields, vectors):
    expected = json.loads((HERE / "index_fingerprint.v1.example.json").read_text())
    projection, meta = expected["projection"], expected["mapping_meta"]
    definition = SCHEMAS["index_fingerprint.v1.schema.json"]
    projection_check = schema("index_fingerprint.v1.schema.json")
    projection_check.validate(projection)
    Draft202012Validator({"$ref": definition["$id"] + "#/$defs/mapping_meta"}, registry=REGISTRY).validate(meta)

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


def assert_error(body, request_body, *, ingestion_conflicts=False):
    required_fields = {"code", "message", "module"}
    if ingestion_conflicts:
        required_fields.update({"path", "conflicts"})
    assert required_fields <= body.keys() <= required_fields | {"path", "run_id"}
    assert body["code"] and body["message"]
    if "path" in body:
        assert body["path"].startswith("/") and request_body is not None
    if ingestion_conflicts:
        schema("ingestion_request.schema.json").validate(request_body)
        document_ids = [document["document_id"] for document in request_body["documents"]]
        conflicts = body["conflicts"]
        assert isinstance(conflicts, list) and conflicts
        for conflict in conflicts:
            assert {"document_id", "status"} <= conflict.keys() <= {"document_id", "status", "run_id"}
            assert conflict["status"] is None or conflict["status"] in DOCUMENT_STATES
            if "run_id" in conflict:
                assert conflict["status"] is not None
                assert isinstance(conflict["run_id"], str) and conflict["run_id"]
        conflict_ids = [conflict["document_id"] for conflict in conflicts]
        conflict_id_set = set(conflict_ids)
        assert conflict_ids == [document_id for document_id in document_ids if document_id in conflict_id_set]
        first = conflicts[0]
        assert body["path"] == f"/documents/{document_ids.index(first['document_id'])}/document_id"
        assert body.get("run_id") == first.get("run_id")


def assert_run_document(item):
    expected_fields = {"document_id", "status", "module", "updated_at", "error"}
    if item["status"] == "cancelled":
        expected_fields.add("cancellation_pending")
        assert isinstance(item["cancellation_pending"], bool)
    assert set(item) == expected_fields
    assert isinstance(item["document_id"], str) and item["document_id"]
    assert item["status"] in DOCUMENT_STATES
    assert item["module"] is None or isinstance(item["module"], str)
    if item["updated_at"] is not None:
        assert datetime.fromisoformat(item["updated_at"]).utcoffset() is not None
    if item["status"] == "failed":
        assert item["error"] is not None
    if item["error"] is not None:
        assert_error(item["error"], None)


def assert_run(body, run_id):
    assert body["run_id"] == run_id
    if set(body) == {"run_id", "status"}:
        assert body["status"] == "unknown"
        return
    assert set(body) == {"run_id", "status", "config_revision", "counts", "documents"}
    assert isinstance(body["config_revision"], str) and body["config_revision"]
    counts = body["counts"]
    assert set(counts) == {"total", *DOCUMENT_STATES}
    assert all(type(count) is int and count >= 0 for count in counts.values())
    statuses = [item["status"] for item in body["documents"]]
    assert counts["total"] == len(statuses) == sum(counts[state] for state in DOCUMENT_STATES) > 0
    assert all(counts[state] == statuses.count(state) for state in DOCUMENT_STATES)
    if counts["queued"] == counts["total"]:
        expected = "queued"
    elif counts["queued"] or counts["running"]:
        expected = "running"
    elif counts["unknown"]:
        expected = "unknown"
    elif counts["completed"] == counts["total"]:
        expected = "completed"
    elif counts["cancelled"] == counts["total"]:
        expected = "cancelled"
    elif counts["completed"]:
        expected = "partial"
    else:
        expected = "failed"
    assert body["status"] == expected
    for item in body["documents"]:
        assert_run_document(item)


def assert_system_status(body, system_id):
    assert set(body) == {"system_id", "active_config_revision", "index_ready", "index_generation",
                         "loaded", "busy", "can_ingest", "can_query"}
    assert body["system_id"] == system_id and body["active_config_revision"]
    assert all(isinstance(body[key], bool) for key in ("loaded", "busy", "can_ingest", "can_query"))
    assert body["index_ready"] is None or isinstance(body["index_ready"], bool)
    if body["index_ready"]:
        assert body["index_generation"]
    if not body["loaded"]:
        assert body["index_generation"] and body["index_ready"] is not None
        assert not body["can_ingest"] and not body["can_query"]


def verify(scenarios):
    for definition in SCHEMAS.values():
        Draft202012Validator.check_schema(definition)
    catalog = json.loads((HERE / "runtime_catalog.response.json").read_text())
    schema("runtime_catalog.draft.schema.json").validate(catalog)
    published = {(item["module"], item["component_id"], item["component_version"]) for item in catalog["descriptors"]}
    assert len(published) == len(catalog["descriptors"])
    happy = scenarios["happy_path"]
    initial_config = next(item["request"]["body"]["config"] for item in happy if item["request"]["method"] == "PUT")
    fields, vectors, index = compile_local_example({"system_id": "es-example", "config_revision": "revision-1",
                                                    "config": initial_config})
    verify_index_fingerprint(fields, vectors)

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

            if status >= 400:
                assert set(body) == {"error"}
                ingestion_conflicts = (
                    method == "POST" and path.endswith("/ingestions")
                    and status == 409 and body["error"]["code"] == "DOCUMENT_BUSY"
                )
                assert_error(body["error"], sent, ingestion_conflicts=ingestion_conflicts)
            if status == 204:
                assert "body" not in response and "body_file" not in response
            if "body_file" in response:
                assert path == "/internal/v1/catalog" and response["body_file"] == "runtime_catalog.response.json"
            if method == "GET" and status == 200:
                if path == SYSTEM_PATH.rstrip("/"):
                    assert set(body) == {"systems"}
                    for system in body["systems"]:
                        assert_system_status(system, system["system_id"])
                        assert system["loaded"]
                elif path.startswith(SYSTEM_PATH):
                    assert_system_status(body, path[len(SYSTEM_PATH):])
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
                    assert headers["X-Expected-Config-Revision"] and headers["X-Expected-Index-Generation"]
            if system_route and (method == "PUT" or path.endswith("/config:validate")):
                system_id = path[len(SYSTEM_PATH):].removesuffix("/config:validate")
                snapshot = {"system_id": system_id, "config_revision": sent.get("config_revision", "preview"),
                            "config": sent["config"]}
                schema("system_config.draft.schema.json").validate(snapshot)
                operation = sent.get("operation")
                assert operation in APPLY_OPERATIONS or method == "POST" and operation is None
                assert ("recovery_from" in sent) == (operation == "recover_index")
                if operation == "recover_index":
                    previous = sent["recovery_from"]
                    assert set(previous) == {"config_revision", "index_generation"}
                    assert all(isinstance(value, str) and value for value in previous.values())
                    if method == "PUT":
                        assert sent["config_revision"] == previous["config_revision"]
                assert "allow_rebuild" not in sent or operation == "update" and method == "PUT"
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
                        assert set(body) == {*DRAFT_KEYS, "context_revision", "active_config_revision", "loaded",
                                             "index_impact"}
                        assert type(body["loaded"]) is bool
                        if body["loaded"]:
                            assert body["active_config_revision"]
                        impact = body["index_impact"]
                        assert set(impact) == {"action", "code", "message"}
                        assert impact["action"] in {"create", "reuse", "rebuild_required", "recover", "blocked", "none"}
                        previews[body["context_revision"]] = (sent, body)
                    else:
                        draft, preview = previews[sent["context_revision"]]
                        assert all(sent[key] == draft[key] for key in (*DRAFT_KEYS, "config", "operation"))
                        assert sent.get("recovery_from") == draft.get("recovery_from")
                        assert sent["expected_active_revision"] == preview["active_config_revision"]
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
                        assert body["loaded"]
            if path.endswith("/ingestions") and status == 202:
                schema("ingestion_request.schema.json").validate(sent)
                assert set(body) == {"run_id", "status", "config_revision", "documents"}
                assert body["status"] == "queued"
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
                    assert set(body) == {"run_id", "documents"}
                    assert body["run_id"] == path.split("/")[-2]
                    assert [item["document_id"] for item in body["documents"]] == sent["document_ids"]
                    for item in body["documents"]:
                        assert item["status"] in CANCEL_RESULT_STATES[item["result"]]
                        expected_fields = {"document_id", "result", "status"}
                        if item["status"] == "cancelled":
                            expected_fields.add("cancellation_pending")
                            assert isinstance(item["cancellation_pending"], bool)
                        assert set(item) == expected_fields
                if status == 404:
                    assert body["error"]["code"] == "INGESTION_RUN_NOT_FOUND"
            if "/ingestions/" in path and method == "GET" and status == 200:
                assert_run(body, path.rsplit("/", 1)[1])
            if path.endswith("/ingestion-status") and status == 200:
                document = {key: value for key, value in body.items() if key != "run_id"}
                assert_run_document(document)
                assert document["document_id"] == path.split("/")[-2]
                if body["run_id"] is None:
                    assert document["status"] == "unknown"
                    assert all(document[key] is None for key in ("module", "updated_at", "error"))
            if path.endswith("/documents") and status == 200:
                assert set(body) == {"documents", "next_cursor"}
                ids = [item["document_id"] for item in body["documents"]]
                assert ids == sorted(set(ids))
                assert len(ids) <= int(parse_qs(url.query).get("limit", ["100"])[0])
                for item in body["documents"]:
                    assert set(item) == {"document_id", "source_revisions"}
                    revisions = item["source_revisions"]
                    assert isinstance(revisions, list) and all(isinstance(revision, str) and revision for revision in revisions)
                    assert len(revisions) == len(set(revisions))
                assert body["next_cursor"] is None or isinstance(body["next_cursor"], str)
            if path.endswith("/queries"):
                schema("inference_request.schema.json").validate(sent)
                if status == 200:
                    validate_filters(sent.get("filters", []), index["filters"], "/filters")
                    schema("query_context.schema.json").validate(body)
                    assert response["headers"]["X-Config-Revision"] == "revision-1"
                    for context in body:
                        assert context["ori_query"] == sent["query"]
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
    contexts = next(item["response"]["body"] for item in happy if item["request"]["path"].endswith("/queries"))
    candidate = contexts[0]["result_sets"][0]["items"][0]["data"]
    listing = next(item["response"]["body"]["documents"] for item in happy
                   if urlsplit(item["request"]["path"]).path.endswith("/documents"))
    assert candidate["document_id"] == document["document_id"]
    assert "source_revision" not in document and "source_revision" not in candidate
    assert listing == [{"document_id": document["document_id"], "source_revisions": []}]

    put = next(item["response"]["body"] for item in happy if item["request"]["method"] == "PUT")
    updates = [item["response"]["body"] for item in scenarios["reuse_and_rebuild"]
               if item["request"]["method"] == "PUT" and item["response"]["status"] == 200]
    assert put["index_generation"] == updates[0]["index_generation"] != updates[1]["index_generation"]
    assert updates[1] == updates[2]
    reload_status = scenarios["reload_existing_index"][-1]["response"]["body"]
    assert reload_status == put
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

    before_cancel, cancel, cancel_retry, after_cancel, after_write, missing_run, invalid_cancel = (
        scenarios["cancel_ingestion_documents"]
    )
    assert cancel == cancel_retry and cancel["response"]["status"] == 200
    assert missing_run["response"]["status"] == 404 and invalid_cancel["response"]["status"] == 422
    assert before_cancel["request"] == after_cancel["request"] == after_write["request"]
    before_documents = {item["document_id"]: item for item in before_cancel["response"]["body"]["documents"]}
    after_documents = {item["document_id"]: item for item in after_cancel["response"]["body"]["documents"]}
    final_documents = {item["document_id"]: item for item in after_write["response"]["body"]["documents"]}
    assert before_documents.keys() == after_documents.keys()
    assert before_documents["guide-unselected"] == after_documents["guide-unselected"]
    pending_by_document = {"guide-queued": False, "guide-prewrite": False, "guide-running": True}
    for item in cancel["response"]["body"]["documents"]:
        document_id = item["document_id"]
        if item["result"] == "not_found":
            assert document_id not in after_documents
            continue
        assert item["status"] == after_documents[document_id]["status"]
        if document_id in pending_by_document:
            assert before_documents[document_id]["status"] in {"queued", "running"}
            assert item["result"] == "cancelled"
            assert item["cancellation_pending"] == after_documents[document_id]["cancellation_pending"]
            assert item["cancellation_pending"] is pending_by_document[document_id]
        else:
            assert before_documents[document_id] == after_documents[document_id]
    assert after_documents.pop("guide-running")["cancellation_pending"]
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
    verify(json.loads((HERE / "runtime_http.examples.json").read_text())["scenarios"])
