"""Offline acceptance of the Descriptor draft and selected System Config relationships."""
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import json

from jsonschema import Draft202012Validator, ValidationError
from referencing import Registry, Resource

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MODULES = {
    "ingestion": ("parsing", "chunking", "embedding"),
    "inference": ("query_transformation", "retrieval", "rerank"),
}
METHOD_FAMILIES = {
    "import": (("platform",), ("IngestionRequest", "Document")),
    "parsing": (("passthrough", "pdf", "pdf_ocr", "office", "image_ocr", "text", "json"),
                ("Document", "Document[]")),
    "chunking": (("fixed", "recursive", "header_aware"), ("Document[]", "Document[]")),
    "embedding": (("dense",), ("Document[]", "Document[]")),
    "indexing": (("elasticsearch", "local"), ("Document[]", "IndexBinding")),
    "inference_input": (("platform",), ("InferenceRequest", "QueryContext[]")),
    "query_transformation": (("none", "rewrite", "multi_query"),
                             ("QueryContext[]", "QueryContext[]")),
    "retrieval": (("builtin",), ("QueryContext[]", "QueryContext[]")),
    "rerank": (("none", "model_api"), ("QueryContext[]", "QueryContext[]")),
}
FIELD_SOURCES = {"input.structdata", "candidate.structdata", "index_plan.fulltext"}
SCALAR_TYPES = ["string", "integer", "number", "boolean"]


def obj(properties, required=None):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties) if required is None else required,
        "additionalProperties": False,
    }


def array(items):
    return {"type": "array", "items": items}


NAME = {"type": "string", "minLength": 1}
BOOL = {"type": "boolean"}
NAT = {"type": "integer", "minimum": 0}
POS = {"type": "integer", "minimum": 1}
FIELD_RULE = obj({"type": {"enum": SCALAR_TYPES}, "required": BOOL})
DESCRIPTOR_SCHEMA = json.loads((REPO / "schemas/component_descriptor.draft.schema.json").read_text())
SYSTEM_CONFIG_SCHEMA = json.loads((REPO / "schemas/system_config.draft.schema.json").read_text())
BUILTIN_SCHEMA = SYSTEM_CONFIG_SCHEMA["$defs"]["builtin_node"]


@dataclass(frozen=True)
class Field:
    type: str
    required: bool = True


@dataclass(frozen=True)
class Vector:
    source: str
    profile: str
    dimensions: int


class ConfigError(ValueError):
    pass


def fail(code):
    raise ConfigError(code)


def descriptor(module, method, params, io, selectors=None, rules=(), constraints=(), required=None):
    value = {
        "descriptor_version": "0.1-draft", "module": module, "method_id": method,
        "method_version": "1.0.0", "parameters_schema": obj(params, required),
        "io": dict(zip(("input", "output"), io)),
        "option_sources": {"/" + key.lstrip("/"): spec for key, spec in (selectors or {}).items()},
        "data_rules": list(rules), "constraints": list(constraints),
    }
    validate_descriptor(value)
    return value


