"""Compile a System Config into an executable plan, an index plan and the index fingerprint.

The compiler is the Runtime side of ``config:validate``. Every error is a ConfigInvalid
located by a JSON Pointer relative to the request body (``/config/...``).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from rag_engine.adapters.es_mapping import analysis_settings, index_mappings
from rag_engine.components.chunking import DEFAULT_SEPARATORS, RecursiveSettings
from rag_engine.components.embedding import TEMPLATE_FIELD, DenseSettings
from rag_engine.components.remote import RemoteCall
from rag_engine.contracts import ContractError, errors, schema_ref
from rag_engine.core.canonical import sha256_hex
from rag_engine.core.errors import ConfigInvalid, RequestInvalid
from rag_engine.core.filters import validate_filters
from rag_engine.core.resources import RuntimeResources
from rag_engine.core.types import Fields, FieldSpec, Vectors, VectorSpec, fields_meta
from rag_engine.engine.catalog import REMOTE_ADAPTER_VERSIONS, Catalog
from rag_engine.engine.plan import (
    BuiltinRetrieval,
    ChunkStage,
    CompiledSystem,
    EmbedStage,
    IndexPlan,
    InferencePlan,
    IngestionPlan,
    IngestionStage,
    McpSettings,
    RemoteSegment,
    RetrievalReferences,
)
from rag_engine.engine.values import (
    EXPRESSION,
    RESERVED_SECRET_KEYS,
    RequestParameter,
    SystemValues,
    load_values,
    references,
    request_parameters,
)

INGESTION_ORDER = ("import", "parsing", "chunking", "embedding", "indexing")
INFERENCE_ORDER = ("inference_input", "query_transformation", "retrieval", "rerank")
REMOTE_INGESTION = ("parsing", "chunking", "embedding")
REMOTE_INFERENCE = ("query_transformation", "retrieval", "rerank")
REMOTE_TIMEOUT_LIMITS = {"ingestion": 600, "inference": 60}
ES_CREDENTIAL_FIELDS = ("es_number", "account", "password")
FINGERPRINT_VERSION = 1


# ---------------------------------------------------------------------------- helpers


def _shape(config: dict[str, Any]) -> None:
    for error in errors(schema_ref("system_config.draft.schema.json", "/$defs/config"), config):
        raise ConfigInvalid(error.message, path="/config" + _localize(config, error.path))


def _localize(config: dict[str, Any], path: str) -> str:
    """Re-check a node that failed ``oneOf`` against its own branch to point at the bad field."""
    parts = path.strip("/").split("/")
    if len(parts) != 3 or parts[0] != "pipelines":
        return path
    node = config.get("pipelines", {}).get(parts[1], {}).get(parts[2])
    if not isinstance(node, dict):
        return path
    if node.get("component_id") == "remote_api":
        branch = "remote_ingestion_node" if parts[1] == "ingestion" else "remote_inference_node"
    else:
        branch = "builtin_node"
    for error in errors(schema_ref("system_config.draft.schema.json", f"/$defs/{branch}"), node):
        return path + error.path
    return path


def _node_path(lane: str, module: str) -> str:
    return f"/config/pipelines/{lane}/{module}"


def _find_descriptor(catalog: Catalog, lane: str, module: str, node: dict[str, Any]) -> dict[str, Any]:
    descriptor = catalog.descriptor(module, node["component_id"], node["component_version"])
    if descriptor is None:
        raise ConfigInvalid(
            f"{module} component {node['component_id']}@{node['component_version']} is not available in this Runtime",
            path=_node_path(lane, module) + "/component_id",
            module=module,
        )
    return descriptor


def _check_parameters(
    schema: dict[str, Any], parameters: dict[str, Any], path: str, module: str, skip: set[str] | None = None
) -> None:
    """Validate ``parameters`` against a Descriptor schema; errors under ``skip`` names are ignored."""
    skip = skip or set()
    try:
        for error in errors(schema, parameters):
            parts = error.path.split("/")
            if len(parts) > 1 and parts[1] in skip:
                continue
            raise ConfigInvalid(error.message, path=f"{path}/parameters{error.path}", module=module)
    except ContractError as error:  # pragma: no cover - defensive
        raise ConfigInvalid(str(error), path=path, module=module) from error


def _descriptor(catalog: Catalog, lane: str, module: str, node: dict[str, Any]) -> dict[str, Any]:
    descriptor = _find_descriptor(catalog, lane, module, node)
    _check_parameters(descriptor["parameters_schema"], node["parameters"], _node_path(lane, module), module)
    return descriptor


def _secret_keys(values: SystemValues) -> set[str]:
    return set(values.secrets) | set(RESERVED_SECRET_KEYS)


def _no_secret_refs(value: Any, path: str, values: SystemValues, module: str) -> None:
    secrets = _secret_keys(values)
    for key, location in references(value, path):
        if key in secrets:
            raise ConfigInvalid("Secret reference outside authentication", path=location, module=module)


def _literal(value: Any, path: str, module: str) -> None:
    for _, location in references(value, path):
        raise ConfigInvalid("index-affecting parameter must be literal", path=location, module=module)


def _remote_call(
    lane: str, module: str, node: dict[str, Any], values: SystemValues
) -> tuple[RemoteCall, frozenset[str]]:
    path = _node_path(lane, module)
    if node["component_version"] not in REMOTE_ADAPTER_VERSIONS:
        raise ConfigInvalid("unknown Remote API adapter version", path=path + "/component_version", module=module)
    order = REMOTE_INGESTION if lane == "ingestion" else REMOTE_INFERENCE
    through = node["through"]
    if order.index(through) < order.index(module):
        raise ConfigInvalid("through must not precede the first module", path=path + "/through", module=module)
    connection = node["connection"]
    url_match = EXPRESSION.match(connection["url"])
    key = url_match[1] if url_match else ""
    if key in _secret_keys(values):
        raise ConfigInvalid("Secret reference outside authentication", path=path + "/connection/url", module=module)
    if key not in values.variables:
        raise ConfigInvalid(f"undeclared System Variable {key}", path=path + "/connection/url", module=module)
    url = values.variables[key]
    scheme, _, rest = url.partition("://")
    if scheme.lower() not in ("http", "https") or not rest or rest[0] in "/?#" or any(c.isspace() for c in url):
        raise ConfigInvalid("invalid Remote URL", path=path + "/connection/url", module=module)
    timeout = connection.get("timeout_seconds", 30)
    if timeout > REMOTE_TIMEOUT_LIMITS[lane]:
        raise ConfigInvalid(
            f"Remote timeout exceeds the {lane} deadline", path=path + "/connection/timeout_seconds", module=module
        )
    headers: dict[str, str] = {}
    for name, value in connection.get("headers", {}).items():
        location = f"{path}/connection/headers/{name}"
        _no_secret_refs(value, location, values, module)
        match = EXPRESSION.match(value)
        if match:
            if match[1] not in values.variables:
                raise ConfigInvalid(f"undeclared System Variable {match[1]}", path=location, module=module)
            value = values.variables[match[1]]
        elif references(value, location):
            raise ConfigInvalid("invalid parameter expression", path=location, module=module)
        headers[name] = value
    token = None
    if "auth" in node:
        token_ref = EXPRESSION.match(node["auth"]["bearer_token"])
        token_key = token_ref[1] if token_ref else ""
        location = path + "/auth/bearer_token"
        if token_key in RESERVED_SECRET_KEYS:
            raise ConfigInvalid("reserved System API Secret key", path=location, module=module)
        if token_key not in values.secrets:
            raise ConfigInvalid(f"undeclared System Secret {token_key}", path=location, module=module)
        token = values.secrets[token_key]
    _no_secret_refs(node["parameters"], path + "/parameters", values, module)
    runtime_only = frozenset(node.get("runtime_only_parameters", []))
    for name in runtime_only:
        if name not in node["parameters"]:
            raise ConfigInvalid("unknown runtime-only parameter", path=f"{path}/parameters/{name}", module=module)
    call = RemoteCall(module, through, node["contract_version"], url, float(timeout), headers, token)
    return call, runtime_only


def _covered(order: tuple[str, ...], module: str, through: str) -> tuple[str, ...]:
    return order[order.index(module) : order.index(through) + 1]


# ---------------------------------------------------------------------------- ingestion


@dataclass
class _IngestionState:
    fields: Fields
    vectors: Vectors
    stages: list[IngestionStage]
    projection: list[dict[str, Any]]


def _stage_projection(module: str, node: dict[str, Any], parameters: dict[str, Any], fields: Fields) -> dict[str, Any]:
    return {
        "kind": "builtin",
        "module": module,
        "component_id": node["component_id"],
        "component_version": node["component_version"],
        "parameters": parameters,
        "output_structdata": fields_meta(fields),
    }


def _compile_ingestion(
    config: dict[str, Any], catalog: Catalog, values: SystemValues
) -> tuple[IngestionPlan, _IngestionState, dict[str, Any]]:
    lane = "ingestion"
    nodes = config["pipelines"][lane]
    resources = catalog.resources
    importer = nodes["import"]
    _descriptor(catalog, lane, "import", importer)
    import_params = importer["parameters"]
    _literal(
        {k: v for k, v in import_params.items() if k != "request_parameters"},
        _node_path(lane, "import") + "/parameters",
        "import",
    )
    fields = {name: FieldSpec.from_meta(meta) for name, meta in import_params["structdata"].items()}
    source = import_params.get("source", "structdata")
    specs = request_parameters(
        import_params.get("request_parameters", []), _node_path(lane, "import") + "/parameters/request_parameters"
    )
    state = _IngestionState(dict(fields), {}, [], [_stage_projection("import", importer, {"source": source}, fields)])
    covered: set[str] = set()
    for module in REMOTE_INGESTION:
        node = nodes.get(module)
        path = _node_path(lane, module)
        if module in covered:
            if node is not None:
                raise ConfigInvalid("module is covered by a Remote segment", path=path, module=module)
            continue
        if node is None:
            if module == "parsing":
                raise ConfigInvalid("missing effective module parsing", path=path, module=module)
            continue
        if node["component_id"] == "remote_api":
            _compile_remote_ingestion(module, node, values, resources, state)
            covered.update(_covered(REMOTE_INGESTION, module, node["through"]))
            continue
        _descriptor(catalog, lane, module, node)
        _no_secret_refs(node["parameters"], path + "/parameters", values, module)
        _literal(node["parameters"], path + "/parameters", module)
        if module == "parsing":
            if source == "content":
                raise ConfigInvalid(
                    "content sources need a file Parser, not available in this Runtime",
                    path=path + "/component_id",
                    module=module,
                )
            state.stages.append("passthrough")
            state.projection.append(_stage_projection(module, node, {}, state.fields))
        elif module == "chunking":
            _compile_chunking(node, resources, state, path)
        elif module == "embedding":
            _compile_embedding(node, resources, state, path)
    if "chunking" not in covered and nodes.get("chunking") is None:
        raise ConfigInvalid("missing effective module chunking", path=_node_path(lane, "chunking"), module="chunking")
    indexing = nodes["indexing"]
    _descriptor(catalog, lane, "indexing", indexing)
    plan = IngestionPlan(source, fields, specs, tuple(state.stages))
    return plan, state, indexing


def _compile_remote_ingestion(
    module: str, node: dict[str, Any], values: SystemValues, resources: RuntimeResources, state: _IngestionState
) -> None:
    path = _node_path("ingestion", module)
    call, runtime_only = _remote_call("ingestion", module, node, values)
    fixed = {key: value for key, value in node["parameters"].items() if key not in runtime_only}
    _literal(fixed, path + "/parameters", module)
    _literal(node["output"], path + "/output", module)
    covered = _covered(REMOTE_INGESTION, module, node["through"])
    output = node["output"]
    needs_fields = any(item in covered for item in ("parsing", "chunking"))
    if needs_fields != ("structdata" in output) or ("embedding" in covered) != ("vectors" in output):
        raise ConfigInvalid(
            "Remote output declarations do not match the covered modules", path=path + "/output", module=module
        )
    if "structdata" in output:
        state.fields = {name: FieldSpec.from_meta(meta) for name, meta in output["structdata"].items()}
    vectors: Vectors = {}
    for name, entry in output.get("vectors", {}).items():
        location = f"{path}/output/vectors/{name}"
        source = state.fields.get(entry["source_field"])
        if source is None or source.type != "string" or not source.required:
            raise ConfigInvalid(
                "vector source must be a required string field", path=location + "/source_field", module=module
            )
        profile = resources.profiles.get(entry["embedding_profile_id"])
        if profile is None or profile.dimensions != entry["dimensions"]:
            raise ConfigInvalid("unknown Embedding Profile or dimension mismatch", path=location, module=module)
        vectors[name] = VectorSpec(entry["source_field"], entry["embedding_profile_id"], entry["dimensions"])
    state.vectors.update(vectors)
    segment = RemoteSegment(
        module,
        node["through"],
        covered,
        call,
        node["parameters"],
        runtime_only,
        node["revision"],
        dict(state.fields),
        vectors,
    )
    state.stages.append(segment)
    state.projection.append(
        {
            "kind": "remote",
            "module": module,
            "through": node["through"],
            "adapter_version": node["component_version"],
            "contract_version": node["contract_version"],
            "implementation_revision": node["revision"],
            "parameters": fixed,
            "output_structdata": fields_meta(state.fields),
        }
    )


def _compile_chunking(node: dict[str, Any], resources: RuntimeResources, state: _IngestionState, path: str) -> None:
    params = node["parameters"]
    for flag in ("preserve_original", "include_original_chunk"):
        if params.get(flag):
            raise ConfigInvalid(
                f"{flag} is not supported by this Runtime", path=f"{path}/parameters/{flag}", module="chunking"
            )
    if params["overlap_tokens"] >= params["max_tokens"]:
        raise ConfigInvalid(
            "overlap_tokens must be less than max_tokens", path=path + "/parameters/overlap_tokens", module="chunking"
        )
    split = state.fields.get(params["split_field"])
    if split is None or split.type != "string" or not split.required:
        raise ConfigInvalid(
            "split_field must be a required string field", path=path + "/parameters/split_field", module="chunking"
        )
    tokenizer = resources.tokenizer_profiles.get(params["tokenizer_profile_id"])
    if tokenizer is None:
        raise ConfigInvalid(
            "unknown tokenizer profile", path=path + "/parameters/tokenizer_profile_id", module="chunking"
        )
    output: Fields = {params["output_field"]: FieldSpec("string", True)}
    for index, item in enumerate(params["copy_fields"]):
        location = f"{path}/parameters/copy_fields/{index}"
        source = state.fields.get(item["source_field"])
        if source is None:
            raise ConfigInvalid("unknown copy source field", path=location + "/source_field", module="chunking")
        if item["output_field"] in output:
            raise ConfigInvalid("duplicate output field", path=location + "/output_field", module="chunking")
        output[item["output_field"]] = source
    settings = RecursiveSettings.from_parameters(params)
    state.fields = output
    state.stages.append(ChunkStage(settings, tokenizer))
    state.projection.append(
        _stage_projection(
            "chunking",
            node,
            {
                "split_field": settings.split_field,
                "output_field": settings.output_field,
                "copy_fields": [
                    {"source_field": source, "output_field": target}
                    for source, target in sorted(settings.copy_fields, key=lambda pair: pair[1])
                ],
                "max_tokens": settings.max_tokens,
                "overlap_tokens": settings.overlap_tokens,
                "tokenizer_revision": tokenizer.revision,
                "separators": list(params.get("separators", DEFAULT_SEPARATORS)),
                "keep_separator": settings.keep_separator,
                "preserve_original": False,
                "include_original_chunk": False,
            },
            state.fields,
        )
    )


def _compile_embedding(node: dict[str, Any], resources: RuntimeResources, state: _IngestionState, path: str) -> None:
    params = node["parameters"]
    if params.get("service_source", "dev_test") != "dev_test":
        raise ConfigInvalid(
            "self-provided embedding services are not supported; use a platform profile",
            path=path + "/parameters/service_source",
            module="embedding",
        )
    profile = resources.profiles.get(params["profile"])
    if profile is None:
        raise ConfigInvalid("unknown Embedding Profile", path=path + "/parameters/profile", module="embedding")
    settings = DenseSettings.from_parameters(params)
    fields = dict(state.fields)
    projection: dict[str, Any] = {"compose_text": settings.compose_text}
    if settings.compose_text:
        assert settings.composition_field and settings.composition_template
        if settings.composition_field in fields:
            raise ConfigInvalid("duplicate field", path=path + "/parameters/composition_field", module="embedding")
        for name in TEMPLATE_FIELD.findall(settings.composition_template):
            spec = fields.get(name.strip())
            if spec is None or spec.type != "string" or not spec.required:
                raise ConfigInvalid(
                    f"invalid composition source {name}",
                    path=path + "/parameters/composition_template",
                    module="embedding",
                )
        fields[settings.composition_field] = FieldSpec("string", True)
        projection.update(
            composition_field=settings.composition_field, composition_template=settings.composition_template
        )
    for index, (source, vector_name) in enumerate(settings.mappings):
        location = f"{path}/parameters/mappings/{index}"
        spec = fields.get(source)
        if spec is None or spec.type != "string" or not spec.required:
            raise ConfigInvalid(
                "vector source must be a required string field", path=location + "/source_field", module="embedding"
            )
        if vector_name in state.vectors:
            raise ConfigInvalid("duplicate vector", path=location + "/vector_name", module="embedding")
        state.vectors[vector_name] = VectorSpec(source, profile.profile_id, profile.dimensions)
    tokenizer = resources.tokenizer_profiles.get(profile.tokenizer_profile_id or "")
    state.fields = fields
    state.stages.append(EmbedStage(settings, profile, tokenizer))
    state.projection.append(_stage_projection("embedding", node, projection, state.fields))


# ---------------------------------------------------------------------------- index


def _compile_index(
    node: dict[str, Any],
    state: _IngestionState,
    values: SystemValues,
    resources: RuntimeResources,
    environment: Mapping[str, str] | None,
) -> IndexPlan:
    path = _node_path("ingestion", "indexing")
    params = node["parameters"]
    if node["component_id"] != "elasticsearch":  # pragma: no cover - Catalog prevents this
        raise ConfigInvalid("only Elasticsearch indexing is available", path=path + "/component_id")
    credentials = {name: params[name] for name in ES_CREDENTIAL_FIELDS if name in params}
    ordinary = {key: value for key, value in params.items() if key not in ES_CREDENTIAL_FIELDS}
    _no_secret_refs(ordinary, path + "/parameters", values, "indexing")
    _literal(ordinary, path + "/parameters", "indexing")
    connection: dict[str, Any] = {"service_source": params["service_source"]}
    if params["service_source"] == "dev_test" and environment is not None:
        raise ConfigInvalid(
            "Builder test ES is only available in DEV", path=path + "/parameters/service_source", module="indexing"
        )
    for name, value in credentials.items():
        location = f"{path}/parameters/{name}"
        match = EXPRESSION.match(value)
        if match:
            if match[1] not in values.secrets or match[1] in RESERVED_SECRET_KEYS:
                raise ConfigInvalid(f"undeclared System Secret {match[1]}", path=location, module="indexing")
            value = values.secrets[match[1]]
        elif environment is not None or name == "password":
            raise ConfigInvalid("PLED field requires a System Secret reference", path=location, module="indexing")
        connection[name] = value
    fields = dict(state.fields)
    for name, override in params.get("structdata_overrides", {}).items():
        location = f"{path}/parameters/structdata_overrides/{name}"
        if name not in fields:
            raise ConfigInvalid("override targets an unknown field", path=location, module="indexing")
        fields[name] = fields[name].override(override)
        if fields[name].searchable and fields[name].type != "string":
            raise ConfigInvalid("only string fields can be searchable", path=location, module="indexing")
    selected = [params["vector_name"]] if "vector_name" in params else list(params.get("vector_fields", []))
    vectors: Vectors = {}
    for name in selected:
        if name not in state.vectors:
            raise ConfigInvalid(f"unknown vector {name}", path=path + "/parameters/vector_fields", module="indexing")
        vectors[name] = state.vectors[name]
    mappings = index_mappings(fields, vectors, resources.profiles, resources.text_analysis)
    analysis = analysis_settings(resources.text_analysis)
    spaces = {}
    for name, vector in vectors.items():
        profile = resources.profiles[vector.embedding_profile_id]
        spaces[name] = {"model_id": profile.model_id, "model_revision": profile.model_revision}
    projection = {
        "version": FINGERPRINT_VERSION,
        "ingestion": state.projection,
        "index": {
            "component_id": node["component_id"],
            "component_version": node["component_version"],
            "structdata": fields_meta(fields),
            "vector_bindings": {
                name: {
                    "source_field": v.source_field,
                    "embedding_profile_id": v.embedding_profile_id,
                    "dimensions": v.dimensions,
                }
                for name, v in vectors.items()
            },
            "embedding_spaces": spaces,
            "mapping": mappings,
            "settings": {"analysis": analysis, "similarity": {}},
        },
    }
    for error in errors(schema_ref("index_fingerprint.v1.schema.json"), projection):
        raise ConfigInvalid(f"index fingerprint projection invalid: {error.message}", path=path)
    return IndexPlan(
        node["component_id"],
        node["component_version"],
        fields,
        vectors,
        mappings,
        analysis,
        connection,
        projection,
        sha256_hex(projection),
    )


# ---------------------------------------------------------------------------- inference


def _compile_inference(
    config: dict[str, Any], catalog: Catalog, values: SystemValues, index: IndexPlan
) -> InferencePlan:
    lane = "inference"
    nodes = config["pipelines"][lane]
    entry = nodes["inference_input"]
    _descriptor(catalog, lane, "inference_input", entry)
    specs = request_parameters(
        entry["parameters"].get("request_parameters", []),
        _node_path(lane, "inference_input") + "/parameters/request_parameters",
    )
    fixed = list(nodes.get("fixed_filters", []))
    validate_filters(fixed, index.fields, "/config/pipelines/inference/fixed_filters", error=ConfigInvalid)
    segments: dict[str, RemoteSegment | BuiltinRetrieval | None] = {}
    retrieval_refs: RetrievalReferences | None = None
    covered: set[str] = set()
    for module in REMOTE_INFERENCE:
        node = nodes.get(module)
        path = _node_path(lane, module)
        if module in covered:
            if node is not None:
                raise ConfigInvalid("module is covered by a Remote segment", path=path, module=module)
            continue
        if node is None:
            if module == "retrieval":
                raise ConfigInvalid("missing effective module retrieval", path=path, module=module)
            segments[module] = None
            continue
        if node["component_id"] == "remote_api":
            call, _ = _remote_call(lane, module, node, values)
            through = node["through"]
            segments[module] = RemoteSegment(
                module,
                through,
                _covered(REMOTE_INFERENCE, module, through),
                call,
                node["parameters"],
                frozenset(),
                node.get("revision"),
            )
            covered.update(_covered(REMOTE_INFERENCE, module, through))
            continue
        descriptor = _find_descriptor(catalog, lane, module, node)
        params = node["parameters"]
        _no_secret_refs(params, path + "/parameters", values, module)
        refs = _builtin_references(params, specs, values, path, module)
        schema = descriptor["parameters_schema"]
        variable_values = {
            name: _variable_value(values.variables[key], schema, name, path, module)
            for name, key in refs.items()
            if key in values.variables
        }
        # Validate now with the values known at publish time. A reference that only a
        # request can fill is skipped here and checked for each request.
        sample = dict(params)
        deferred: set[str] = set()
        for name, key in refs.items():
            request_spec = specs.get(key)
            if request_spec is not None and request_spec.has_default:
                sample[name] = request_spec.default
            elif name in variable_values:
                sample[name] = variable_values[name]
            else:
                deferred.add(name)
        _check_parameters(schema, sample, path, module, skip=deferred)
        if module == "retrieval":
            # With references, the settings built for each request replace this one.
            segments[module] = _compile_retrieval(sample, index, path, skip=deferred)
            if refs:
                retrieval_refs = RetrievalReferences(dict(params), refs, variable_values, schema)
        else:
            segments[module] = None  # "none" methods
    mcp = nodes.get("mcp", {})
    text_field = mcp.get("text_field", "text")
    spec = index.fields.get(text_field)
    if "text_field" in mcp and (spec is None or spec.type != "string"):
        raise ConfigInvalid(
            "MCP text field must be an effective string field", path="/config/pipelines/inference/mcp/text_field"
        )
    transformation = segments.get("query_transformation")
    retrieval = segments.get("retrieval")
    rerank = segments.get("rerank")
    assert transformation is None or isinstance(transformation, RemoteSegment)
    assert rerank is None or isinstance(rerank, RemoteSegment)
    return InferencePlan(
        request_parameters=specs,
        fixed_filters=fixed,
        transformation=transformation,
        retrieval=retrieval,
        rerank=rerank,
        candidate_fields=index.fields,
        mcp=McpSettings(mcp.get("tool_name", "search"), mcp.get("description"), text_field),
        uses_platform_index=isinstance(retrieval, BuiltinRetrieval),
        retrieval_references=retrieval_refs,
    )


def _builtin_references(
    params: dict[str, Any], specs: dict[str, RequestParameter], values: SystemValues, path: str, module: str
) -> dict[str, str]:
    """Top-level parameters written as ``"{{KEY}}"``. KEY must be a request parameter or a Variable."""
    found: dict[str, str] = {}
    for name, value in params.items():
        location = f"{path}/parameters/{name}"
        match = EXPRESSION.match(value) if isinstance(value, str) else None
        if match is None:
            for _, inner in references(value, location):
                raise ConfigInvalid(
                    'a reference must be the whole value of a top-level parameter, e.g. "{{TOP_N}}"',
                    path=inner,
                    module=module,
                )
            continue
        key = match[1]
        if key not in specs and key not in values.variables:
            raise ConfigInvalid(
                f"{key} is neither an Inference request parameter nor a System Variable", path=location, module=module
            )
        found[name] = key
    return found


def _variable_value(raw: str, schema: dict[str, Any], name: str, path: str, module: str) -> Any:
    """Parse a Variable (always a string) to the parameter's type: strings as is, others as JSON."""
    target = schema.get("properties", {}).get(name, {}).get("type", "string")
    if target == "string":
        return raw
    try:
        return json.loads(raw)
    except ValueError as error:
        raise ConfigInvalid(
            f"System Variable value is not valid JSON for type {target}",
            path=f"{path}/parameters/{name}",
            module=module,
        ) from error


