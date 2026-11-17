"""Offline proof for the Inference Descriptor examples. No provider or DB calls.

Only this fixture's boundary bindings, field inheritance, and option sources are
resolved here. This is not a generic Descriptor compiler or an Inference API.
"""
from copy import deepcopy
from math import isfinite
import json
import runpy

from jsonschema import Draft202012Validator as V

from validate_examples import (
    HERE, MISSING, binding_parent, get, inspect_schema, must_fail, read,
    registry, require, tokens, validate_config, validate_descriptor, value_of,
)

BINDING = "urn:retrieval-builder:index-binding:0.2-draft"
FIELDS = "/result_sets/*/items/*/chunk/fields"
FORMAT_DEFS = json.loads((HERE.parent / "pydantic_contracts/artifact_definitions.json").read_text())
OPERATIONS = runpy.run_path(str(HERE.parent / "inference/python_example.py"))


def data_node(schema, path, create=False):
    """Paths are relative to one QueryContext, even when the wire root is a list."""
    node = schema.setdefault("items", {}) if create else schema.get("items", MISSING)
    for name in tokens(path):
        if node is MISSING:
            break
        if name == "*":
            if create:
                node.setdefault("type", "array")
                node = node.setdefault("items", {})
            else:
                node = node.get("items", MISSING)
        elif create:
            node.setdefault("type", "object")
            node = node.setdefault("properties", {}).setdefault(name, {})
        else:
            node = node.get("properties", {}).get(name, MISSING)
    return node


def compile_boundary(descriptor, side, config, facts, upstream=None):
    boundary = descriptor["io"][side]
    spec = deepcopy(boundary.get("constraints", {}))
    for b in boundary.get("schema_bindings", []):
        node, key = binding_parent(spec, b["path"])
        value = value_of(b["value"], config, None, facts)
        require(value is not MISSING, "unresolved boundary binding: " + b["path"])
        node[key] = deepcopy(value)
    for rule in boundary.get("inherit", []):
        if isinstance(rule, str):
            if upstream is None:
                continue
            dest, inherited = rule, data_node(upstream, rule)
            if inherited is MISSING:
                # In this fixture, no additional constraints means retain the base contract.
                continue
        else:
            dest = rule["target"]
            inherited = get(facts, rule["source"]["path"])
            require(isinstance(inherited, dict) and inherited.get("type") == "object",
                    "unresolved declared object for Context inheritance")
            inspect_schema(inherited)
        node = data_node(spec, dest, create=True)
        for key, value in inherited.items():
            require(key not in node or node[key] == value, "conflicting inherited Schema: " + dest)
            node[key] = deepcopy(value)
    inspect_schema(spec)
    return spec


def wire_validator(descriptor, side, spec):
    # The referenced contract is already QueryContext[]. No second array wrapper.
    return V({"allOf": [{"$ref": descriptor["io"][side]["contract_ref"]}, spec]}, registry=registry())


def config_values(value, path):
    parts = tokens(path)
    def visit(node, rest, actual):
        if not rest:
            yield actual, node
        elif rest[0] == "*":
            require(isinstance(node, list), "expected array at " + actual)
            for i, item in enumerate(node):
                yield from visit(item, rest[1:], f"{actual}/{i}")
        else:
            require(isinstance(node, dict) and rest[0] in node, "missing config at " + path)
            yield from visit(node[rest[0]], rest[1:], actual + "/" + rest[0])
    return list(visit(value, parts, ""))


def option_values(source, facts, upstream=None):
    path = source["source"]["path"]
    if source["source"]["side"] == "context":
        value = get(facts, path)
        require(isinstance(value, (list, dict)), "unresolved option source: " + path)
        return set(value)
    require(source["source"]["side"] == "input" and upstream is not None, "missing input Schema")
    spec = data_node(upstream, path)
    require(spec is not MISSING, "unresolved option source: " + path)
    f = source.get("filter", {})
    return {name for name, p in spec.get("properties", {}).items()
            if (not f.get("types") or p.get("type") in f["types"])
            and (not f.get("required") or name in spec.get("required", []))}


