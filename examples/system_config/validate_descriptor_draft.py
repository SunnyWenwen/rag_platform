"""Offline acceptance of the Descriptor draft and selected System Config relationships."""
from copy import deepcopy
from dataclasses import dataclass, replace
from math import isfinite
from pathlib import Path
import json
import re

from jsonschema import Draft202012Validator, FormatChecker, ValidationError
from referencing import Registry, Resource

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MODULES = {
    "ingestion": ("parsing", "chunking", "embedding"),
    "inference": ("query_transformation", "retrieval", "rerank"),
}
BUILTIN_COMPONENTS = {
    "import": (("platform",), ("IngestionRequest", "Document")),
    "parsing": (("passthrough", "pdf", "pdf_ocr", "office", "image_ocr", "text", "json"),
                ("Document", "Document[]")),
    "chunking": (("recursive", "fixed_size", "header_aware"), ("Document[]", "Document[]")),
    "embedding": (("dense",), ("Document[]", "Document[]")),
    "indexing": (("elasticsearch", "local"), ("Document[]", "IndexBinding")),
    "inference_input": (("platform",), ("InferenceRequest", "QueryContext[]")),
    "query_transformation": (("none", "rewrite"),
                             ("QueryContext[]", "QueryContext[]")),
    "retrieval": (("builtin",), ("QueryContext[]", "QueryContext[]")),
    "rerank": (("none", "model_api"), ("QueryContext[]", "QueryContext[]")),
}
FIELD_SOURCES = {"input.structdata", "candidate.structdata", "candidate.document_fields", "index_plan.fulltext"}


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
DESCRIPTOR_SCHEMA = json.loads((REPO / "schemas/component_descriptor.draft.schema.json").read_text())
BUILDER_FORM_DESCRIPTORS = json.loads((HERE / "builder_form.descriptors.json").read_text())
CATALOG_SCHEMA = json.loads((REPO / "schemas/runtime_catalog.draft.schema.json").read_text())
RUNTIME_CATALOG = json.loads((HERE / "runtime_catalog.response.json").read_text())
SYSTEM_CONFIG_SCHEMA = json.loads((REPO / "schemas/system_config.draft.schema.json").read_text())
DATA_META = json.loads((REPO / "schemas/data_meta.schema.json").read_text())
QUERY_CONTEXT = json.loads((REPO / "schemas/query_context.schema.json").read_text())
SCHEMA_REGISTRY = Registry().with_resources(
    (schema["$id"], Resource.from_contents(schema)) for schema in (DATA_META, QUERY_CONTEXT, DESCRIPTOR_SCHEMA)
)
DATE_FORMATS = {
    kind: Draft202012Validator(DATA_META["$defs"][kind], format_checker=FormatChecker())
    for kind in ("date", "datetime")
}
FILTER_SHAPE = Draft202012Validator({"$ref": QUERY_CONTEXT["$id"] + "#/$defs/filters"}, registry=SCHEMA_REGISTRY)
BUILTIN_SCHEMA = SYSTEM_CONFIG_SCHEMA["$defs"]["builtin_node"]
REMOTE_ADAPTER_VERSIONS = {"1.0.0"}
PARAMETER_EXPRESSION = re.compile(SYSTEM_CONFIG_SCHEMA["$defs"]["parameter_expression"]["pattern"])


@dataclass(frozen=True)
class Field:
    type: str
    required: bool = True
    searchable: bool = False
    filterable: bool = False


@dataclass(frozen=True)
class Vector:
    source: str
    profile: str
    dimensions: int


class ConfigError(ValueError):
    pass


def fail(code):
    raise ConfigError(code)