def resolve_retrieval(refs: RetrievalReferences, index: IndexPlan, request_values: dict[str, Any]) -> BuiltinRetrieval:
    """Retrieval settings for one request: request value first, then the parsed Variable."""
    path = _node_path("inference", "retrieval")
    params = dict(refs.parameters)
    for name, key in refs.references.items():
        if key in request_values:
            params[name] = request_values[key]
        elif name in refs.variable_values:
            params[name] = refs.variable_values[name]
        else:
            raise RequestInvalid(
                f"no value for {key}, used by retrieval parameter {name}", path=f"/parameters/{key}", module="retrieval"
            )
    try:
        _check_parameters(refs.schema, params, path, "retrieval")
        return _compile_retrieval(params, index, path)
    except ConfigInvalid as error:
        location = (error.path or "").removeprefix(path + "/parameters/").split("/")[0]
        source = refs.references.get(location)
        raise RequestInvalid(
            f"invalid retrieval parameter {location}: {error.message}",
            path=f"/parameters/{source}" if source else "/parameters",
            module="retrieval",
        ) from error


def _compile_retrieval(
    params: dict[str, Any], index: IndexPlan, path: str, skip: set[str] | None = None
) -> BuiltinRetrieval:
    """Check the parameters against the index. Field lists named in ``skip`` are not checked."""
    skip = skip or set()
    vector_fields = () if "vector_fields" in skip else tuple(params.get("vector_fields", []))
    fulltext_fields = () if "fulltext_fields" in skip else tuple(params.get("fulltext_fields", []))
    group_by = () if "group_by" in skip else tuple(params.get("group_by", []))
    for position, name in enumerate(vector_fields):
        if name not in index.vectors:
            raise ConfigInvalid(
                "vector field is not in the index",
                path=f"{path}/parameters/vector_fields/{position}",
                module="retrieval",
            )
    for position, name in enumerate(fulltext_fields):
        spec = index.fields.get(name.removeprefix("structdata."))
        if spec is None or not spec.searchable:
            raise ConfigInvalid(
                "full-text field is not searchable",
                path=f"{path}/parameters/fulltext_fields/{position}",
                module="retrieval",
            )
    for position, name in enumerate(group_by):
        spec = index.fields.get(name.removeprefix("structdata."))
        if name != "document_id" and (spec is None or spec.type != "string"):
            raise ConfigInvalid(
                "group_by needs document_id or a string field",
                path=f"{path}/parameters/group_by/{position}",
                module="retrieval",
            )
    routes = len(vector_fields) + len(fulltext_fields)
    if routes > 1 and "fusion" not in params:
        raise ConfigInvalid(
            "fusion is required for multiple search routes", path=path + "/parameters", module="retrieval"
        )
    return BuiltinRetrieval(
        vector_fields=vector_fields,
        fulltext_fields=tuple(name.removeprefix("structdata.") for name in fulltext_fields),
        per_route_k=params["per_route_k"],
        fusion=params.get("fusion"),
        rrf_k=params.get("rrf_k", 60),
        group_by=group_by,
        top_n=params.get("top_n"),
    )


# ---------------------------------------------------------------------------- entry point


def compile_system(
    config: dict[str, Any],
    catalog: Catalog,
    *,
    environment: Mapping[str, str] | None = None,
) -> CompiledSystem:
    """Validate and compile ``config``. ``environment`` is None in DEV (values in Config)."""
    _shape(config)
    values = load_values(config, environment)
    ingestion, state, indexing = _compile_ingestion(config, catalog, values)
    index = _compile_index(indexing, state, values, catalog.resources, environment)
    inference = _compile_inference(config, catalog, values, index)
    return CompiledSystem(config, values, ingestion, index, inference)
