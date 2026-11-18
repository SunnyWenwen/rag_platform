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
DOCUMENT_STATES = ("queued", "running", "completed", "failed", "unknown")


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


def assert_error(body, request_body):
    assert {"code", "message", "module"} <= body.keys() <= {"code", "message", "module", "path", "run_id"}
    assert body["code"] and body["message"]
    if "path" in body:
        assert body["path"].startswith("/") and request_body is not None


def assert_run_document(item):
    assert set(item) == {"document_id", "status", "module", "updated_at", "error"}
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
    elif counts["completed"] and counts["failed"]:
        expected = "partial"
    else:
        expected = "completed" if counts["completed"] else "failed"
    assert body["status"] == expected
    for item in body["documents"]:
        assert_run_document(item)


def assert_system_status(body, system_id):
    assert set(body) == {"system_id", "active_config_revision", "index_ready", "index_generation",
                         "busy", "can_ingest", "can_query"}
    assert body["system_id"] == system_id and body["active_config_revision"]
    assert all(isinstance(body[key], bool) for key in ("busy", "can_ingest", "can_query"))
    assert body["index_ready"] is None or isinstance(body["index_ready"], bool)
    if body["index_ready"]:
        assert body["index_generation"]


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
        for step in steps:
            request, response = step["request"], step["response"]
            url = urlsplit(request["path"])
            path = url.path
            method, sent = request["method"], request.get("body")
            status, body = response["status"], response.get("body")

            if status >= 400:
                assert set(body) == {"error"}
                assert_error(body["error"], sent)
            if status == 204:
                assert "body" not in response and "body_file" not in response
            if "body_file" in response:
                assert path == "/internal/v1/catalog" and response["body_file"] == "runtime_catalog.response.json"
            if path.startswith(SYSTEM_PATH) and method in ("POST", "PUT"):
                system_id = path[len(SYSTEM_PATH):].removesuffix("/config:validate")
                snapshot = {"system_id": system_id, "config_revision": sent.get("config_revision", "preview"),
                            "config": sent["config"]}
                schema("system_config.draft.schema.json").validate(snapshot)
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
                        assert set(body) == {*DRAFT_KEYS, "context_revision", "active_config_revision", "index_impact"}
                        impact = body["index_impact"]
                        assert set(impact) == {"action", "code", "message"}
                        assert impact["action"] in {"create", "reuse", "rebuild_required", "blocked", "none"}
                        previews[body["context_revision"]] = (sent, body)
                    else:
                        draft, preview = previews[sent["context_revision"]]
                        assert all(sent[key] == draft[key] for key in (*DRAFT_KEYS, "config"))
                        assert sent["expected_active_revision"] == preview["active_config_revision"]
                        assert bool(sent.get("allow_rebuild")) == (preview["index_impact"]["action"] == "rebuild_required")
                        assert_system_status(body, system_id)
                        assert body["active_config_revision"] == sent["config_revision"]
            if path.endswith("/ingestions") and status == 202:
                schema("ingestion_request.schema.json").validate(sent)
                assert set(body) == {"run_id", "status", "config_revision", "documents"}
                assert body["status"] == "queued"
                assert response["headers"]["Location"] == f"{path}/{body['run_id']}"
                assert body["documents"] == [{"document_id": doc["document_id"], "status": "queued"}
                                             for doc in sent["documents"]]
            if "/ingestions/" in path and status == 200:
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