def check_config(descriptor, cfg, facts, upstream=None):
    validate_config(descriptor, cfg, facts)
    for source in descriptor.get("option_sources", []):
        allowed = option_values(source, facts, upstream)
        for path, value in config_values(cfg, source["target"]):
            require(value in allowed, "unavailable option at " + path + ": " + value)


def provider_rewrite_schema(count):
    return {"type": "object", "additionalProperties": False, "required": ["queries"],
            "properties": {"queries": {"type": "array", "minItems": count, "maxItems": count,
                                       "items": {"type": "string", "minLength": 1}}}}


def rewrite_seed(initial, response, config):
    V(provider_rewrite_schema(config["count"])).validate(response)
    queries = [q.strip() for q in response["queries"]]
    require(all(queries), "blank rewritten query")
    seed = initial[0]
    if config["include_original"]:
        queries.insert(0, seed["ori_query"])
    return [dict(deepcopy(seed), query=q, result_sets=[]) for q in queries]


def index_route_keys(binding, config):
    V({"$ref": BINDING}, registry=registry()).validate(binding)
    formats = {d["artifact_type"]: d["target_schema"] for d in FORMAT_DEFS}
    kind = binding["artifact_type"]
    require(kind in formats, "unregistered IndexBinding format")
    V(formats[kind]).validate(binding.get("target", {}))
    fulltext, vector = config["fulltext_fields"], config["vector_fields"]
    require(fulltext or vector, "select at least one search field")
    if config["output_mode"] == "backend_fused":
        require(kind == "builtin.elasticsearch/v1" and fulltext and vector,
                "backend_fused needs a compatible hybrid Adapter")
        return ["es_hybrid"]
    return [*("fulltext:" + f for f in fulltext), *("vector:" + f for f in vector)]


def check_request_filters(contexts, binding):
    for context in contexts:
        for f in context.get("filters", []):
            require(f["field"] in binding.get("filter_fields", []), "request filter not indexed")


def check_query_encoders(config, binding, encoders):
    for name in config["vector_fields"]:
        vector = binding["vector_bindings"][name]
        encoder = encoders.get(vector["embedding_profile_id"])
        require(encoder is not None and encoder["dimensions"] == vector["dimensions"],
                "no compatible query encoder for vector: " + name)


def materialize_hybrid(contexts, hits, chunks):
    require(len(contexts) == len(hits), "missing search response")
    by_id = {c["chunk_id"]: c for c in chunks}
    def items(rows):
        return [{"chunk": deepcopy(by_id[h["chunk_id"]]), "score": h["score"]} for h in rows]
    return [dict(deepcopy(c), result_sets=[{"key": "es_hybrid", "items": items(rows)}])
            for c, rows in zip(contexts, hits)]


def check_route_keys(contexts, keys):
    for c in contexts:
        actual = [r["key"] for r in c["result_sets"]]
        require(len(actual) == len(set(actual)) and set(actual) == set(keys),
                "missing, duplicate or unexpected ResultSet.key")


def check_sum_score(result_sets, comparable):
    require(comparable, "score comparability must be established by the plan")
    require(all(isinstance(i.get("score"), (int, float)) and not isinstance(i["score"], bool)
                and isfinite(i["score"]) for r in result_sets for i in r["items"]),
            "Sum Score requires finite scores")


