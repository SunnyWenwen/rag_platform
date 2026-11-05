"""Bounded offline checks for the Descriptor discussion draft, not an Engine.

Does NOT compile data_rules, normalize applicability/defaults, render UI, execute
components/templates, or prove equivalence with the manually written expected
I/O schemas. Contract files are loaded from this repository without network IO.
"""
from copy import deepcopy
from pathlib import Path
import json

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

HERE = Path(__file__).resolve().parent
SCHEMA = json.loads((HERE / "descriptor.schema.json").read_text())
CATALOG = json.loads((HERE / "catalog.fixture.json").read_text())
CASES = ["parser", "chunker", "embedding", "embedding_template", "remote_segment"]
ORDER = {
    "ingestion": ["import", "parsing", "chunking", "embedding", "indexing"],
    "inference": ["query_transformation", "retrieval", "rerank"],
}
KEYWORDS = {
    "$schema", "$id", "$ref", "$defs", "type", "title", "description", "default",
    "properties", "required", "additionalProperties", "items", "minItems", "maxItems",
    "uniqueItems", "minLength", "maxLength", "minimum", "maximum", "exclusiveMinimum",
    "exclusiveMaximum", "enum", "const", "pattern", "allOf", "if", "then", "else",
}
BIND_KEYWORDS = {
    "type", "const", "enum", "minItems", "maxItems", "minLength", "maxLength",
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
}
MISSING = object()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(name, suffix):
    return json.loads((HERE / f"{name}.{suffix}.json").read_text())


def tokens(path):
    if not path:
        return []
    require(path.startswith("/"), "path must be a JSON Pointer")
    return [p.replace("~1", "/").replace("~0", "~") for p in path[1:].split("/")]


def get(value, path):
    for key in tokens(path):
        if isinstance(value, dict) and key in value:
            value = value[key]
        elif isinstance(value, list) and key.isdigit() and int(key) < len(value):
            value = value[int(key)]
        else:
            return MISSING
    return value


def config_node(schema, path):
    """Only direct properties/items paths used by these fixtures are handled."""
    for key in tokens(path):
        if key == "*":
            require(schema.get("type") == "array", "wildcard must select config array items")
            schema = schema["items"]
        else:
            require(key in schema.get("properties", {}), f"unknown config path: {path}")
            schema = schema["properties"][key]
    return schema


def inspect_schema(schema):
    Draft202012Validator.check_schema(schema)
    if isinstance(schema, bool):
        return
    require(not (set(schema) - KEYWORDS), "unsupported embedded Schema keyword")
    if "$ref" in schema:
        uri = schema["$ref"]
        require(uri.startswith("#/$defs/") or uri.split("#")[0] in CATALOG["contracts"],
                "unregistered Schema reference")
    for group in ["properties", "$defs"]:
        for child in schema.get(group, {}).values():
            inspect_schema(child)
    for key in ["items", "additionalProperties", "if", "then", "else"]:
        if isinstance(schema.get(key), (dict, bool)):
            inspect_schema(schema[key])
    for child in schema.get("allOf", []):
        inspect_schema(child)


def inspect_values(value, config_schema, item_schema=None):
    if isinstance(value, dict):
        if set(value) == {"value"}:
            return
        if set(value) == {"scope", "path"}:
            require("*" not in tokens(value["path"]), "value path cannot use a wildcard")
            if value["scope"] == "config":
                config_node(config_schema, value["path"])
            elif value["scope"] == "item":
                require(item_schema is not None, "item reference outside for_each")
                config_node(item_schema, value["path"])
        else:
            for key, child in value.items():
                if key != "schema":
                    inspect_values(child, config_schema, item_schema)
    elif isinstance(value, list):
        for child in value:
            inspect_values(child, config_schema, item_schema)