def path_parts(pointer):
    if not pointer.startswith("/") or any(not segment for segment in pointer[1:].split("/")):
        fail("invalid parameter path:" + pointer)
    return [part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/")]


def schema_at(root, pointer):
    node = root
    for part in path_parts(pointer):
        child = node.get("items") if part == "*" else node.get("properties", {}).get(part)
        if child is None:
            fail("unknown parameter path:" + pointer)
        node = child
    return node


def validate_descriptor(value):
    Draft202012Validator(DESCRIPTOR_SCHEMA).validate(value)
    root = value["parameters_schema"]
    Draft202012Validator.check_schema(root)
    expected_io = METHOD_FAMILIES[value["module"]][1]
    if (value["io"]["input"], value["io"]["output"]) != expected_io:
        fail("invalid module I/O")
    for pointer, spec in value.get("option_sources", {}).items():
        if spec["source"] not in FIELD_SOURCES and {"types", "required"} & spec.keys():
            fail("field filters require a field source")
        if schema_at(root, pointer).get("type") != "string":
            fail("selector must target a string")
    for rule in value.get("data_rules", ()):
        scope = schema_at(root, rule["for_each"]).get("items") if "for_each" in rule else root
        if scope is None:
            fail("for_each must target an array")
        for key in ("source", "target", "profile"):
            if key in rule and schema_at(scope, rule[key]).get("type") != "string":
                fail("data rule must reference a string")
    for rule in value.get("constraints", ()):
        for key in ("left", "right"):
            if schema_at(root, rule[key]).get("type") not in ("integer", "number"):
                fail("lt operands must be numeric")


def selector(source, *types):
    return {"source": source, **({"types": list(types), "required": True} if types else {})}


STRING_INPUT = selector("input.structdata", "string")
CHUNK = descriptor(
    "chunking", "recursive",
    {"split_field": NAME, "output_field": NAME,
     "copy_fields": array(obj({"source_field": NAME, "output_field": NAME})),
     "max_tokens": POS, "overlap_tokens": NAT, "tokenizer_profile_id": NAME},
    ("Document[]", "Document[]"),
    {"split_field": STRING_INPUT, "/copy_fields/*/source_field": selector("input.structdata", *SCALAR_TYPES)},
    [{"op": "declare", "target": "/output_field", "schema": {"type": "string", "required": True}},
     {"op": "copy", "source": "/source_field", "target": "/output_field", "for_each": "/copy_fields"}],
    [{"op": "lt", "left": "/overlap_tokens", "right": "/max_tokens"}],
)
EMBED = descriptor(
    "embedding", "dense",
    {"source_field": NAME, "vector_name": NAME, "profile": NAME},
    ("Document[]", "Document[]"),
    {"source_field": STRING_INPUT, "profile": selector("profiles")},
    [{"op": "vector", "source": "/source_field", "target": "/vector_name", "profile": "/profile"}],
)
INDEX = descriptor(
    "indexing", "local",
    {"persistence": {"const": "memory"}, "fulltext_field": NAME, "vector_name": NAME},
    ("Document[]", "IndexBinding"),
    {"fulltext_field": STRING_INPUT, "vector_name": selector("input.vectors")},
)
RETRIEVE = descriptor(
    "retrieval", "builtin",
    {"vector_name": NAME, "query_profile": NAME, "top_k": POS},
    ("QueryContext[]", "QueryContext[]"),
    {"vector_name": selector("index_plan.vectors"), "query_profile": selector("profiles")},
)
RERANK = descriptor(
    "rerank", "model_api",
    {"text_field": NAME},
    ("QueryContext[]", "QueryContext[]"),
    {"text_field": selector("candidate.structdata", "string")},
)
FIXTURE_DESCRIPTORS = (
    CHUNK, EMBED, INDEX, RETRIEVE, RERANK,
    descriptor("import", "platform",
               {"structdata": {"type": "object", "additionalProperties": FIELD_RULE}},
               ("IngestionRequest", "Document")),
    descriptor("parsing", "passthrough", {}, ("Document", "Document[]")),
    descriptor("inference_input", "platform", {}, ("InferenceRequest", "QueryContext[]")),
    descriptor("query_transformation", "none", {}, ("QueryContext[]", "QueryContext[]")),
    descriptor("rerank", "none", {}, ("QueryContext[]", "QueryContext[]")),
)
REGISTRY = {(d["module"], d["method_id"], d["method_version"]): d for d in FIXTURE_DESCRIPTORS}
PROFILES = {"text-v1": 3, "other-space-v1": 3}

def node(method, **parameters):
    return {"kind": "builtin", "method_id": method, "method_version": "1.0.0",
            "parameters": parameters}


def options(spec, context):
    # An absent dependency and a valid dependency with zero options are distinguishable.
    source = spec["source"]
    if source not in context:
        fail("unresolved:" + source)
    return sorted(name for name, value in context[source].items()
                  if (not spec.get("types") or value.type in spec["types"])
                  and (not spec.get("required") or value.required))


def selected_values(values, pointer):
    current = [values]
    for part in path_parts(pointer):
        if part == "*":
            current = [item for values in current for item in values]
        else:
            current = [value[part] for value in current if part in value]
    return current


def parameters(module, config, context):
    Draft202012Validator(BUILTIN_SCHEMA).validate(config)
    key = module, config["method_id"], config["method_version"]
    if key not in REGISTRY:
        fail("unknown method")
    desc = REGISTRY[key]
    values = config["parameters"]
    Draft202012Validator(desc["parameters_schema"]).validate(values)
    for key, spec in desc.get("option_sources", {}).items():
        selected = selected_values(values, key)
        if selected and any(value not in options(spec, context) for value in selected):
            fail("invalid selection:" + key)
    for rule in desc.get("constraints", ()):
        if not values[rule["left"][1:]] < values[rule["right"][1:]]:
            fail("constraint:lt")
    return desc, values


def data_effects(desc, values, fields, vectors):
    result = {} if desc["module"] == "chunking" else fields.copy()
    vector_result = vectors.copy()
    for rule in desc["data_rules"]:
        if "for_each" in rule:
            for item in values[rule["for_each"][1:]]:
                target = item[rule["target"][1:]]
                if target in result:
                    fail("duplicate field")
                result[target] = fields[item[rule["source"][1:]]]
            continue
        target = values[rule["target"][1:]]
        if rule["op"] == "vector":
            if target in vector_result:
                fail("duplicate vector")
            profile = values[rule["profile"][1:]]
            vector_result[target] = Vector(values[rule["source"][1:]], profile, PROFILES[profile])
        else:
            if target in result:
                fail("duplicate field")
            result[target] = (Field(**rule["schema"]) if rule["op"] == "declare"
                              else fields[values[rule["source"][1:]]])
    return result, vector_result


def context(fields, vectors):
    return {"input.structdata": fields, "input.vectors": vectors, "profiles": PROFILES}


def compile_index(fields, vectors, config):
    _, params = parameters("indexing", config, context(fields, vectors))
    return {"fulltext": {params["fulltext_field"]: fields[params["fulltext_field"]]},
            "vectors": {params["vector_name"]: vectors[params["vector_name"]]}}


def compile_retrieval(index_plan, config):
    _, params = parameters("retrieval", config, {"index_plan.vectors": index_plan["vectors"],
                                                  "profiles": PROFILES})
    vector = index_plan["vectors"][params["vector_name"]]
    if params["query_profile"] != vector.profile:
        fail("incompatible query profile")


def binding_fixture():
    return {
        "artifact_type": "builtin.local/v1",
        "target": {"collection": "test-only"},
        "fulltext_fields": ["text"],
        "filter_fields": [],
        "vector_bindings": {
            "text": {"source_field": "text", "embedding_profile_id": "text-v1", "dimensions": 3},
        },
    }


def check_runtime_binding(index_plan, binding):
    schema = json.loads((REPO / "schemas/index_binding.schema.json").read_text())
    Draft202012Validator(schema).validate(binding)
    vectors = {
        name: Vector(entry["source_field"], entry["embedding_profile_id"], entry["dimensions"])
        for name, entry in binding.get("vector_bindings", {}).items()
    }
    if (set(binding.get("fulltext_fields", [])) != set(index_plan["fulltext"])
            or vectors != index_plan["vectors"]):
        fail("binding mismatch")


def remote_contract(pipeline, start, end):
    order = MODULES.get(pipeline, ())
    if start not in order or end not in order or order.index(start) > order.index(end):
        fail("invalid remote range")
    covered = order[order.index(start):order.index(end) + 1]
    if pipeline == "inference":
        return covered, "QueryContext[]", "QueryContext[]", set()
    declarations = set()
    if any(module in covered for module in ("parsing", "chunking")):
        declarations.add("structdata")
    if "embedding" in covered:
        declarations.add("vectors")
    return covered, "Document" if start == "parsing" else "Document[]", "Document[]", declarations


def remote_effects(start, end, declarations, previous_fields=None):
    _, _, _, expected = remote_contract("ingestion", start, end)
    if set(declarations) != expected:
        fail("wrong remote declarations")
    fields = declarations.get("structdata", previous_fields)
    if fields is None:
        fail("missing upstream schema")
    vectors = declarations.get("vectors", {})
    for vector in vectors.values():
        field = fields.get(vector.source)
        if field != Field("string"):
            fail("invalid remote vector source")
        if PROFILES.get(vector.profile) != vector.dimensions:
            fail("remote profile dimension mismatch")
    return fields, vectors


def check_coverage(covered, active_nodes):
    if set(covered) & set(active_nodes):
        fail("overlapping effective nodes")


TESTS = []


def case(name):
    def register(test):
        TESTS.append((name, test))
        return test
    return register


def rejects(test, expected):
    try:
        test()
    except (ConfigError, ValidationError) as error:
        if expected != str(error) and expected != type(error).__name__:
            raise AssertionError(f"expected {expected}, got {error}") from error
    else:
        raise AssertionError("expected rejection: " + expected)


UPSTREAM = {"body": Field("string"), "title": Field("string"),
            "page": Field("integer"), "summary": Field("string", False)}
CHUNK_CONFIG = node("recursive", split_field="body", output_field="text",
                    copy_fields=[{"source_field": "title", "output_field": "title"}],
                    max_tokens=500, overlap_tokens=50, tokenizer_profile_id="fixture")
EMBED_CONFIG = node("dense", source_field="text", vector_name="text", profile="text-v1")
INDEX_CONFIG = node("local", persistence="memory", fulltext_field="text", vector_name="text")
RETRIEVAL_CONFIG = node("builtin", vector_name="text", query_profile="text-v1", top_k=10)
RERANK_CONFIG = node("model_api", text_field="text")


def builtin_output(chunk_config=CHUNK_CONFIG):
    desc, values = parameters("chunking", chunk_config, context(UPSTREAM, {}))
    fields, vectors = data_effects(desc, values, UPSTREAM, {})
    desc, values = parameters("embedding", EMBED_CONFIG, context(fields, vectors))
    return data_effects(desc, values, fields, vectors)


def effective_nodes(pipeline, nodes):
    order = (("import", *MODULES["ingestion"], "indexing") if pipeline == "ingestion"
             else ("inference_input", *MODULES["inference"]))
    covered = set()
    for module in order:
        if module in covered:
            continue
        config = nodes.get(module)
        if config is None:
            fail("missing effective module:" + module)
        if config["kind"] == "remote":
            segment, _, _, _ = remote_contract(pipeline, module, config["through"])
            check_coverage(segment[1:], nodes)
            covered.update(segment)
        yield module, config


def field_specs(values):
    return {name: Field(**value) for name, value in values.items()}


def compile_local_example(snapshot):
    """Exercise the Local Search examples using the offline descriptor registry."""
    Draft202012Validator(SYSTEM_CONFIG_SCHEMA).validate(snapshot)
    pipelines = snapshot["config"]["pipelines"]
    fields, vectors = {}, {}
    for module, config in effective_nodes("ingestion", pipelines["ingestion"]):
        if config["kind"] == "remote":
            output = config["output"]
            declarations = {}
            if "structdata" in output:
                declarations["structdata"] = field_specs(output["structdata"])
            if "vectors" in output:
                declarations["vectors"] = {
                    name: Vector(entry["source_field"], entry["embedding_profile_id"], entry["dimensions"])
                    for name, entry in output["vectors"].items()
                }
            fields, vectors = remote_effects(module, config["through"], declarations, fields)
        elif module == "indexing":
            index = compile_index(fields, vectors, config)
        else:
            desc, values = parameters(module, config, context(fields, vectors))
            if module == "import":
                fields = field_specs(values["structdata"])
            else:
                fields, vectors = data_effects(desc, values, fields, vectors)

    for module, config in effective_nodes("inference", pipelines["inference"]):
        if config["kind"] == "remote":
            fail("example compiler only supports builtin Inference")
        if module == "retrieval":
            compile_retrieval(index, config)
        else:
            parameters(module, config, {"candidate.structdata": fields})
    return fields, vectors, index


def local_snapshot(mode):
    return json.loads((HERE / f"local_memory.{mode}.json").read_text())


@case("published Local Search examples compile to the same index and candidate contracts")
def _():
    builtin = local_snapshot("builtin")
    remote = local_snapshot("remote_parsing")
    assert builtin["system_id"] == remote["system_id"]
    assert builtin["config_revision"] != remote["config_revision"]
    builtin["config"]["pipelines"]["ingestion"].pop("parsing")
    parser = remote["config"]["pipelines"]["ingestion"].pop("parsing")
    assert builtin["config"] == remote["config"]
    assert remote_contract("ingestion", "parsing", parser["through"])[1:3] == ("Document", "Document[]")
    fields, vectors, index = compile_local_example(local_snapshot("builtin"))
    assert (fields, vectors, index) == compile_local_example(local_snapshot("remote_parsing"))
    assert fields == {"text": Field("string"), "title": Field("string")}
    assert vectors == {"text": Vector("text", "text-v1", 3)}
    check_runtime_binding(index, binding_fixture())


@case("System Config rejects extra deployment keys, forbidden scopes and invalid effective settings")
def _():
    bad = local_snapshot("remote_parsing")
    pipeline = bad["config"]["pipelines"]["ingestion"]
    parser = pipeline["parsing"]
    parser["endpoint"] = "https://example.invalid/parse"
    rejects(lambda: compile_local_example(bad), "ValidationError")
    del parser["endpoint"]
    parser["through"] = "chunking"
    rejects(lambda: compile_local_example(bad), "overlapping effective nodes")
    parser["through"] = "parsing"
    parser["output"]["vectors"] = {}
    rejects(lambda: compile_local_example(bad), "wrong remote declarations")
    del parser["output"]["vectors"]
    del parser["output"]["structdata"]["body"]
    rejects(lambda: compile_local_example(bad), "invalid selection:/split_field")
    pipeline["indexing"] = deepcopy(parser)
    rejects(lambda: compile_local_example(bad), "ValidationError")
    bad = local_snapshot("builtin")
    del bad["config"]["pipelines"]["ingestion"]["chunking"]
    rejects(lambda: compile_local_example(bad), "missing effective module:chunking")


@case("builtin flow uses one derived set of fields through Rerank")
def _():
    fields, vectors = builtin_output()
    assert fields == {"text": Field("string"), "title": Field("string")}
    assert vectors == {"text": Vector("text", "text-v1", 3)}
    index = compile_index(fields, vectors, INDEX_CONFIG)
    compile_retrieval(index, RETRIEVAL_CONFIG)
    check_runtime_binding(index, binding_fixture())
    parameters("rerank", RERANK_CONFIG, {"candidate.structdata": fields})


@case("field picker excludes optional and integer fields")
def _():
    assert options(CHUNK["option_sources"]["/split_field"], context(UPSTREAM, {})) == ["body", "title"]
    for field in ("summary", "page", "missing"):
        rejects(lambda: parameters("chunking", node("recursive", **{
            **CHUNK_CONFIG["parameters"], "split_field": field}), context(UPSTREAM, {})),
            "invalid selection:/split_field")


@case("renaming output invalidates the old Embedding choice")
def _():
    config = deepcopy(CHUNK_CONFIG)
    config["parameters"]["output_field"] = "body"
    desc, params = parameters("chunking", config, context(UPSTREAM, {}))
    fields, vectors = data_effects(desc, params, UPSTREAM, {})
    assert options(EMBED["option_sources"]["/source_field"], context(fields, vectors)) == ["body", "title"]
    rejects(lambda: parameters("embedding", EMBED_CONFIG, context(fields, vectors)),
            "invalid selection:/source_field")


@case("copy preserves type and catches collisions")
def _():
    config = deepcopy(CHUNK_CONFIG)
    config["parameters"]["copy_fields"] = [{"source_field": "page", "output_field": "page"}]
    desc, params = parameters("chunking", config, context(UPSTREAM, {}))
    fields, _ = data_effects(desc, params, UPSTREAM, {})
    assert fields["page"] == Field("integer")
    params["copy_fields"][0]["output_field"] = "text"
    rejects(lambda: data_effects(desc, params, UPSTREAM, {}), "duplicate field")
    params["copy_fields"][0]["source_field"] = "summary"
    rejects(lambda: parameters("chunking", config, context(UPSTREAM, {})),
            "invalid selection:/copy_fields/*/source_field")


@case("unknown method, invalid parameter type and invalid relation fail separately")
def _():
    bad = deepcopy(CHUNK_CONFIG)
    bad["method_version"] = "2.0.0"
    rejects(lambda: parameters("chunking", bad, context(UPSTREAM, {})), "unknown method")
    bad["method_version"] = "1.0.0"
    bad["parameters"]["overlap_tokens"] = "500"
    rejects(lambda: parameters("chunking", bad, context(UPSTREAM, {})), "ValidationError")
    bad["parameters"]["overlap_tokens"] = 500
    rejects(lambda: parameters("chunking", bad, context(UPSTREAM, {})), "constraint:lt")


@case("index plan drives compile-time choices and binding is checked separately")
def _():
    fields, vectors = builtin_output()
    index = compile_index(fields, vectors, INDEX_CONFIG)
    compile_retrieval(index, RETRIEVAL_CONFIG)
    bad = deepcopy(RETRIEVAL_CONFIG)
    bad["parameters"]["query_profile"] = "other-space-v1"
    rejects(lambda: compile_retrieval(index, bad), "incompatible query profile")
    binding = binding_fixture()
    check_runtime_binding(index, binding)
    binding["vector_bindings"]["text"]["dimensions"] = 4
    rejects(lambda: check_runtime_binding(index, binding), "binding mismatch")
    binding["vector_bindings"]["text"]["dimensions"] = "3"
    rejects(lambda: check_runtime_binding(index, binding), "ValidationError")
    binding["vector_bindings"] = {}
    rejects(lambda: check_runtime_binding(index, binding), "binding mismatch")
    rejects(lambda: options(RETRIEVE["option_sources"]["/vector_name"], {}), "unresolved:index_plan.vectors")
    assert options(RETRIEVE["option_sources"]["/vector_name"], {"index_plan.vectors": {}}) == []


@case("all twelve allowed Remote scopes plus invalid and overlapping scopes")
def _():
    assert [remote_contract("ingestion", start, end)[3] for start, end in (
        ("parsing", "parsing"), ("parsing", "chunking"), ("parsing", "embedding"),
        ("chunking", "chunking"), ("chunking", "embedding"), ("embedding", "embedding"),
    )] == [{"structdata"}, {"structdata"}, {"structdata", "vectors"},
           {"structdata"}, {"structdata", "vectors"}, {"vectors"}]
    assert remote_contract("ingestion", "parsing", "embedding")[1:3] == ("Document", "Document[]")
    assert remote_contract("ingestion", "chunking", "embedding")[1:3] == ("Document[]", "Document[]")
    for i, start in enumerate(MODULES["inference"]):
        for end in MODULES["inference"][i:]:
            assert remote_contract("inference", start, end)[1:] == ("QueryContext[]", "QueryContext[]", set())
    for start, end in (("import", "parsing"), ("parsing", "indexing"), ("embedding", "parsing")):
        rejects(lambda: remote_contract("ingestion", start, end), "invalid remote range")
    check_coverage(("parsing", "chunking", "embedding"), ("indexing",))
    rejects(lambda: check_coverage(("parsing", "chunking", "embedding"), ("chunking", "indexing")),
            "overlapping effective nodes")


@case("Remote Parsing-to-Embedding reuses the Indexing contract")
def _():
    fields, vectors = builtin_output()
    remote = {"structdata": fields, "vectors": vectors}
    assert compile_index(*remote_effects("parsing", "embedding", remote), INDEX_CONFIG) == compile_index(
        fields, vectors, INDEX_CONFIG)
    assert remote_effects("embedding", "embedding", {"vectors": vectors}, fields) == (fields, vectors)
    rejects(lambda: remote_effects("parsing", "embedding", {"structdata": fields}),
            "wrong remote declarations")
    rejects(lambda: remote_effects("parsing", "embedding", {"structdata": fields,
            "vectors": {"text": Vector("text", "text-v1", 4)}}), "remote profile dimension mismatch")
    rejects(lambda: remote_effects("parsing", "embedding", {"structdata": {"title": Field("string")},
            "vectors": vectors}), "invalid remote vector source")


@case("published Document and vector envelopes still validate example payloads")
def _():
    base = json.loads((REPO / "schemas/document.schema.json").read_text())
    schema = Draft202012Validator(base)
    examples = REPO / "examples/user_remote_api"
    candidate = json.loads((examples / "remote_ingestion.response.json").read_text())["output"][0]
    schema.validate(candidate)
    bad = deepcopy(candidate)
    bad["structdata"]["text"] = ["invalid", "nested"]
    rejects(lambda: schema.validate(bad), "ValidationError")


@case("descriptor envelope represents all planned builtin method families")
def _():
    for module, (methods, io) in METHOD_FAMILIES.items():
        for method in methods:
            descriptor(module, method, {}, io)


@case("external retrieval candidate uses effective output schema without an IndexBinding")
def _():
    paths = REPO / "schemas"
    document = json.loads((paths / "document.schema.json").read_text())
    query_context = json.loads((paths / "query_context.schema.json").read_text())
    registry = Registry().with_resource(document["$id"], Resource.from_contents(document))
    query = Draft202012Validator(query_context, registry=registry)
    response = json.loads((REPO / "examples/user_remote_api/remote_retrieval.response.json").read_text())
    results = response["output"]
    query.validate(results)
    fields, _ = builtin_output()
    field_schema = obj({name: {"type": value.type} for name, value in fields.items()},
                       [name for name, value in fields.items() if value.required])
    validator = Draft202012Validator({"properties": {"structdata": field_schema}})
    candidate = results[0]["result_sets"][0]["items"][0]["data"]
    validator.validate(candidate)
    parameters("rerank", RERANK_CONFIG, {"candidate.structdata": fields})
    del candidate["structdata"]["text"]
    query.validate(results)
    rejects(lambda: validator.validate(candidate), "ValidationError")


@case("malformed descriptor pointers fail at registration")
def _():
    bad = deepcopy(CHUNK)
    bad["option_sources"]["/split_filed"] = STRING_INPUT
    rejects(lambda: validate_descriptor(bad), "unknown parameter path:/split_filed")
    del bad["option_sources"]["/split_filed"]
    bad["data_rules"][1]["source"] = "/missing"
    rejects(lambda: validate_descriptor(bad), "unknown parameter path:/missing")
    del bad["data_rules"][1]
    bad["constraints"][0]["left"] = "/split_field"
    rejects(lambda: validate_descriptor(bad), "lt operands must be numeric")


@case("nested selector paths use one grammar at registration and evaluation")
def _():
    nested = descriptor("query_transformation", "rewrite_test",
                        {"model": obj({"provider": obj({"model_id": NAME})})},
                        ("QueryContext[]", "QueryContext[]"),
                        {"/model/provider/model_id": selector("models")})
    key = "/model/provider/model_id"
    assert schema_at(nested["parameters_schema"], key)["type"] == "string"
    assert selected_values({"model": {"provider": {"model_id": "draft-llm"}}}, key) == ["draft-llm"]
    assert selected_values({"copy_fields": [{"source_field": "title"}, {"source_field": "page"}]},
                           "/copy_fields/*/source_field") == ["title", "page"]
    rejects(lambda: schema_at(nested["parameters_schema"], "/model//provider"), "invalid parameter path:/model//provider")


@case("unknown module I/O and incompatible selector filters fail at registration")
def _():
    bad = deepcopy(EMBED)
    bad["io"]["input"] = "ArbitraryShape"
    rejects(lambda: validate_descriptor(bad), "invalid module I/O")
    bad = deepcopy(EMBED)
    bad["option_sources"]["/profile"]["types"] = ["string"]
    rejects(lambda: validate_descriptor(bad), "field filters require a field source")


if __name__ == "__main__":
    Draft202012Validator.check_schema(DESCRIPTOR_SCHEMA)
    Draft202012Validator.check_schema(SYSTEM_CONFIG_SCHEMA)
    assert CHUNK == json.loads((HERE / "recursive.descriptor.json").read_text())
    for name, test in TESTS:
        test()
        print("PASS", name)
    print(f"{len(TESTS)} scenario groups passed")
