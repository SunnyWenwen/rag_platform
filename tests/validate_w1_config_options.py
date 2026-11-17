"""Replay the W1 HTTP fixtures against the offline Descriptor resolver."""

import json
from pathlib import Path
import re
import sys

from jsonschema import ValidationError

EXAMPLES = Path(__file__).resolve().parents[1] / "examples/system_config"
sys.path.insert(0, str(EXAMPLES))
from validate_descriptor_draft import (
    CHUNK, ConfigError, context, data_effects, field_specs, options, parameters, path_parts,
)


def value_at(value, parts):
    for part in parts:
        if isinstance(value, list):
            index = int(part)
            value = value[index] if index < len(value) else None
        else:
            value = value.get(part) if isinstance(value, dict) else None
    return value


def parsing_input(config):
    fields = {}
    ingestion = config["pipelines"]["ingestion"]
    for module, parameter, instruction in (
        ("import", "/parameters/structdata", "請先宣告 Import 的 structdata。"),
        ("parsing", "", "請先設定可用的 Parsing 方法。"),
    ):
        try:
            descriptor, values = parameters(module, ingestion.get(module), context(fields, {}))
        except (ConfigError, ValidationError):
            issue = {"code": "DEPENDENCY_NOT_READY", "module": module, "message": instruction,
                     "path": f"/config/pipelines/ingestion/{module}{parameter}"}
            return {}, issue
        if module == "import":
            fields = field_specs(values["structdata"])
        else:
            fields, _ = data_effects(descriptor, values, fields, {})
    return fields, None


def option_spec(path):
    root = "/config/pipelines/ingestion/chunking/parameters"
    assert path.startswith(root + "/")
    pattern = re.sub(r"/(?:0|[1-9][0-9]*)(?=/|$)", "/*", path.removeprefix(root))
    return CHUNK["option_sources"][pattern]


def resolve_options(request):
    """Only selectors exercised by these W1 fixtures are modeled here."""
    assert request["method"] == "POST"
    assert request["path"] == "/internal/v1/systems/es-w1-example/config:options"
    body = request["body"]
    spec = option_spec(body["path"])
    target = body["config"]["pipelines"]["ingestion"]["chunking"]
    assert (target["component_id"], target["component_version"]) == ("recursive", "1.0.0")
    versions = {key: body[key] for key in ("runtime_ref", "catalog_revision", "draft_revision")}
    response = {**versions, "context_revision": body["draft_revision"].replace("draft-", "context-"), "options": []}
    fields = {}
    if spec["source"] == "input.structdata":
        fields, issue = parsing_input(body["config"])
        if issue:
            return {"status": 200, "body": {**response, "dependency_issue": issue}}
    candidates = options(spec, context(fields, {}))
    response["options"] = [{"value": name, "enabled": True} for name in candidates]
    current = value_at(body, path_parts(body["path"]))
    if current and current not in candidates:
        response["options"].append(
            {"value": current, "enabled": False, "reason": "目前的候選來源已不包含此選值。"}
        )
    return {"status": 200, "body": response}


def check_builder(steps, expectation):
    paths = list(dict.fromkeys(step["request"]["body"]["path"] for step in steps))
    refresh = [path for path in paths if option_spec(path)["source"] == "input.structdata"
               and expectation["edited_path"].startswith("/config/pipelines/ingestion/import/")]
    assert refresh == expectation["refresh_paths"]
    if "receive_order" not in expectation:
        return
    latest = {step["request"]["body"]["path"]: index for index, step in enumerate(steps)}
    current_revision = expectation["current_draft_revision"]
    applied = []
    for index in expectation["receive_order"]:
        step = steps[index]
        request, response = step["request"]["body"], step["response"]["body"]
        if response["draft_revision"] == current_revision and latest[request["path"]] == index:
            applied.append(index)
    assert applied == expectation["apply_steps"]


if __name__ == "__main__":
    cases = json.loads((EXAMPLES / "w1_config_options.http.json").read_text())
    for name, case in cases.items():
        for step in case["steps"]:
            actual = resolve_options(step["request"])
            assert actual == step["response"], (name, actual, step["response"])
        if "builder" in case:
            check_builder(case["steps"], case["builder"])
        print("PASS", name)