def validate_descriptor(descriptor):
    Draft202012Validator(SCHEMA).validate(descriptor)
    scope = descriptor["scope"]
    order = ORDER[scope["pipeline"]]
    positions = [order.index(m) for m in scope["modules"]]
    require(positions == list(range(positions[0], positions[0] + len(positions))),
            "noncontiguous or reversed modules")
    config_schema = descriptor["config_schema"]
    inspect_schema(config_schema)
    require(config_schema.get("type") == "object", "config_schema root must be object")
    for side in ["input", "output"]:
        boundary = descriptor["io"][side]
        require(boundary["contract_ref"] in CATALOG["contracts"], "unknown boundary Contract")
        require(side == "output" or not boundary.get("inherit"), "input cannot inherit itself")
        if "constraints" in boundary:
            inspect_schema(boundary["constraints"])
    # Only the four ingestion boundary types represented by these examples.
    ing, parsed, chunk = list(CATALOG["contracts"])
    inputs = {"parsing": (ing, "direct"), "chunking": (parsed, "list"), "embedding": (chunk, "list")}
    outputs = {"parsing": (parsed, "list"), "chunking": (chunk, "list"), "embedding": (chunk, "list")}
    for side, expected in [("input", inputs.get(scope["modules"][0])),
                           ("output", outputs.get(scope["modules"][-1]))]:
        if expected:
            b = descriptor["io"][side]
            require((b["contract_ref"], b["shape"]) == expected, "wrong Module boundary")
    for collection in ["data_rules", "option_sources", "rules", "resources"]:
        ids = [r["id"] for r in descriptor.get(collection, [])]
        require(len(ids) == len(set(ids)), f"duplicate {collection} id")
    sources = {s["id"]: s for s in descriptor.get("option_sources", [])}
    hints = descriptor.get("ui_hints", {})
    for path in hints.get("order", []):
        config_node(config_schema, path)
    for group in hints.get("groups", []):
        for path in group["fields"]:
            config_node(config_schema, path)
    for path, field in hints.get("fields", {}).items():
        config_node(config_schema, path)
        if "option_source" in field:
            require(field["option_source"] in sources, "unknown option source id")
            require(sources[field["option_source"]]["target"] == path, "option source target mismatch")
    for source in sources.values():
        config_node(config_schema, source["target"])
    for cap in descriptor.get("capabilities", {}).values():
        for declaration in cap:
            if "when" in declaration:
                inspect_values(declaration["when"], config_schema)
    for resource in descriptor.get("resources", []):
        if "when" in resource:
            inspect_values(resource["when"], config_schema)
        for key in ["service_parameter", "profile_parameter"]:
            if key in resource:
                config_node(config_schema, resource[key])
    for rule in descriptor.get("data_rules", []):
        item_schema = None
        if "for_each" in rule:
            node = config_node(config_schema, rule["for_each"])
            require(node.get("type") == "array", "for_each must select config array")
            item_schema = node["items"]
        inspect_values(rule, config_schema, item_schema)
        if "schema" in rule:
            inspect_schema(rule["schema"])
        for binding in rule.get("schema_bindings", []):
            parts = tokens(binding["path"])
            require(parts and parts[-1] in BIND_KEYWORDS, "forbidden schema binding keyword")
            parent = "/" + "/".join(binding["path"][1:].split("/")[:-1]) if len(parts) > 1 else ""
            require(isinstance(get(rule["schema"], parent), dict), "schema binding parent absent")
    for rule in descriptor.get("rules", []):
        config_node(config_schema, rule["target"])
        item_schema = None
        if "for_each" in rule:
            node = config_node(config_schema, rule["for_each"])
            require(node.get("type") == "array", "rule for_each must select array")
            item_schema = node["items"]
        inspect_values(rule, config_schema, item_schema)
        if rule["kind"] == "unique_by":
            node = config_node(config_schema, rule["target"])
            require(node.get("type") == "array", "unique_by must select array")
            config_node(node["items"], rule["item_path"])


def value_of(expr, config, item):
    if "value" in expr:
        return expr["value"]
    source = {"config": config, "item": item, "context": CATALOG["facts"]}[expr["scope"]]
    return get(source, expr["path"])