def descriptor(module, component_id, params, io, selectors=None, rules=(), constraints=(), required=None):
    value = {
        "descriptor_version": "0.2-draft", "module": module, "component_id": component_id,
        "component_version": "1.0.0", "parameters_schema": obj(params, required),
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
    Draft202012Validator(DESCRIPTOR_SCHEMA, registry=SCHEMA_REGISTRY).validate(value)
    root = value["parameters_schema"]
    Draft202012Validator.check_schema(root)
    expected_io = BUILTIN_COMPONENTS[value["module"]][1]
    if "content_media_types" in value["io"] and value["module"] != "parsing":
        fail("content media types require a Parsing Component")
    if (value["io"]["input"], value["io"]["output"]) != expected_io:
        fail("invalid module I/O")
    for pointer, spec in value.get("option_sources", {}).items():
        if spec["source"] not in FIELD_SOURCES and {"types", "required"} & spec.keys():
            fail("field filters require a field source")
        if schema_at(root, pointer).get("type") != "string":
            fail("selector must target a string")
    hints = value.get("ui_hints", {})
    for pointer in (*hints.get("order", ()), *hints.get("advanced", ()),
                    *(field for group in hints.get("groups", ()) for field in group["fields"])):
        schema_at(root, pointer)
    for pointer, control in hints.get("controls", {}).items():
        shape = schema_at(root, pointer)
        if control == "structdata_editor":
            compatible = shape.get("$ref") in (DATA_META["$id"], DATA_META["$id"] + "#/$defs/structdata")
        elif control == "structdata_overrides_editor":
            compatible = shape.get("$ref") == DATA_META["$id"] + "#/$defs/overrides"
        elif control == "vector_checklist":
            source = value.get("option_sources", {}).get(pointer + "/*", {}).get("source")
            compatible = shape.get("type") == "array" and shape.get("items", {}).get("type") == "string" \
                and source == "input.vectors"
        else:
            compatible = (shape.get("type") == "string" and not {"enum", "const"} & shape.keys()
                          and pointer not in value.get("option_sources", {}))
        if not compatible:
            fail("incompatible UI control:" + pointer)
    for pointer, rule in hints.get("visible_when", {}).items():
        schema_at(root, pointer)
        if isinstance(rule, bool):
            continue
        for condition in next(iter(rule.values())):
            if "paths" in condition:
                shapes = [schema_at(root, path) for path in condition["paths"]]
                if any(shape.get("type") != "array" or shape.get("items", {}).get("type") != "string"
                       for shape in shapes):
                    fail("visibility selection count requires string arrays")
            else:
                shape = schema_at(root, condition["path"])
                if "minimum" in condition and shape.get("type") not in ("integer", "number"):
                    fail("visibility minimum requires a number")
                if "equals" in condition and not Draft202012Validator(shape).is_type(
                    condition["equals"], shape.get("type", "null")
                ):
                    fail("visibility equality requires a matching type")
    for rule in value.get("data_rules", ()):
        if rule["op"] == "compose":
            if (schema_at(root, rule["enabled"]).get("type") != "boolean"
                    or any(schema_at(root, rule[key]).get("type") != "string" for key in ("target", "template"))):
                fail("invalid composition rule")
            continue
        scope = schema_at(root, rule["for_each"]).get("items") if "for_each" in rule else root
        if scope is None:
            fail("for_each must target an array")
        for key in ("source", "target", "profile"):
            if key in rule and schema_at(root if key == "profile" else scope, rule[key]).get("type") != "string":
                fail("data rule must reference a string")
    for rule in value.get("constraints", ()):
        for key in ("left", "right"):
            if schema_at(root, rule[key]).get("type") not in ("integer", "number"):
                fail("lt operands must be numeric")


def selector(source, *types):
    return {"source": source, **({"types": list(types), "required": True} if types else {})}


STRING_INPUT = selector("input.structdata", "string")


def form_descriptor(module, component_id):
    return next(item for item in BUILDER_FORM_DESCRIPTORS
                if (item["module"], item["component_id"]) == (module, component_id))


CHUNK = form_descriptor("chunking", "recursive")
EMBED = form_descriptor("embedding", "dense")
INDEX = form_descriptor("indexing", "local")
RETRIEVE = form_descriptor("retrieval", "builtin")
RERANK = form_descriptor("rerank", "model_api")
REWRITE = form_descriptor("query_transformation", "rewrite")
for form in BUILDER_FORM_DESCRIPTORS:
    validate_descriptor(form)

REGISTRY = {(d["module"], d["component_id"], d["component_version"]): d for d in BUILDER_FORM_DESCRIPTORS}
RESOURCES = RUNTIME_CATALOG["resources"]
PROFILES = {key: value["dimensions"] for key, value in RESOURCES["profiles"].items()}

def node(component_id, **parameters):
    return {"component_id": component_id, "component_version": "1.0.0",
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
    key = module, config["component_id"], config["component_version"]
    if key not in REGISTRY:
        fail("unknown component version")
    desc = REGISTRY[key]
    values = config["parameters"]
    if module == "embedding" and any(key in values for key in ("source_field", "vector_name")):
        values = values.copy()
        first = {key: values.pop(key) for key in ("source_field", "vector_name") if key in values}
        if isinstance(values.get("mappings", []), list):
            values["mappings"] = [first, *values.get("mappings", [])]
    if module == "retrieval" and "vector_name" in values and isinstance(values.get("vector_fields", []), list):
        values = values.copy()
        name = values.pop("vector_name")
        values.pop("query_profile", None)
        values["vector_fields"] = [name, *(field for field in values.get("vector_fields", []) if field != name)]
    Draft202012Validator(desc["parameters_schema"], registry=SCHEMA_REGISTRY).validate(values)
    if module == "embedding":
        context = {**context, "input.structdata": composition_fields(desc, values, context.get("input.structdata", {}))}
    for key, spec in desc.get("option_sources", {}).items():
        selected = selected_values(values, key)
        if selected and any(value not in options(spec, context) for value in selected):
            fail("invalid selection:" + key)
    for rule in desc.get("constraints", ()):
        if not values[rule["left"][1:]] < values[rule["right"][1:]]:
            fail("constraint:lt")
    return desc, values


TEMPLATE_FIELD = re.compile(r"\{\{\s*structdata\.([^{}]+?)\s*\}\}")


def composition_fields(desc, values, fields):
    result = fields.copy()
    for rule in desc.get("data_rules", ()):
        if rule["op"] != "compose" or not values.get(rule["enabled"][1:]):
            continue
        target = values[rule["target"][1:]]
        if target in result:
            fail("duplicate field")
        template = values[rule["template"][1:]]
        remainder = TEMPLATE_FIELD.sub("", template)
        if not template.strip() or "{{" in remainder or "}}" in remainder:
            fail("invalid composition template")
        for name in TEMPLATE_FIELD.findall(template):
            field = fields.get(name)
            if not field or field.type != "string" or not field.required:
                fail("invalid composition source:" + name)
        result[target] = Field("string")
    return result


def data_effects(desc, values, fields, vectors):
    result = {} if desc["module"] == "chunking" else composition_fields(desc, values, fields)
    vector_result = vectors.copy()
    for rule in desc.get("data_rules", ()):
        op = rule["op"]
        if op == "compose":
            continue
        rows = values.get(rule["for_each"][1:], []) if "for_each" in rule else [values]
        for row in rows:
            target = row[rule["target"][1:]]
            if op == "vector":
                if target in vector_result:
                    fail("duplicate vector")
                profile = values[rule["profile"][1:]]
                vector_result[target] = Vector(row[rule["source"][1:]], profile, PROFILES[profile])
            else:
                if target in result:
                    fail("duplicate field")
                result[target] = (Field(**rule["schema"]) if op == "declare"
                                  else fields[row[rule["source"][1:]]])
    return result, vector_result


def context(fields, vectors):
    return {**RESOURCES, "input.structdata": fields, "input.vectors": vectors}


def candidate_context(fields):
    return {
        "candidate.structdata": fields,
        "candidate.document_fields": {"document_id": Field("string"),
                                      **{f"structdata.{name}": value for name, value in fields.items()}},
    }


def compile_index(fields, vectors, config):
    _, params = parameters("indexing", config, context(fields, vectors))
    effective = fields.copy()
    for name, override in params.get("structdata_overrides", {}).items():
        path = f"/ingestion/indexing/parameters/structdata_overrides/{name}"
        if name not in effective:
            fail("missing index override field:" + path)
        effective[name] = replace(effective[name], **override)
        if effective[name].searchable and effective[name].type != "string":
            fail("invalid searchable type:" + path)
    return {
        "fields": effective,
        "fulltext": {f"structdata.{name}": value for name, value in effective.items() if value.searchable},
        "filters": {f"structdata.{name}": value for name, value in effective.items() if value.filterable},
        "vectors": {name: vectors[name] for name in
                    ([params["vector_name"]] if "vector_name" in params else params.get("vector_fields", []))},
    }


def validate_filters(filters, filter_fields, path):
    FILTER_SHAPE.validate(filters)
    range_types = {"integer", "number", "date", "datetime"}
    for index, clause in enumerate(filters):
        conditions = clause.get("any", [clause])
        for position, condition in enumerate(conditions):
            location = f"{path}/{index}"
            if "any" in clause:
                location += f"/any/{position}"
            field = filter_fields.get(condition["field"])
            operator = condition["operator"]
            if field is None:
                fail("field is not filterable:" + location + "/field")
            if operator not in {"eq", "in"} and field.type not in range_types:
                fail("invalid filter operator:" + location + "/operator")
            values = condition["value"] if operator == "in" else [condition["value"]]
            kind = "string" if field.type == "string_array" else field.type
            value_schema = {"type": kind}
            validator = DATE_FORMATS.get(kind) or Draft202012Validator(value_schema)
            if any((isinstance(value, float) and not isfinite(value)) or not validator.is_valid(value)
                   for value in values):
                fail("invalid filter value:" + location + "/value")


def compile_retrieval(index_plan, config):
    _, params = parameters("retrieval", config, {
        **candidate_context(index_plan["fields"]), "index_plan.fulltext": index_plan["fulltext"],
        "index_plan.vectors": index_plan["vectors"],
    })
    profiles = {name: index_plan["vectors"][name].profile for name in params.get("vector_fields", [])}
    original = config["parameters"]
    if "vector_name" in original and "query_profile" in original:
        if original["query_profile"] != profiles[original["vector_name"]]:
            fail("incompatible query profile")
    if len(profiles) + len(params.get("fulltext_fields", [])) > 1 and "fusion" not in params:
        fail("fusion required for multiple routes")
    return profiles


def binding_fixture():
    binding = json.loads((HERE / "index_binding.example.json").read_text())
    return {**binding, "filter_fields": []}


def check_runtime_binding(index_plan, binding):
    schema = json.loads((REPO / "schemas/index_binding.schema.json").read_text())
    Draft202012Validator(schema).validate(binding)
    vectors = {
        name: Vector(entry["source_field"], entry["embedding_profile_id"], entry["dimensions"])
        for name, entry in binding.get("vector_bindings", {}).items()
    }
    if (set(binding.get("fulltext_fields", [])) != set(index_plan["fulltext"])
            or set(binding.get("filter_fields", [])) != set(index_plan["filters"])
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
        if not field or field.type != "string" or not field.required:
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
EMBED_CONFIG = node("dense", mappings=[{"source_field": "text", "vector_name": "text"}], profile="text-v1")
INDEX_CONFIG = node("local", persistence="memory", structdata_overrides={"text": {"searchable": True}},
                    vector_name="text")
RETRIEVAL_CONFIG = node("builtin", vector_fields=["text"], per_route_k=10)
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
        if config["component_id"] == "remote_api":
            if config["component_version"] not in REMOTE_ADAPTER_VERSIONS:
                fail("unknown Remote API adapter version")
            segment, _, _, _ = remote_contract(pipeline, module, config["through"])
            check_coverage(segment[1:], nodes)
            covered.update(segment)
        yield module, config


def field_specs(values):
    return {name: Field(**value) for name, value in values.items()}


def bind_system_parameters(snapshot, environment=None, *, request_parameters=None):
    """Exercise startup and request binding for the published fixtures."""
    Draft202012Validator(SYSTEM_CONFIG_SCHEMA, registry=SCHEMA_REGISTRY).validate(snapshot)
    config = snapshot["config"]
    declared = config.get("secret", {})
    values = declared if environment is None else environment
    for key, configured in declared.items():
        if environment is not None and configured is not None:
            fail(f"export contains a DEV value:/config/secret/{key}")
        if not isinstance(values.get(key), str):
            fail(f"missing System Secret:/config/secret/{key}")

    def resolve(value, shape, path, specs, request_values):
        if isinstance(value, dict):
            return {key: resolve(item, shape.get("properties", {}).get(key, {}), f"{path}/{key}", specs, request_values)
                    for key, item in value.items()}
        if isinstance(value, list):
            return [resolve(item, shape.get("items", {}), f"{path}/{i}", specs, request_values)
                    for i, item in enumerate(value)]
        if not isinstance(value, str) or not (value.startswith("{{") and value.endswith("}}")):
            return value
        if not PARAMETER_EXPRESSION.fullmatch(value):
            fail(f"invalid parameter expression:{path}")
        key = value[2:-2]
        if request_values is not None and key in request_values:
            return request_values[key]
        if key not in declared:
            if key in specs and request_values is None:
                return value  # Request-only references are bound when the fixture is invoked.
            if key in specs:
                fail(f"missing parameter {key}:{path}")
            fail(f"undeclared System Secret {key}:{path}")
        if shape.get("type") in ("integer", "number", "boolean", "array", "object"):
            try:
                return json.loads(values[key])
            except ValueError:
                raise ConfigError(f"invalid System Secret value:{path}") from None
        return values[key]

    pipelines = deepcopy(config["pipelines"])
    for lane, nodes in pipelines.items():
        entry = nodes.get("import" if lane == "ingestion" else "inference_input", {})
        declarations = entry.get("parameters", {}).get("request_parameters", [])
        specs = {item["name"]: item for item in declarations}
        if len(specs) != len(declarations):
            fail(f"duplicate request parameter:/config/pipelines/{lane}")
        supplied = (request_parameters or {}).get(lane)
        request_values = None if supplied is None else {}
        if supplied is not None:
            for name, spec in specs.items():
                if name in supplied:
                    value = supplied[name]
                elif "default_value" in spec:
                    value = json.loads(spec["default_value"])
                elif spec["required"]:
                    fail(f"missing required request parameter:/parameters/{name}")
                else:
                    continue
                if not Draft202012Validator({"type": spec["type"]}).is_valid(value):
                    fail(f"invalid request parameter type:/parameters/{name}")
                request_values[name] = value
        for module, node_config in effective_nodes(lane, nodes):
            key = module, node_config["component_id"], node_config["component_version"]
            descriptor = REGISTRY.get(key, {})
            path = f"/config/pipelines/{lane}/{module}"
            shape = descriptor.get("parameters_schema", {})
            template_fields = {"query_transformation": {"prompt"}, "embedding": {"composition_template"}}.get(module, set())
            node_config["parameters"] = {
                name: value if name in template_fields else resolve(
                    value, shape.get("properties", {}).get(name, {}), f"{path}/parameters/{name}", specs, request_values
                )
                for name, value in node_config["parameters"].items()
            }
            if "auth" in node_config:
                node_config["auth"] = resolve(node_config["auth"], {}, f"{path}/auth", {}, {})
                if not node_config["auth"]["bearer_token"]:
                    fail(f"missing bearer token:{path}/auth/bearer_token")
    return pipelines


def compile_local_example(snapshot, environment=None):
    """Exercise the Local Search examples using the offline descriptor registry."""
    pipelines = bind_system_parameters(snapshot, environment)
    fields, vectors = {}, {}
    for module, config in effective_nodes("ingestion", pipelines["ingestion"]):
        if config["component_id"] == "remote_api":
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
                if module == "parsing":
                    source = pipelines["ingestion"]["import"]["parameters"].get("source", "structdata")
                    file_parser = bool(desc["io"].get("content_media_types"))
                    if file_parser != (source == "content"):
                        fail("Parser does not match Import source")
                    if file_parser:
                        if "contenttext" in fields:
                            fail("duplicate field")
                        fields = {**fields, "contenttext": Field("string")}
                fields, vectors = data_effects(desc, values, fields, vectors)

    inference = pipelines["inference"]
    validate_filters(inference.get("fixed_filters", []), index["filters"], "/inference/fixed_filters")
    for module, config in effective_nodes("inference", inference):
        if config["component_id"] == "remote_api":
            fail("example compiler only supports builtin Inference")
        if module == "retrieval":
            compile_retrieval(index, config)
        else:
            parameters(module, config, {**RESOURCES, **candidate_context(index["fields"])})
    return index["fields"], vectors, index


def local_snapshot(mode):
    return json.loads((HERE / f"local_memory.{mode}.json").read_text())


@case("one Rewrite component supports single and multiple generated queries")
def _():
    config = node("rewrite", llm_ref="default-llm",
                  prompt="Rewrite {{query}} in {{count}} distinct ways.",
                  count=1, include_original=False)
    context = {"models": {"default-llm": None}}
    snapshot = local_snapshot("builtin")
    inference = snapshot["config"]["pipelines"]["inference"]
    inference["query_transformation"] = config
    compile_local_example(snapshot)
    _, single = parameters("query_transformation", config, context)
    assert single["count"] == 1 and not single["include_original"]
    config["parameters"].update(count=2, include_original=True)
    compile_local_example(snapshot)
    _, multiple = parameters("query_transformation", config, context)
    assert multiple["count"] + int(multiple["include_original"]) == 3
    config["parameters"].update(
        cross_query_at="Rerank 後", cross_query_method="RRF",
        cross_query_group_by=["document_id"], cross_query_top_n=5,
    )
    compile_local_example(snapshot)

    bad = deepcopy(config)
    bad["component_id"] = "multi_query"
    rejects(lambda: parameters("query_transformation", bad, context), "unknown component version")
    for key, value in (("count", 0), ("count", "2"), ("prompt", "  "), ("include_original", 1),
                       ("cross_query_at", "after_rerank"), ("cross_query_method", "off"),
                       ("cross_query_top_n", 0)):
        bad = deepcopy(config)
        bad["parameters"][key] = value
        rejects(lambda: parameters("query_transformation", bad, context), "ValidationError")
    bad = deepcopy(snapshot)
    bad["config"]["pipelines"]["inference"]["query_transformation"]["parameters"][
        "cross_query_group_by"
    ] = ["structdata.unknown"]
    rejects(lambda: compile_local_example(bad), "invalid selection:/cross_query_group_by/*")
    bad = deepcopy(config)
    bad["parameters"]["llm_ref"] = "unknown"
    rejects(lambda: parameters("query_transformation", bad, context), "invalid selection:/llm_ref")


@case("System Secrets resolve DEV values and deployment environment at startup")
def _():
    dev = local_snapshot("remote_parsing")
    exported = local_snapshot("remote_parsing.export")
    dev_secrets = dev["config"]["secret"]
    assert exported["config"]["secret"] == dict.fromkeys(dev_secrets)
    assert exported["config"]["pipelines"] == dev["config"]["pipelines"]
    environment = {"PARSER_API_TOKEN": "fixture-deploy-token", "CHUNK_MAX_TOKENS": "500", "language": "en-US"}
    assert compile_local_example(dev) == compile_local_example(exported, environment)
    dev_ingestion = bind_system_parameters(dev)["ingestion"]
    deployed_ingestion = bind_system_parameters(exported, environment)["ingestion"]
    assert dev_ingestion["parsing"]["auth"] == {"bearer_token": dev_secrets["PARSER_API_TOKEN"]}
    assert deployed_ingestion["parsing"]["auth"] == {"bearer_token": environment["PARSER_API_TOKEN"]}
    assert deployed_ingestion["chunking"]["parameters"]["max_tokens"] == 500

    rejects(lambda: compile_local_example(exported, {"CHUNK_MAX_TOKENS": "500", "language": "en-US"}),
            "missing System Secret:/config/secret/PARSER_API_TOKEN")
    rejects(lambda: compile_local_example(dev, environment),
            "export contains a DEV value:/config/secret/PARSER_API_TOKEN")
    rejects(lambda: compile_local_example(exported, {**environment, "CHUNK_MAX_TOKENS": "invalid"}),
            "invalid System Secret value:/config/pipelines/ingestion/chunking/parameters/max_tokens")
    undeclared = deepcopy(dev)
    undeclared["config"]["pipelines"]["ingestion"]["parsing"]["auth"]["bearer_token"] = "{{UNDECLARED}}"
    rejects(lambda: compile_local_example(undeclared),
            "undeclared System Secret UNDECLARED:/config/pipelines/ingestion/parsing/auth/bearer_token")
    literal = deepcopy(dev)
    literal["config"]["pipelines"]["ingestion"]["parsing"]["auth"]["bearer_token"] = "fixture-inline-token"
    rejects(lambda: compile_local_example(literal), "ValidationError")


@case("Unified parameter references prefer the validated request and protect Remote authentication")
def _():
    snapshot = local_snapshot("remote_parsing")
    ingestion = snapshot["config"]["pipelines"]["ingestion"]
    specs = ingestion["import"]["parameters"]["request_parameters"]
    body = json.loads((HERE.parent / "user_remote_api/ingestion.request.json").read_text())

    def parser(request):
        return bind_system_parameters(snapshot, request_parameters={"ingestion": request})["ingestion"]["parsing"]

    default_language = snapshot["config"]["secret"]["language"]
    assert parser({})["parameters"]["language"] == default_language
    assert default_language != body["parameters"]["language"]
    assert parser(body["parameters"])["parameters"] == body["parameters"]
    assert parser({"language": ""})["parameters"]["language"] == ""
    rejects(lambda: parser({"language": None}), "invalid request parameter type:/parameters/language")
    rejects(lambda: parser({"language": 42}), "invalid request parameter type:/parameters/language")

    specs[0]["default_value"] = '"ja-JP"'
    assert parser({})["parameters"]["language"] == "ja-JP"
    specs.append({"name": "PARSER_API_TOKEN", "type": "string", "required": False})
    assert parser({"PARSER_API_TOKEN": "fixture-caller-value"})["auth"] == {
        "bearer_token": snapshot["config"]["secret"]["PARSER_API_TOKEN"]
    }
    del snapshot["config"]["secret"]["PARSER_API_TOKEN"]
    rejects(lambda: parser({"PARSER_API_TOKEN": "fixture-caller-value"}),
            "undeclared System Secret PARSER_API_TOKEN:/config/pipelines/ingestion/parsing/auth/bearer_token")


@case("published Local Search examples compile to the same index and candidate contracts")
def _():
    builtin = local_snapshot("builtin")
    remote = local_snapshot("remote_parsing")
    assert builtin["system_id"] == remote["system_id"]
    assert builtin["config_revision"] != remote["config_revision"]
    builtin_pipelines = bind_system_parameters(builtin)
    remote_pipelines = bind_system_parameters(remote)
    builtin_pipelines["ingestion"].pop("parsing")
    parser = remote_pipelines["ingestion"].pop("parsing")
    remote_pipelines["ingestion"]["import"]["parameters"].pop("request_parameters")
    assert builtin_pipelines == remote_pipelines
    assert remote_contract("ingestion", "parsing", parser["through"])[1:3] == ("Document", "Document[]")
    fields, vectors, index = compile_local_example(local_snapshot("builtin"))
    assert (fields, vectors, index) == compile_local_example(local_snapshot("remote_parsing"))
    assert fields == {
        "text": Field("string", searchable=True),
        "title": Field("string", filterable=True),
        "price": Field("number", required=False, filterable=True),
        "tags": Field("string_array", required=False, filterable=True),
    }
    assert vectors == {"text": Vector("text", "text-v1", 3)}
    binding = json.loads((HERE / "index_binding.example.json").read_text())
    check_runtime_binding(index, binding)
    for field in ("fulltext_fields", "filter_fields"):
        rejects(lambda: check_runtime_binding(index, {**binding, field: ["text"]}), "ValidationError")
    snapshot = local_snapshot("builtin")
    retrieval = snapshot["config"]["pipelines"]["inference"]["retrieval"]["parameters"]
    retrieval["group_by"] = ["document_id", "structdata.title"]
    retrieval["fulltext_fields"] = ["structdata.text"]
    retrieval["fusion"] = "RRF"
    compile_local_example(snapshot)
    retrieval["group_by"] = ["structdata.tags"]
    rejects(lambda: compile_local_example(snapshot), "invalid selection:/group_by/*")
    retrieval["group_by"] = ["document_id"]
    retrieval["fulltext_fields"] = ["structdata.title"]
    rejects(lambda: compile_local_example(snapshot), "invalid selection:/fulltext_fields/*")


@case("Indexing changes capabilities while preserving the final Document shape")
def _():
    snapshot = local_snapshot("remote_parsing")
    pipeline = snapshot["config"]["pipelines"]["ingestion"]
    pipeline["parsing"]["output"]["structdata"]["section_title"] = {"type": "string", "required": False}
    copies = pipeline["chunking"]["parameters"]["copy_fields"]
    copies.append({"source_field": "section_title", "output_field": "section_title"})
    overrides = pipeline["indexing"]["parameters"]["structdata_overrides"]
    overrides["section_title"] = {"searchable": True}
    fields, _, index = compile_local_example(snapshot)
    assert fields["section_title"] == Field("string", required=False, searchable=True)
    assert "structdata.section_title" in index["fulltext"]
    copies.pop()
    rejects(lambda: compile_local_example(snapshot), "missing index override field:/ingestion/indexing/parameters/structdata_overrides/section_title")
    del overrides["section_title"]
    overrides["tags"] = {"searchable": True}
    rejects(lambda: compile_local_example(snapshot), "invalid searchable type:/ingestion/indexing/parameters/structdata_overrides/tags")
    overrides["tags"] = {"required": True}
    rejects(lambda: compile_local_example(snapshot), "ValidationError")
    del overrides["tags"]
    overrides["price"] = {"filterable": False}
    rejects(lambda: compile_local_example(snapshot), "field is not filterable:/inference/fixed_filters/0/field")


@case("Fixed and request Filters use the same typed rules and one-level any groups")
def _():
    _, _, index = compile_local_example(local_snapshot("builtin"))
    request = json.loads((REPO / "examples/user_remote_api/inference.request.json").read_text())
    filters = index["filters"] | {"structdata.updated_at": Field("datetime", filterable=True),
                                  "structdata.valid_on": Field("date", filterable=True)}
    validate_filters(request["filters"], filters, "/filters")
    for kind, value, invalid in (
        ("updated_at", "2026-11-16T00:00:00+08:00", "2026-11-16T00:00:00"),
        ("valid_on", "2026-11-16", "2026-02-31"),
        ("price", 300, "300"),
    ):
        condition = {"field": "structdata." + kind, "operator": "gte", "value": value}
        validate_filters([condition], filters, "/filters")
        condition["value"] = invalid
        rejects(lambda: validate_filters([condition], filters, "/filters"), "invalid filter value:/filters/0/value")
    invalid_range = [{"field": "structdata.tags", "operator": "gt", "value": "設備"}]
    rejects(lambda: validate_filters(invalid_range, filters, "/filters"), "invalid filter operator:/filters/0/operator")


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


@case("component IDs select the node shape and versions pin the implementation")
def _():
    bad_descriptor = deepcopy(CHUNK)
    bad_descriptor["component_id"] = "remote_api"
    rejects(lambda: validate_descriptor(bad_descriptor), "ValidationError")
    del bad_descriptor["component_id"]
    rejects(lambda: validate_descriptor(bad_descriptor), "ValidationError")

    snapshot = local_snapshot("remote_parsing")
    parser = snapshot["config"]["pipelines"]["ingestion"]["parsing"]
    parser["kind"] = "remote"
    rejects(lambda: compile_local_example(snapshot), "ValidationError")
    del parser["kind"]
    del parser["component_version"]
    rejects(lambda: compile_local_example(snapshot), "ValidationError")
    parser["component_version"] = "2.0.0"
    rejects(lambda: compile_local_example(snapshot), "unknown Remote API adapter version")
    parser["component_version"] = "1.0.0"
    parser["component_id"] = "passthrough"
    rejects(lambda: compile_local_example(snapshot), "ValidationError")

    parser["component_id"] = "remote_api"
    inference = snapshot["config"]["pipelines"]["inference"]
    inference["retrieval"] = {
        "component_id": "remote_api",
        "component_version": "1.0.0",
        "through": "rerank",
        "service_ref": "external-search",
        "parameters": {},
    }
    del inference["rerank"]
    Draft202012Validator(SYSTEM_CONFIG_SCHEMA, registry=SCHEMA_REGISTRY).validate(snapshot)
    assert [module for module, _ in effective_nodes("inference", inference)] == [
        "inference_input", "query_transformation", "retrieval",
    ]


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
    assert options(EMBED["option_sources"]["/mappings/*/source_field"], context(fields, vectors)) == ["body", "title"]
    rejects(lambda: parameters("embedding", EMBED_CONFIG, context(fields, vectors)),
            "invalid selection:/mappings/*/source_field")


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
    params["copy_fields"][0]["output_field"] = "summary"
    desc, params = parameters("chunking", config, context(UPSTREAM, {}))
    fields, _ = data_effects(desc, params, UPSTREAM, {})
    assert fields["summary"] == Field("string", required=False)


@case("unknown component version, invalid parameter type and invalid relation fail separately")
def _():
    bad = deepcopy(CHUNK_CONFIG)
    bad["component_version"] = "2.0.0"
    rejects(lambda: parameters("chunking", bad, context(UPSTREAM, {})), "unknown component version")
    bad["component_version"] = "1.0.0"
    bad["parameters"]["overlap_tokens"] = "500"
    rejects(lambda: parameters("chunking", bad, context(UPSTREAM, {})), "ValidationError")
    bad["parameters"]["overlap_tokens"] = 500
    rejects(lambda: parameters("chunking", bad, context(UPSTREAM, {})), "constraint:lt")


@case("index plan drives compile-time choices and binding is checked separately")
def _():
    fields, vectors = builtin_output()
    index = compile_index(fields, vectors, INDEX_CONFIG)
    assert compile_retrieval(index, RETRIEVAL_CONFIG) == {"text": "text-v1"}
    legacy = node("builtin", vector_name="text", query_profile="text-v1", per_route_k=10)
    assert compile_retrieval(index, legacy) == {"text": "text-v1"}
    legacy["parameters"]["query_profile"] = "other-space-v1"
    rejects(lambda: compile_retrieval(index, legacy), "incompatible query profile")
    invalid_limit = node("builtin", vector_fields=["text"], top_k=10)
    rejects(lambda: compile_retrieval(index, invalid_limit), "ValidationError")
    binding = binding_fixture()
    check_runtime_binding(index, binding)
    binding["vector_bindings"]["text"]["dimensions"] = 4
    rejects(lambda: check_runtime_binding(index, binding), "binding mismatch")
    binding["vector_bindings"]["text"]["dimensions"] = "3"
    rejects(lambda: check_runtime_binding(index, binding), "ValidationError")
    binding["vector_bindings"] = {}
    rejects(lambda: check_runtime_binding(index, binding), "binding mismatch")
    vector_options = RETRIEVE["option_sources"]["/vector_fields/*"]
    rejects(lambda: options(vector_options, {}), "unresolved:index_plan.vectors")
    assert options(vector_options, {"index_plan.vectors": {}}) == []


@case("retrieval supports multi-select and inherits a query profile per indexed vector")
def _():
    fields, vectors = builtin_output()
    vectors["title"] = Vector("title", "other-space-v1", 3)
    index = compile_index(fields, vectors, node(
        "local", persistence="memory", vector_fields=["text", "title"],
        structdata_overrides={"text": {"searchable": True}},
    ))
    config = node("builtin", vector_fields=["text", "title"], fulltext_fields=["structdata.text"],
                  per_route_k=10, fusion="RRF", group_by=["document_id"], top_n=3)
    assert compile_retrieval(index, config) == {"text": "text-v1", "title": "other-space-v1"}
    del config["parameters"]["fusion"]
    rejects(lambda: compile_retrieval(index, config), "fusion required for multiple routes")
    assert compile_retrieval(index, node("builtin", fulltext_fields=["structdata.text"], per_route_k=5)) == {}
    rejects(lambda: compile_retrieval(index, node("builtin", per_route_k=5)), "ValidationError")
    rejects(lambda: compile_retrieval(index, node("builtin", vector_fields=["text"], per_route_k=5, top_n=0)),
            "ValidationError")


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
    searchable_text = {**fields, "text": Field("string", searchable=True, filterable=True)}
    assert remote_effects("embedding", "embedding", {"vectors": vectors}, searchable_text) == (
        searchable_text, vectors)
    rejects(lambda: remote_effects("parsing", "embedding", {"structdata": fields}),
            "wrong remote declarations")
    rejects(lambda: remote_effects("parsing", "embedding", {"structdata": fields,
            "vectors": {"text": Vector("text", "text-v1", 4)}}), "remote profile dimension mismatch")
    rejects(lambda: remote_effects("parsing", "embedding", {"structdata": {"title": Field("string")},
            "vectors": vectors}), "invalid remote vector source")
    rejects(lambda: remote_effects("embedding", "embedding", {"vectors": vectors},
            {**fields, "text": Field("string", required=False)}), "invalid remote vector source")


@case("published Document and vector envelopes still validate example payloads")
def _():
    base = json.loads((REPO / "schemas/document.schema.json").read_text())
    schema = Draft202012Validator(base)
    examples = REPO / "examples/user_remote_api"
    candidate = json.loads((examples / "remote_ingestion.response.json").read_text())["output"][0]
    schema.validate(candidate)
    bad = deepcopy(candidate)
    bad["structdata"]["text"] = [["invalid", "nested"]]
    rejects(lambda: schema.validate(bad), "ValidationError")


@case("the form catalog covers all planned builtin ids with a real descriptor")
def _():
    expected = {(module, component) for module, (components, _) in BUILTIN_COMPONENTS.items()
                for component in components}
    assert {(module, component) for module, component, _ in REGISTRY} == expected
    assert len(REGISTRY) == len(BUILDER_FORM_DESCRIPTORS) == len(expected) == 20


@case("external retrieval candidate uses effective output schema without an IndexBinding")
def _():
    paths = REPO / "schemas"
    document = json.loads((paths / "document.schema.json").read_text())
    query_context = json.loads((paths / "query_context.schema.json").read_text())
    registry = Registry().with_resource(document["$id"], Resource.from_contents(document))
    query = Draft202012Validator(query_context, registry=registry)
    examples = REPO / "examples/user_remote_api"
    request = json.loads((examples / "remote_retrieval.request.json").read_text())
    response = json.loads((examples / "remote_retrieval.response.json").read_text())
    query.validate(request["input"])
    results = response["output"]
    query.validate(results)

    fields, _, index = compile_local_example(local_snapshot("builtin"))
    for position, context_value in enumerate(request["input"]):
        validate_filters(context_value["filters"], index["filters"], f"/input/{position}/filters")

    field_schema = obj(
        {name: array({"type": "string"}) if field.type == "string_array" else {"type": field.type}
         for name, field in fields.items()},
        sorted(name for name, field in fields.items() if field.required),
    )
    effective = json.loads((examples / "effective_document.schema.json").read_text())
    fixture_fields = effective["allOf"][1]["properties"]["structdata"]
    assert field_schema == {**fixture_fields, "required": sorted(fixture_fields["required"])}, "effective Document fixture drifted from System Config"
    validator = Draft202012Validator(effective, registry=registry)
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


@case("Builder form descriptors and data contracts match the standalone Prototype")
def _():
    source = (REPO / "01_ui_prototype.html").read_text()
    def embedded(script_id):
        start = f'<script type="application/json" id="{script_id}">'
        return json.loads(source.split(start,1)[1].split("</script>",1)[0])
    assert embedded("builder-form-descriptors") == BUILDER_FORM_DESCRIPTORS
    runtime = embedded("runtime-fixture")
    assert runtime["catalog"] == RUNTIME_CATALOG
    assert len(runtime["catalog"]["descriptors"]) == len(BUILTIN_COMPONENTS)
    assert {item["module"] for item in runtime["catalog"]["descriptors"]} == BUILTIN_COMPONENTS.keys()
    Draft202012Validator(CATALOG_SCHEMA, registry=SCHEMA_REGISTRY).validate(RUNTIME_CATALOG)
    for desc in RUNTIME_CATALOG["descriptors"]:
        validate_descriptor(desc)
        assert desc == REGISTRY[desc["module"], desc["component_id"], desc["component_version"]]
    assert PROFILES["text-v1"] == 3
    for name, schema in runtime["schemas"].items():
        assert schema == json.loads((REPO / f"schemas/{name}.schema.json").read_text())
    for module, component in (("embedding","dense"), ("indexing","elasticsearch"),
                              ("indexing","local"), ("rerank","model_api")):
        assert form_descriptor(module, component)["parameters_schema"]["properties"]["service_source"]["default"] == "DEV test use"


@case("Builder controls must target a compatible declared parameter")
def _():
    for module, component, pointer in (
        ("import", "platform", "/source"),
        ("indexing", "local", "/persistence"),
        ("embedding", "dense", "/mappings"),
    ):
        bad = deepcopy(form_descriptor(module, component))
        controls = bad["ui_hints"]["controls"]
        controls[pointer] = next(iter(controls.values()))
        rejects(lambda: validate_descriptor(bad), "incompatible UI control:" + pointer)
        controls[pointer] = "unknown_editor"
        rejects(lambda: validate_descriptor(bad), "ValidationError")


@case("visibility references use the right parameter types")
def _():
    bad = deepcopy(RETRIEVE)
    condition = bad["ui_hints"]["visible_when"]["/fusion"]["all"][0]
    condition["paths"] = ["/per_route_k"]
    rejects(lambda: validate_descriptor(bad), "visibility selection count requires string arrays")
    condition["paths"] = ["/unknown"]
    rejects(lambda: validate_descriptor(bad), "unknown parameter path:/unknown")
    bad["ui_hints"]["visible_when"]["/fusion"] = {"all": [{"path": "/per_route_k", "equals": "2"}]}
    rejects(lambda: validate_descriptor(bad), "visibility equality requires a matching type")


@case("catalog resources cover registered option sources and invalid references fail at publish")
def _():
    sources = {entry["source"] for descriptor in BUILDER_FORM_DESCRIPTORS
               for entry in descriptor.get("option_sources", {}).values()}
    assert sources - FIELD_SOURCES - {"input.vectors", "index_plan.vectors"} == RESOURCES.keys()
    catalog = deepcopy(RUNTIME_CATALOG)
    catalog["resources"]["profiles"]["text-v1"]["dimensions"] = 0
    validator = Draft202012Validator(CATALOG_SCHEMA, registry=SCHEMA_REGISTRY)
    rejects(lambda: validator.validate(catalog), "ValidationError")
    catalog["resources"]["profiles"] = {}
    validator.validate(catalog)
    existing = node("dense", mappings=[{"source_field": "text", "vector_name": "text"}], profile="removed")
    rejects(lambda: parameters("embedding", existing, context({"text": Field("string")}, {})),
            "invalid selection:/profile")


@case("Import source controls built-in Parser compatibility")
def _():
    snapshot = local_snapshot("builtin")
    ingestion = snapshot["config"]["pipelines"]["ingestion"]
    ingestion["parsing"] = node("pdf")
    rejects(lambda: compile_local_example(snapshot), "Parser does not match Import source")
    ingestion["import"]["parameters"]["source"] = "content"
    ingestion["chunking"]["parameters"]["split_field"] = "contenttext"
    compile_local_example(snapshot)
    ingestion["parsing"] = node("passthrough")
    rejects(lambda: compile_local_example(snapshot), "Parser does not match Import source")


@case("Embedding composition and multiple named vectors feed Indexing selections")
def _():
    config = deepcopy(EMBED_CONFIG)
    config["parameters"].update(
        compose_text=True, composition_field="embedding_text",
        composition_template="{{structdata.title}}｜{{structdata.text}}",
    )
    config["parameters"]["mappings"].append({"source_field": "embedding_text", "vector_name": "combined"})
    fields = {"title": Field("string"), "text": Field("string")}
    desc, values = parameters("embedding", config, context(fields, {}))
    legacy = node("dense", source_field="text", vector_name="text", profile="text-v1",
                  mappings=[{"source_field": "embedding_text", "vector_name": "combined"}],
                  compose_text=True, composition_field="embedding_text",
                  composition_template=config["parameters"]["composition_template"])
    assert parameters("embedding", legacy, context(fields, {}))[1] == values
    empty = node("dense", mappings=[], profile="text-v1")
    rejects(lambda: parameters("embedding", empty, context(fields, {})), "ValidationError")
    expanded, vectors = data_effects(desc, values, fields, {})
    assert expanded["embedding_text"] == Field("string")
    assert vectors["combined"] == Vector("embedding_text", "text-v1", 3)
    index_config = node("local", persistence="memory", vector_fields=["text", "combined"])
    assert compile_index(expanded, vectors, index_config)["vectors"] == vectors
    index_config["parameters"]["vector_fields"] = ["combined"]
    assert set(compile_index(expanded, vectors, index_config)["vectors"]) == {"combined"}
    config["parameters"]["composition_template"] = "{{structdata.missing}}"
    rejects(lambda: parameters("embedding", config, context(fields, {})), "invalid composition source:missing")
    config["parameters"]["composition_template"] = "{{not_structdata.title}}"
    rejects(lambda: parameters("embedding", config, context(fields, {})), "invalid composition template")


if __name__ == "__main__":
    Draft202012Validator.check_schema(DATA_META)
    Draft202012Validator.check_schema(DESCRIPTOR_SCHEMA)
    Draft202012Validator.check_schema(CATALOG_SCHEMA)
    Draft202012Validator.check_schema(SYSTEM_CONFIG_SCHEMA)
    assert CHUNK == json.loads((HERE / "recursive.descriptor.json").read_text())
    assert REWRITE == json.loads((HERE / "rewrite.descriptor.json").read_text())
    for name, test in TESTS:
        test()
        print("PASS", name)
    print(f"{len(TESTS)} scenario groups passed")