def main():
    names = ["query_transformation", "retrieval", "rerank"]
    q, r, rank = [read(name, "descriptor") for name in names]
    f = json.loads((HERE / "inference.fixture.json").read_text())
    qc, rc, rankc = [f["configs"][name] for name in names]
    for d in (q, r, rank):
        validate_descriptor(d)
    initial, binding = f["initial"], f["index_binding"]
    facts = {"inference": {
        "llm_profiles": ["llm.main"],
        "rewrite": {"output_count": qc["count"] + int(qc["include_original"])},
        "index_binding": binding,
        "retrieval": {"result_set_keys": index_route_keys(binding, rc),
                      "hydrated_fields": f["stored_fields_contract"]},
        "rerank": {"services": ["rerank.main"], "input_result_set_keys": index_route_keys(binding, rc),
                   "current_query_available": True, "top_n": f["result_plan"]["rerank_top_n"]},
    }}
    check_config(q, qc, facts)
    qi = compile_boundary(q, "input", qc, facts)
    qo = compile_boundary(q, "output", qc, facts, qi)
    wire_validator(q, "input", qi).validate(initial)
    rewritten = rewrite_seed(initial, f["provider_rewrites"], qc)
    wire_validator(q, "output", qo).validate(rewritten)
    assert len(rewritten) == 3 and all(x["ori_query"] == initial[0]["ori_query"]
                                       and x["metadata"] == initial[0]["metadata"]
                                       and x["filters"] == initial[0]["filters"] for x in rewritten)
    no_original = dict(qc, include_original=False)
    no_original_facts = deepcopy(facts)
    no_original_facts["inference"]["rewrite"]["output_count"] = qc["count"]
    qo2 = compile_boundary(q, "output", no_original, no_original_facts, qi)
    wire_validator(q, "output", qo2).validate(rewrite_seed(initial, f["provider_rewrites"], no_original))
    assert qo2["maxItems"] == 2 and qo["maxItems"] == 3

    check_config(r, rc, facts)
    check_query_encoders(rc, binding, f["query_encoders"])
    wire_validator(r, "input", compile_boundary(r, "input", rc, facts)).validate(rewritten)
    check_request_filters(rewritten, binding)
    ro = compile_boundary(r, "output", rc, facts, qo)
    hits = materialize_hybrid(rewritten, f["hybrid_hits"], f["chunks"])
    wire_validator(r, "output", ro).validate(hits)
    check_route_keys(hits, ["es_hybrid"])
    assert hits[1]["result_sets"][0]["items"] == []

    # The same Descriptor also handles Local independent routes, with no new DTO.
    lc = dict(rc, output_mode="independent")
    local = dict(binding, artifact_type="builtin.local_search/v1", target={})
    local_keys = index_route_keys(local, lc)
    assert local_keys == ["fulltext:fields.body_text", "vector:body_vec"]
    lf = deepcopy(facts)
    lf["inference"].update(index_binding=local)
    lf["inference"]["retrieval"]["result_set_keys"] = local_keys
    check_config(r, lc, lf)
    check_query_encoders(lc, local, f["query_encoders"])
    lo = compile_boundary(r, "output", lc, lf, qo)
    lr = [dict(deepcopy(rewritten[0]), result_sets=[{"key": k, "items": []} for k in local_keys])]
    lr[0]["result_sets"][0]["items"] = [{"chunk": f["chunks"][0]}]  # rank-only is legal
    wire_validator(r, "output", lo).validate(lr)
    check_route_keys(lr, local_keys)
    assert OPERATIONS["rrf"](lr[0]["result_sets"])["items"][0]["score"] > 0

    assert option_values(rank["option_sources"][1], facts, ro) == {"body_text", "title"}
    check_config(rank, rankc, facts, ro)
    wire_validator(rank, "input", compile_boundary(rank, "input", rankc, facts)).validate(hits)
    rko = compile_boundary(rank, "output", rankc, facts, ro)
    ranked = OPERATIONS["rerank"](hits, f["rerank_scores"], f["result_plan"]["rerank_top_n"])
    wire_validator(rank, "output", rko).validate(ranked)
    assert data_node(rko, FIELDS) == data_node(ro, FIELDS)
    assert ranked[0]["result_sets"][0]["items"][0]["chunk"]["chunk_id"] == "c2"
    assert ranked[0]["result_sets"][0]["items"][0]["score"] == 0.92
    assert ranked[1]["result_sets"][0]["items"] == []
    fused_after_rank = OPERATIONS["cross_query_merge"](ranked, n=2)
    V({"$ref": r["io"]["output"]["contract_ref"]}, registry=registry()).validate(fused_after_rank)
    assert len(fused_after_rank[0]["result_sets"][0]["items"]) == 2  # plan has its own cap
    # None bypasses the Component; rank-only lists keep their original valid boundary.
    wire_validator(r, "output", lo).validate(lr)
    assert "score" not in lr[0]["result_sets"][0]["items"][0]

    merged_facts = deepcopy(facts)
    merged_facts["inference"]["rerank"]["current_query_available"] = False
    merged = OPERATIONS["cross_query_merge"](hits, n=2)
    merged_facts["inference"]["rerank"]["input_result_set_keys"] = [
        rs["key"] for rs in merged[0]["result_sets"]
    ]
    # The before-rerank plan retains the key and hydrated fields; collapse to one context.
    merged_input = dict(deepcopy(ro), maxItems=1)
    wire_validator(r, "output", merged_input).validate(merged)
    original = dict(rankc, query_source="original")
    check_config(rank, original, merged_facts, merged_input)
    mo = compile_boundary(rank, "output", original, merged_facts, merged_input)
    wire_validator(rank, "output", mo).validate(OPERATIONS["rerank"](merged, f["rerank_scores"], 1))

    negatives = 0
    def neg(label, call):
        nonlocal negatives
        must_fail(label, call)
        negatives += 1
    for d in (q, r, rank):
        bad = deepcopy(d)
        bad["io"]["output"]["shape"] = "list"
        neg("QueryContext[] cannot be wrapped again", lambda: validate_descriptor(bad))
    def bad_binding(label, path):
        d = deepcopy(q)
        d["io"]["output"]["schema_bindings"][0]["path"] = path
        neg(label, lambda: validate_descriptor(d))
    bad_binding("binding must not modify ref", "/$ref")
    bad_binding("binding parent absent", "/properties/missing/maxItems")
    bad_binding("cannot bind inside example data", "/default/maxItems")
    d = deepcopy(q); del d["io"]["output"]["constraints"]
    neg("binding requires declared constraints", lambda: validate_descriptor(d))
    d = deepcopy(r); d["io"]["output"]["inherit"][-1]["source"]["path"] = "/secrets"
    neg("unregistered inheritance source", lambda: validate_descriptor(d))
    d = deepcopy(q); d["io"]["output"]["schema_bindings"][0]["value"]["path"] = "/missing"
    neg("unknown fact cannot resolve", lambda: compile_boundary(d, "output", qc, facts))
    neg("model cannot return only one rewrite", lambda: rewrite_seed(initial, {"queries": ["a"]}, qc))
    neg("model cannot send filters", lambda: rewrite_seed(initial, dict(f["provider_rewrites"], filters=[]), qc))
    neg("whitespace rewrite", lambda: rewrite_seed(initial, {"queries": ["   ", "a"]}, qc))
    neg("public output count mismatch", lambda: wire_validator(q, "output", qo).validate(rewritten[:2]))
    neg("wrong wrapper", lambda: wire_validator(q, "output", qo).validate({"data": rewritten}))
    neg("unavailable LLM", lambda: check_config(q, dict(qc, llm_ref="missing"), facts))
    neg("unindexed text", lambda: check_config(r, dict(rc, fulltext_fields=["fields.title"]), facts))
    neg("unknown vector", lambda: check_config(r, dict(rc, vector_fields=["missing"]), facts))
    neg("unindexed config filter", lambda: check_config(r, dict(rc, filters=[{"field": "fields.title", "operator": "eq", "value": "x"}]), facts))
    neg("unsupported range operator", lambda: check_config(r, dict(rc, filters=[{"field": "metadata.department", "operator": "gt", "value": "x"}]), facts))
    neg("wrong filter value type", lambda: check_config(r, dict(rc, filters=[{"field": "metadata.department", "operator": "eq", "value": ["x"]}]), facts))
    neg("unindexed request filter", lambda: check_request_filters([dict(initial[0], filters=[{"field": "fields.title", "operator": "eq", "value": "x"}])], binding))
    neg("Local cannot pretend backend fusion", lambda: index_route_keys(local, rc))
    neg("no route", lambda: index_route_keys(binding, dict(lc, fulltext_fields=[], vector_fields=[])))
    neg("unregistered index format", lambda: index_route_keys(dict(binding, artifact_type="unknown"), rc))
    neg("wrong index target", lambda: index_route_keys(dict(binding, target={}), rc))
    neg("same dimension does not imply Profile compatibility", lambda: check_query_encoders(rc, binding, {"other-profile": {"dimensions": 3}}))
    neg("wrong query encoder dimension", lambda: check_query_encoders(rc, binding, {"example.embedding/v1": {"dimensions": 5}}))
    wrong = deepcopy(hits); wrong[0]["result_sets"][0]["key"] = "fulltext:fields.body_text"
    neg("ES fused key cannot be split", lambda: wire_validator(r, "output", ro).validate(wrong))
    wrong = deepcopy(hits); wrong[0]["result_sets"] *= 2
    neg("duplicate ResultSet key", lambda: check_route_keys(wrong, ["es_hybrid"]))
    wrong = deepcopy(hits); wrong[0]["result_sets"][0]["items"] *= 2
    neg("Retrieval limit per list", lambda: wire_validator(r, "output", ro).validate(wrong))
    neg("Sum Score without numeric scores", lambda: check_sum_score(lr[0]["result_sets"], True))
    neg("Sum Score with incomparable numeric scores", lambda: check_sum_score(hits[0]["result_sets"], False))
    neg("non-text rerank field", lambda: check_config(rank, dict(rankc, content_fields=["page"]), facts, ro))
    neg("current query unavailable after cross-query merge", lambda: check_config(rank, rankc, merged_facts, merged_input))
    bad_facts = deepcopy(facts)
    del bad_facts["inference"]["retrieval"]["hydrated_fields"]
    neg("unknown stored-fields guarantee", lambda: compile_boundary(r, "output", rc, bad_facts, qo))
    changed = deepcopy(facts)
    contract = changed["inference"]["retrieval"]["hydrated_fields"]
    contract["properties"]["heading"] = contract["properties"].pop("title")
    contract["required"].remove("title"); contract["required"].append("heading")
    ro_changed = compile_boundary(r, "output", rc, changed, qo)
    assert option_values(rank["option_sources"][1], changed, ro_changed) == {"body_text", "heading"}
    neg("rename invalidates old Rerank field", lambda: check_config(rank, rankc, changed, ro_changed))
    optional = deepcopy(facts)
    optional["inference"]["retrieval"]["hydrated_fields"]["required"].remove("title")
    ro_optional = compile_boundary(r, "output", rc, optional, qo)
    neg("optional field cannot be a guaranteed Rerank input", lambda: check_config(rank, rankc, optional, ro_optional))
    wrong = deepcopy(ranked); del wrong[0]["result_sets"][0]["items"][0]["score"]
    neg("Rerank score must be present", lambda: wire_validator(rank, "output", rko).validate(wrong))
    neg("Rerank Top N is an upper bound", lambda: wire_validator(rank, "output", rko).validate(hits))
    neg("nonfinite model score", lambda: OPERATIONS["rerank"](hits, dict(f["rerank_scores"], c1=float("inf")), 1))
    print(json.dumps({"descriptors": len(names), "negative_cases": negatives,
                      "plans": ["rewrite + ES hybrid + rerank", "local independent + RRF", "cross-query merge before and after rerank"],
                      "not_checked": ["real services", "full compiler/Registry/UI", "Q-014 production defaults"]}))


if __name__ == "__main__":
    main()