def predicate(expr, config, item):
    if "all" in expr:
        return all(predicate(p, config, item) for p in expr["all"])
    if "any" in expr:
        return any(predicate(p, config, item) for p in expr["any"])
    if "not" in expr:
        return not predicate(expr["not"], config, item)
    a = value_of(expr["left"], config, item)
    if expr["op"] == "exists":
        return a is not MISSING
    b = value_of(expr["right"], config, item)
    require(a is not MISSING and b is not MISSING, "unresolved value")
    return {"eq": lambda: a == b, "ne": lambda: a != b, "lt": lambda: a < b,
            "lte": lambda: a <= b, "gt": lambda: a > b, "gte": lambda: a >= b,
            "in": lambda: a in b, "contains": lambda: b in a}[expr["op"]]()


def validate_config(descriptor, config):
    Draft202012Validator(descriptor["config_schema"]).validate(config)
    for rule in descriptor.get("rules", []):
        if rule["kind"] == "unique_by":
            values = [get(v, rule["item_path"]) for v in get(config, rule["target"])]
            require(all(v is not MISSING for v in values), "unique_by value absent")
            require(len(values) == len({json.dumps(v, sort_keys=True) for v in values}), rule["code"])
        elif rule["kind"] == "constraint":
            items = get(config, rule["for_each"]) if "for_each" in rule else [None]
            for item in items:
                require(predicate(rule["assert"], config, item), rule["code"])
    # Check names/known binding values only, not schema construction or copy semantics.
    names = set()
    for rule in descriptor.get("data_rules", []):
        items = get(config, rule["for_each"]) if "for_each" in rule else [None]
        for item in items:
            if "when" in rule and not predicate(rule["when"], config, item):
                continue
            name = value_of(rule["name"], config, item)
            require(isinstance(name, str) and bool(name.strip()), "invalid field name")
            if rule["side"] == "output":
                key = (rule["target"], name)
                require(key not in names, "duplicate output field")
                names.add(key)
            for binding in rule.get("schema_bindings", []):
                require(value_of(binding["value"], config, item) is not MISSING, "unresolved schema binding")


def registry():
    result = Registry()
    for uri, entry in CATALOG["contracts"].items():
        data = json.loads((HERE / entry["file"]).read_text())
        result = result.with_resource(uri, Resource.from_contents(data))
    return result


def validate_data(name, side, data):
    schema = read(name, f"expected_{side}.schema")
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, registry=registry()).validate(data)


def must_fail(label, callback):
    try:
        callback()
    except Exception as exc:
        if not isinstance(exc, ValueError):
            from jsonschema.exceptions import ValidationError, SchemaError
            if not isinstance(exc, (ValidationError, SchemaError)):
                raise
        return
    raise AssertionError(f"negative case accepted: {label}")


