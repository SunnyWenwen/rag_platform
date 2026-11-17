"""Verify the HTTP Mock fixtures without starting Runtime or any backing service."""
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from validate_descriptor_draft import ConfigError, compile_local_example, validate_filters


HERE = Path(__file__).resolve().parent
SCHEMAS = {path.name: json.loads(path.read_text()) for path in (HERE.parents[1] / "schemas").glob("*.json")}
REGISTRY = Registry().with_resources((schema["$id"], Resource.from_contents(schema)) for schema in SCHEMAS.values())
SYSTEM_PATH = "/internal/v1/systems/"
DRAFT_KEYS = ("runtime_ref", "catalog_revision", "draft_revision")


def schema(name):
    return Draft202012Validator(SCHEMAS[name], registry=REGISTRY)


def assert_error(body, request_body):
    assert {"code", "message", "module"} <= body.keys() <= {"code", "message", "module", "path", "run_id"}
    assert body["code"] and body["message"]
    if "path" in body:
        assert body["path"].startswith("/") and request_body is not None


def assert_run(body, run_id):
    assert body["run_id"] == run_id
    if set(body) == {"run_id", "status"}:
        assert body["status"] == "unknown"
        return
    counts = body["counts"]
    outcomes = ("queued", "running", "completed", "failed", "unknown")
    assert set(counts) == {"total", *outcomes}
    statuses = [item["status"] for item in body["documents"]]
    assert counts["total"] == len(statuses) == sum(counts[state] for state in outcomes)
    assert all(counts[state] == statuses.count(state) for state in outcomes)
    if body["status"] == "partial":
        assert counts["completed"] and counts["failed"]
        assert not (counts["queued"] or counts["running"] or counts["unknown"])
    for item in body["documents"]:
        assert item["document_id"]
        datetime.fromisoformat(item["updated_at"])
        if item["error"] is not None:
            assert_error(item["error"], None)


def assert_system_status(body, system_id):
    assert body["system_id"] == system_id and body["active_config_revision"]
    assert all(isinstance(body[key], bool) for key in ("busy", "can_ingest", "can_query"))
    assert body["index_ready"] is None or isinstance(body["index_ready"], bool)
    if body["index_ready"]:
        assert body["index_generation"]


def verify(scenarios):
    catalog = json.loads((HERE / "w1_catalog.response.json").read_text())
    schema("runtime_catalog.draft.schema.json").validate(catalog)
    published = {(item["module"], item["component_id"], item["component_version"]) for item in catalog["descriptors"]}
    happy = scenarios["happy_path"]
    initial_config = next(item["request"]["body"]["config"] for item in happy if item["request"]["method"] == "PUT")
    fields, _, index = compile_local_example({"system_id": "es-w1-example", "config_revision": "revision-1",
                                               "config": initial_config})

    for steps in scenarios.values():
        previews = {}
        for step in steps:
            request, response = step["request"], step["response"]
            path = urlsplit(request["path"]).path
            method, sent = request["method"], request.get("body")
            status, body = response["status"], response.get("body")

            if status >= 400:
                assert_error(body["error"], sent)
            if "body_file" in response:
                assert path == "/internal/v1/catalog" and response["body_file"] == "w1_catalog.response.json"
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
                assert response["headers"]["Location"] == f"{path}/{body['run_id']}"
                assert body["documents"] == [{"document_id": doc["document_id"], "status": "queued"}
                                             for doc in sent["documents"]]
            if "/ingestions/" in path and status == 200:
                assert_run(body, path.rsplit("/", 1)[1])
            if path.endswith("/queries"):
                schema("inference_request.schema.json").validate(sent)
                if status == 200:
                    validate_filters(sent.get("filters", []), index["filters"], "/filters")
                    schema("query_context.schema.json").validate(body)
                    assert response["headers"]["X-Config-Revision"] == "revision-1"
                    for context in body:
                        assert context["ori_query"] == sent["query"]
                        for result in context["result_sets"]:
                            for item in result["items"]:
                                assert all(name in item["data"]["structdata"] for name, field in fields.items()
                                           if field.required)

    put = next(item["response"]["body"] for item in happy if item["request"]["method"] == "PUT")
    updates = [item["response"]["body"] for item in scenarios["reuse_and_rebuild"]
               if item["request"]["method"] == "PUT" and item["response"]["status"] == 200]
    assert put["index_generation"] == updates[0]["index_generation"] != updates[1]["index_generation"]
    assert updates[1] == updates[2]
    print(f"PASS: {len(scenarios)} scenarios, {sum(map(len, scenarios.values()))} HTTP exchanges")


if __name__ == "__main__":
    verify(json.loads((HERE / "w1_http.examples.json").read_text())["scenarios"])