def main():
    Draft202012Validator.check_schema(SCHEMA)
    for name in CASES:
        d, c = read(name, "descriptor"), read(name, "config")
        validate_descriptor(d)
        validate_config(d, c)
        for side in ["input", "output"]:
            validate_data(name, side, read(name, side))
    negatives = 0
    def neg(label, callback):
        nonlocal negatives
        must_fail(label, callback)
        negatives += 1
    def bad_descriptor(label, mutate):
        d = read("embedding", "descriptor")
        mutate(d)
        neg(label, lambda: validate_descriptor(d))
    bad_descriptor("missing version", lambda d: d.pop("descriptor_version"))
    bad_descriptor("unknown root", lambda d: d.update(python="eval(...)"))
    bad_descriptor("wrong pipeline", lambda d: d["scope"].update(pipeline="inference"))
    bad_descriptor("gap", lambda d: d["scope"].update(modules=["parsing", "embedding"]))
    bad_descriptor("wrong boundary", lambda d: d["io"]["input"].update(contract_ref=list(CATALOG["contracts"])[1]))
    bad_descriptor("unknown action", lambda d: d["data_rules"][0].update(action="python"))
    bad_descriptor("unknown rule key", lambda d: d["data_rules"][0].update(code="import os"))
    bad_descriptor("bad config path", lambda d: d["data_rules"][0].update(name={"scope":"config","path":"/missing"}))
    bad_descriptor("item out of scope", lambda d: d["data_rules"][0].pop("for_each"))
    bad_descriptor("forbidden binding", lambda d: d["data_rules"][1]["schema_bindings"][0].update(path="/$ref"))
    bad_descriptor("unknown widget", lambda d: d["ui_hints"]["fields"]["/mappings"].update(widget="arbitrary_react"))
    bad_descriptor("bad UI path", lambda d: d["ui_hints"]["fields"].update({"/mappings/*/wrong":{"widget":"text"}}))
    bad_descriptor("unknown option source", lambda d: d["ui_hints"]["fields"]["/mappings/*/source_field"].update(option_source="missing"))
    bad_descriptor("unknown contract", lambda d: d["io"]["input"].update(contract_ref="https://unregistered.invalid/schema"))
    bad_descriptor("unregistered data ref", lambda d: d["data_rules"][1]["schema"].update({"$ref":"https://unregistered.invalid/schema"}))
    bad_descriptor("invalid schema type", lambda d: d["config_schema"]["properties"]["profile_id"].update(type="text"))
    bad_descriptor("duplicate rule id", lambda d: d["data_rules"][1].update(id=d["data_rules"][0]["id"]))
    bad_descriptor("unsupported embedded keyword", lambda d: d["config_schema"].update(unevaluatedProperties=False))
    def bad_config(label, name, mutate):
        d, c = read(name,"descriptor"), read(name,"config")
        mutate(c)
        neg(label, lambda: validate_config(d,c))
    bad_config("duplicate vector", "embedding", lambda c:c["mappings"][1].update(output_name="text"))
    bad_config("empty mappings", "embedding", lambda c:c.update(mappings=[]))
    bad_config("unknown mapping key", "embedding", lambda c:c["mappings"][0].update(url="https://example.invalid"))
    bad_config("wrong name type", "embedding", lambda c:c["mappings"][0].update(output_name=12))
    bad_config("blank name", "embedding", lambda c:c["mappings"][0].update(output_name=" "))
    bad_config("missing profile", "embedding", lambda c:c.pop("profile_id"))
    bad_config("bad overlap", "chunker", lambda c:c.update(overlap_tokens=c["max_tokens"]))
    bad_config("colliding original", "chunker", lambda c:c.update(original_field="text"))
    bad_config("duplicate parser output", "parser", lambda c:c["mappings"][1].update(output_field="text"))
    def bad_data(label,name,side,mutate):
        data=read(name,side)
        mutate(data)
        neg(label,lambda:validate_data(name,side,data))
    bad_data("missing vector","embedding","output",lambda a:a[0]["vectors"].pop("summary_vector"))
    bad_data("wrong vector source","embedding","output",lambda a:a[0]["vectors"]["text"].update(source_field="summary"))
    bad_data("wrong dimension","embedding","output",lambda a:a[0]["vectors"]["text"]["values"].pop())
    bad_data("wrong profile","embedding","output",lambda a:a[0]["vectors"]["text"].update(embedding_profile_id="different"))
    bad_data("numeric embedding input","embedding","input",lambda a:a[0]["fields"].update(summary=12))
    bad_data("missing parser body","parser","input",lambda a:a["content"].pop("body"))
    bad_data("wrong parser page","parser","output",lambda a:a[0]["units"][0].update(page="one"))
    bad_data("missing copied title","chunker","output",lambda a:a[0]["fields"].pop("title"))
    bad_data("unknown Chunk root","chunker","output",lambda a:a[0].update(extra=True))
    neg("remote wrong boundary data", lambda:validate_data("remote_segment","output",read("parser","output")))
    print(json.dumps({"descriptors":len(CASES),"configs":len(CASES),"io_samples":len(CASES)*2,
                      "negative_cases":negatives,"not_checked":["data_rules compilation/equivalence",
                      "full registry/paths/branch semantics","applicability normalization",
                      "real components/resources/UI/Remote deployment"]}))


if __name__ == "__main__":
    main()
