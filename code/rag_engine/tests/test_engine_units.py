"""Unit tests for pure Engine pieces: chunking, result processing, filters, compiler, fingerprint, ES mapping."""

from __future__ import annotations

import copy
import json

import pytest

from conftest import FIXTURES, scenario_config
from rag_engine.adapters.es_mapping import analysis_settings, field_mapping, filter_clauses, index_mappings
from rag_engine.adapters.tokenizer import SimpleTokenizer
from rag_engine.components import results
from rag_engine.components.chunking import ChunkSettings, chunk_documents, markdown_sections, split_text
from rag_engine.core.canonical import chunk_data_id, sha256_hex
from rag_engine.core.errors import ConfigInvalid, DocumentFailed, EngineError, RequestInvalid
from rag_engine.core.filters import matches, validate_filters
from rag_engine.core.resources import fixture_resources
from rag_engine.core.types import FieldSpec
from rag_engine.engine.catalog import build_catalog
from rag_engine.engine.compiler import compile_system, resolve_retrieval

TOKENIZER = SimpleTokenizer("fixture@1")


def settings(
    max_tokens: int = 10,
    overlap: int = 2,
    separators: tuple[str, ...] = ("\n\n", "\n", "。", ""),
    method: str = "recursive",
    header_levels: tuple[int, ...] = (1, 2, 3),
) -> ChunkSettings:
    return ChunkSettings(
        "body", "text", (("title", "title"),), max_tokens, overlap, separators, False, method, header_levels
    )


# ---------------------------------------------------------------- chunking


def test_chunks_are_substrings_within_the_token_limit() -> None:
    text = "第一段說明清潔散熱孔。第二段說明更換濾網。\n\n第三段說明檢查風扇轉速是否正常。"
    chunks = split_text(text, settings(), TOKENIZER)
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk in text
        assert len(TOKENIZER.spans(chunk)) <= 10


def test_overlap_repeats_trailing_pieces() -> None:
    text = "甲乙。丙丁。戊己。庚辛。壬癸。"
    chunks = split_text(text, settings(max_tokens=6, overlap=3), TOKENIZER)
    assert len(chunks) >= 2
    assert all(chunks[i][-2:] == chunks[i + 1][:2] for i in range(len(chunks) - 1))


def test_hard_split_without_separators() -> None:
    text = "一" * 25
    chunks = split_text(text, settings(max_tokens=10, overlap=0, separators=("",)), TOKENIZER)
    assert [len(chunk) for chunk in chunks] == [10, 10, 5]


def test_chunk_ids_follow_the_document_identity_rule() -> None:
    units = [{"document_id": "doc-1", "structdata": {"body": "短文。", "title": "T"}, "metadata": {"a": 1}}]
    chunks = chunk_documents(units, settings(), TOKENIZER)
    assert chunks[0]["data_id"] == chunk_data_id("doc-1", 0, 0) == sha256_hex(["doc-1", 0, 0])
    assert chunks[0]["structdata"] == {"text": "短文。", "title": "T"}
    assert chunks[0]["metadata"] == {"a": 1}
    with pytest.raises(DocumentFailed):
        chunk_documents([{"document_id": "d", "structdata": {"body": "   "}}], settings(), TOKENIZER)


# ---------------------------------------------------------------- fixed-size (03#chunking acceptance cases)


def fixed(text: str, max_tokens: int, overlap: int) -> list[str]:
    return split_text(text, settings(max_tokens, overlap, method="fixed_size"), TOKENIZER)


def test_fixed_size_windows_follow_the_spec_example() -> None:
    # The test tokenizer counts one token per CJK character.
    assert fixed("一二三四五六七八九十壹", 4, 1) == ["一二三四", "四五六七", "七八九十", "十壹"]  # 11 tokens
    assert fixed("一二三四五六七八九十", 4, 1) == ["一二三四", "四五六七", "七八九十"]  # ends at [6:10]


def test_fixed_size_edge_cases() -> None:
    assert fixed("一二三四五六七八", 4, 0) == ["一二三四", "五六七八"]  # exact blocks, no overlap-only chunk
    assert fixed("一二", 4, 1) == ["一二"]  # short document: one chunk, not padded
    assert fixed("一二三四五", 4, 0) == ["一二三四", "五"]  # last block shorter than size
    # Cuts fall on token offsets: spaces inside a window stay, a space on the cut drops out.
    assert fixed("alpha beta gamma delta", 2, 0) == ["alpha beta", "gamma delta"]
    # Non-BMP characters (emoji, CJK Extension B) are whole characters, never cut in half.
    text = "😀一𠀀二😀三"
    chunks = fixed(text, 2, 1)
    assert chunks == ["😀一", "一𠀀", "𠀀二", "二😀", "😀三"]
    assert all(chunk in text for chunk in chunks)


def test_fixed_size_ignores_recursive_and_heading_settings() -> None:
    text = "第一段。\n\n# 標題\n第二段。"
    base = split_text(text, settings(4, 1, method="fixed_size"), TOKENIZER)
    other = split_text(text, settings(4, 1, separators=("。",), method="fixed_size", header_levels=(1,)), TOKENIZER)
    assert base == other


# ---------------------------------------------------------------- header-aware (03#header-aware-rules)

MARKDOWN = """前言說明。
# 第一章
內容一。
## 1.1 小節
內容二。
```
# 程式碼裡的井號
```
#標籤 不是標題
#### 深層標題
內容三。
# 第二章
內容四。"""


def test_markdown_sections_follow_the_heading_rules() -> None:
    sections = [MARKDOWN[start:end].strip() for start, end in markdown_sections(MARKDOWN, (1, 2, 3))]
    assert sections == [
        "前言說明。",  # text before the first heading is its own section
        "# 第一章\n內容一。",
        "## 1.1 小節\n內容二。\n```\n# 程式碼裡的井號\n```\n#標籤 不是標題\n#### 深層標題\n內容三。",
        "# 第二章\n內容四。",
    ]
    level_one = [MARKDOWN[start:end].strip() for start, end in markdown_sections(MARKDOWN, (1,))]
    assert len(level_one) == 3  # "## 1.1" is not a split level, so it stays inside chapter one
    assert level_one[1].startswith("# 第一章") and "## 1.1 小節" in level_one[1]

    # "~~~" fences, up to three leading spaces, and CRLF line ends.
    text = "~~~\n# x\n~~~\n   ### 縮排標題\n文字\r\n# 下一節\r\n"
    assert [text[start:end].strip() for start, end in markdown_sections(text, (1, 2, 3))] == [
        "~~~\n# x\n~~~",
        "### 縮排標題\n文字",
        "# 下一節",
    ]


def test_header_aware_keeps_sections_apart_and_falls_back_to_recursive() -> None:
    chunks = split_text(MARKDOWN, settings(200, 0, method="header_aware"), TOKENIZER)
    assert chunks[0] == "前言說明。" and chunks[1] == "# 第一章\n內容一。" and chunks[-1] == "# 第二章\n內容四。"

    # A long section is split with Recursive inside it; the heading starts its first chunk and
    # no chunk crosses into the next section.
    long_text = "# 甲\n" + "一二三四五。" * 6 + "\n# 乙\n短。"
    chunks = split_text(long_text, settings(8, 2, method="header_aware"), TOKENIZER)
    assert chunks[0].startswith("# 甲") and chunks[-1] == "# 乙\n短。"
    assert all("乙" not in chunk for chunk in chunks[:-1])
    assert all(len(TOKENIZER.spans(chunk)) <= 8 for chunk in chunks)

    # Without headings the result equals Recursive on the whole text.
    plain = "第一段說明清潔散熱孔。第二段說明更換濾網。\n\n第三段說明檢查風扇轉速是否正常。"
    assert split_text(plain, settings(method="header_aware"), TOKENIZER) == split_text(plain, settings(), TOKENIZER)


def chunking_config(component_id: str, **parameters: object) -> dict:
    config = scenario_config()
    node = config["pipelines"]["ingestion"]["chunking"]
    node["component_id"] = component_id
    node["parameters"].update(parameters)
    return config


def test_chunking_methods_compile_with_their_own_fingerprint_inputs() -> None:
    catalog = build_catalog("dev-runtime", fixture_resources())
    assert {item["component_id"] for item in catalog.descriptors if item["module"] == "chunking"} == {
        "recursive",
        "fixed_size",
        "header_aware",
    }
    recursive = compile_system(scenario_config(), catalog)
    fixed_size = compile_system(chunking_config("fixed_size"), catalog)
    header_aware = compile_system(chunking_config("header_aware"), catalog)
    assert len({recursive.fingerprint, fixed_size.fingerprint, header_aware.fingerprint}) == 3

    projection = {stage["module"]: stage for stage in header_aware.index.projection["ingestion"]}["chunking"]
    assert projection["parameters"]["header_levels"] == [1, 2, 3]  # the Descriptor default
    fixed_projection = {stage["module"]: stage for stage in fixed_size.index.projection["ingestion"]}["chunking"]
    assert "separators" not in fixed_projection["parameters"]
    assert compile_system(chunking_config("header_aware", header_levels=[1]), catalog).fingerprint != (
        header_aware.fingerprint
    )
    # Fixed-size has no separators parameter in its Descriptor.
    with pytest.raises(ConfigInvalid) as raised:
        compile_system(chunking_config("fixed_size", separators=["。"]), catalog)
    assert raised.value.path == "/config/pipelines/ingestion/chunking/parameters"


# ---------------------------------------------------------------- result processing


def item(data_id: str, score: float | None, document_id: str = "d", **fields: str) -> dict:
    return {"data": {"document_id": document_id, "data_id": data_id, "structdata": fields}, "score": score}


def test_rrf_fusion_orders_by_reciprocal_rank() -> None:
    bm25 = [item("A", 9.0), item("B", 5.0)]
    vector = [item("B", 0.9), item("C", 0.8)]
    fused = results.fuse([bm25, vector], "rrf")
    assert [entry["data"]["data_id"] for entry in fused] == ["B", "A", "C"]
    with pytest.raises(EngineError):
        results.fuse([bm25, vector], None)


def test_group_by_keeps_best_and_singletons_with_missing_keys() -> None:
    items = [item("A", 0.9, "d1"), item("B", 0.8, "d1"), item("C", 0.7, "d2"), item("D", 0.6, "d3")]
    assert [x["data"]["data_id"] for x in results.group_by(items, ["document_id"])] == ["A", "C", "D"]
    tagged = [item("A", 0.9, team="x"), item("B", 0.8), item("C", 0.95, team="x")]
    assert [x["data"]["data_id"] for x in results.group_by(tagged, ["structdata.team"])] == ["B", "C"]


def test_cross_query_merge_and_final_context() -> None:
    q1 = {"query": "q1", "result_sets": [{"key": "r", "items": [item("A", 0.82), item("B", 0.75)]}]}
    q2 = {"query": "q2", "result_sets": [{"key": "r", "items": [item("A", 0.91), item("C", 0.78)]}]}
    merged = results.cross_query_merge([q1, q2], None, None)
    assert [(x["data"]["data_id"], x["score"]) for x in merged] == [("A", 0.91), ("C", 0.78), ("B", 0.75)]
    initial = {"ori_query": "原始", "filters": [], "metadata": {}}
    final = results.finalize([q1, q2], initial, merged)
    assert final["query"] == final["ori_query"] == "原始"
    assert final["result_sets"] == [{"key": "final", "items": merged}]


# ---------------------------------------------------------------- filters


FIELDS = {
    "price": FieldSpec("number", False, filterable=True),
    "tags": FieldSpec("string_array", False, filterable=True),
    "at": FieldSpec("datetime", False, filterable=True),
    "title": FieldSpec("string", True),
}


def test_filter_validation_and_semantics() -> None:
    validate_filters([{"field": "structdata.price", "operator": "gte", "value": 300}], FIELDS, "/filters")
    with pytest.raises(EngineError) as raised:
        validate_filters([{"field": "structdata.title", "operator": "eq", "value": "x"}], FIELDS, "/filters")
    assert raised.value.path == "/filters/0/field"
    with pytest.raises(EngineError):
        validate_filters([{"field": "structdata.tags", "operator": "gt", "value": "x"}], FIELDS, "/filters")
    with pytest.raises(EngineError):
        validate_filters([{"field": "structdata.price", "operator": "eq", "value": "300"}], FIELDS, "/filters")
    record = {"price": 350, "tags": ["AI", "ML"], "at": "2026-11-16T09:30:00+08:00"}
    assert matches([{"field": "structdata.tags", "operator": "eq", "value": "AI"}], record, FIELDS)
    assert matches(
        [
            {
                "any": [
                    {"field": "structdata.price", "operator": "lt", "value": 100},
                    {"field": "structdata.tags", "operator": "in", "value": ["ML"]},
                ]
            }
        ],
        record,
        FIELDS,
    )
    assert matches([{"field": "structdata.at", "operator": "gte", "value": "2026-11-16T01:00:00Z"}], record, FIELDS)
    assert not matches([{"field": "structdata.tags", "operator": "eq", "value": "AI"}], {"tags": []}, FIELDS)


# ---------------------------------------------------------------- compiler and fingerprint


def test_fingerprint_matches_the_contract_fixture() -> None:
    expected = json.loads((FIXTURES / "index_fingerprint.v1.example.json").read_text())
    assert sha256_hex(expected["projection"]) == expected["mapping_meta"]["index_fingerprint"]
    compiled = compile_system(scenario_config(), build_catalog("dev-runtime", fixture_resources()))
    assert compiled.index.projection == expected["projection"]
    assert compiled.fingerprint == expected["mapping_meta"]["index_fingerprint"]


def test_fingerprint_ignores_query_settings_and_tracks_chunking() -> None:
    catalog = build_catalog("dev-runtime", fixture_resources())
    base = compile_system(scenario_config(), catalog).fingerprint
    query_only = scenario_config()
    query_only["pipelines"]["inference"]["retrieval"]["parameters"]["top_n"] = 3
    assert compile_system(query_only, catalog).fingerprint == base
    reordered = json.loads(json.dumps(scenario_config(), sort_keys=True))
    assert compile_system(reordered, catalog).fingerprint == base
    chunking = scenario_config()
    chunking["pipelines"]["ingestion"]["chunking"]["parameters"]["max_tokens"] = 400
    assert compile_system(chunking, catalog).fingerprint != base


def test_compiler_rejects_unavailable_components_and_bad_references() -> None:
    catalog = build_catalog("dev-runtime", fixture_resources())
    config = scenario_config()
    config["pipelines"]["inference"]["query_transformation"] = {
        "component_id": "rewrite",
        "component_version": "1.0.0",
        "parameters": {},
    }
    with pytest.raises(ConfigInvalid) as raised:
        compile_system(config, catalog)
    assert raised.value.path == "/config/pipelines/inference/query_transformation/component_id"
    config = scenario_config()
    config["pipelines"]["ingestion"]["chunking"]["parameters"]["max_tokens"] = "{{SIZE}}"
    with pytest.raises(ConfigInvalid):
        compile_system(config, catalog)
    config = scenario_config()
    config["pipelines"]["inference"]["fixed_filters"] = [{"field": "structdata.body", "operator": "eq", "value": "x"}]
    with pytest.raises(ConfigInvalid) as raised:
        compile_system(config, catalog)
    assert raised.value.path == "/config/pipelines/inference/fixed_filters/0/field"


def reference_config(variables: dict[str, str], **retrieval: object) -> dict:
    """Scenario Config whose built-in Retrieval parameters use ``{{KEY}}`` references."""
    config = scenario_config()
    inference = config["pipelines"]["inference"]
    inference["inference_input"]["parameters"]["request_parameters"] = [
        {"name": "TOP_N", "type": "integer", "required": False},
        {"name": "K", "type": "integer", "required": True},
    ]
    inference["retrieval"]["parameters"].update(retrieval)
    config["variable"] = variables
    return config


def test_builtin_retrieval_parameters_resolve_request_then_variable() -> None:
    catalog = build_catalog("dev-runtime", fixture_resources())
    compiled = compile_system(reference_config({"TOP_N": "2"}, top_n="{{TOP_N}}", per_route_k="{{K}}"), catalog)
    refs = compiled.inference.retrieval_references
    assert refs is not None
    assert refs.references == {"top_n": "TOP_N", "per_route_k": "K"}
    assert refs.variable_values == {"top_n": 2}  # parsed to the integer parameter type
    # Query-only references do not touch the index fingerprint.
    assert compiled.fingerprint == compile_system(scenario_config(), catalog).fingerprint

    by_variable = resolve_retrieval(refs, compiled.index, {"K": 4})
    assert (by_variable.top_n, by_variable.per_route_k) == (2, 4)
    by_request = resolve_retrieval(refs, compiled.index, {"K": 4, "TOP_N": 5})
    assert by_request.top_n == 5

    with pytest.raises(RequestInvalid) as raised:
        resolve_retrieval(refs, compiled.index, {"K": 4, "TOP_N": 0})
    assert raised.value.path == "/parameters/TOP_N" and "top_n" in raised.value.message
    with pytest.raises(RequestInvalid) as raised:
        resolve_retrieval(refs, compiled.index, {})
    assert raised.value.path == "/parameters/K"


@pytest.mark.parametrize(
    ("variables", "retrieval", "location"),
    [
        ({}, {"top_n": "{{MISSING}}"}, "top_n"),
        ({"TOP_N": "2"}, {"top_n": "top-{{TOP_N}}"}, "top_n"),
        ({"TOP_N": "two"}, {"top_n": "{{TOP_N}}"}, "top_n"),
        ({"TOP_N": "0"}, {"top_n": "{{TOP_N}}"}, "top_n"),
        ({"FIELDS": '["missing"]'}, {"vector_fields": "{{FIELDS}}"}, "vector_fields/0"),
        ({}, {"top_n": "{{INFERENCE_API_PASSWORD}}"}, "top_n"),
    ],
)
def test_builtin_retrieval_reference_errors_are_located(
    variables: dict[str, str], retrieval: dict[str, object], location: str
) -> None:
    catalog = build_catalog("dev-runtime", fixture_resources())
    config = reference_config(variables, **retrieval)
    if "TOP_N" in variables:  # let the Variable be used: no request parameter of the same name
        config["pipelines"]["inference"]["inference_input"]["parameters"]["request_parameters"] = []
    with pytest.raises(ConfigInvalid) as raised:
        compile_system(config, catalog)
    assert raised.value.path == f"/config/pipelines/inference/retrieval/parameters/{location}"


def remote_parsing_config() -> dict:
    config = scenario_config()
    import_fields = config["pipelines"]["ingestion"]["import"]["parameters"]["structdata"]
    config["pipelines"]["ingestion"]["parsing"] = {
        "component_id": "remote_api",
        "component_version": "1.0.0",
        "contract_version": "1",
        "through": "parsing",
        "connection": {
            "url": "{{REMOTE_PARSING_URL}}",
            "timeout_seconds": 30,
            "headers": {"X-Tenant": "{{REMOTE_PARSING_HEADER_X_TENANT}}"},
        },
        "auth": {"bearer_token": "{{REMOTE_PARSING_TOKEN}}"},
        "revision": "2026.11.1",
        "parameters": {"language": "zh-TW", "trace_label": "{{trace_label}}"},
        "runtime_only_parameters": ["trace_label"],
        "output": {"structdata": copy.deepcopy(import_fields)},
    }
    config["pipelines"]["ingestion"]["import"]["parameters"]["request_parameters"] = [
        {"name": "trace_label", "type": "string", "required": False}
    ]
    config["secret"]["REMOTE_PARSING_TOKEN"] = "token-dev"
    config["variable"] = {
        "REMOTE_PARSING_URL": "https://parser.dev.example/v1/normalize",
        "REMOTE_PARSING_HEADER_X_TENANT": "tenant-dev",
        "trace_label": "dev",
    }
    return config


def test_remote_connection_rules() -> None:
    catalog = build_catalog("dev-runtime", fixture_resources())
    compiled = compile_system(remote_parsing_config(), catalog)
    segment = compiled.ingestion.stages[0]
    assert segment.call.url == "https://parser.dev.example/v1/normalize"  # type: ignore[union-attr]
    assert segment.call.headers == {"X-Tenant": "tenant-dev"}  # type: ignore[union-attr]
    remote_stage = compiled.index.projection["ingestion"][1]
    assert remote_stage["implementation_revision"] == "2026.11.1"
    assert remote_stage["parameters"] == {"language": "zh-TW"}

    moved = remote_parsing_config()
    moved["variable"]["REMOTE_PARSING_URL"] = "http://parser.internal:8080/v2"
    assert compile_system(moved, catalog).fingerprint == compiled.fingerprint
    revised = remote_parsing_config()
    revised["pipelines"]["ingestion"]["parsing"]["revision"] = "2026.12.0"
    assert compile_system(revised, catalog).fingerprint != compiled.fingerprint

    def rejects(change: object, path_suffix: str) -> None:
        config = remote_parsing_config()
        change(config)  # type: ignore[operator]
        with pytest.raises(ConfigInvalid) as raised:
            compile_system(config, catalog)
        assert raised.value.path.endswith(path_suffix), raised.value

    node = ("pipelines", "ingestion", "parsing")
    rejects(
        lambda c: c["pipelines"]["ingestion"]["parsing"]["connection"].update(url="{{REMOTE_PARSING_TOKEN}}"),
        "/connection/url",
    )
    rejects(lambda c: c["variable"].update(REMOTE_PARSING_URL="ftp://x"), "/connection/url")
    rejects(
        lambda c: c["pipelines"]["ingestion"]["parsing"]["connection"]["headers"].update(
            {"X-Tenant": "{{REMOTE_PARSING_TOKEN}}"}
        ),
        "/connection/headers/X-Tenant",
    )
    rejects(
        lambda c: c["pipelines"]["ingestion"]["parsing"]["connection"]["headers"].update({"authorization": "x"}),
        "/connection/headers",
    )
    rejects(
        lambda c: c["pipelines"]["ingestion"]["parsing"]["parameters"].update(language="{{trace_label}}"),
        "/parameters/language",
    )
    del node


# ---------------------------------------------------------------- Elasticsearch mapping


def test_zh_ik_analysis_and_field_mappings() -> None:
    analysis = analysis_settings("zh_ik")
    assert analysis["char_filter"]["rag_t2s"] == {"type": "stconvert", "convert_type": "t2s"}
    assert analysis["analyzer"]["rag_zh_index"]["tokenizer"] == "ik_max_word"
    assert analysis["analyzer"]["rag_zh_search"]["tokenizer"] == "ik_smart"
    text = field_mapping(FieldSpec("string", True, searchable=True, filterable=True), "zh_ik")
    assert text == {
        "type": "text",
        "analyzer": "rag_zh_index",
        "search_analyzer": "rag_zh_search",
        "fields": {"keyword": {"type": "keyword"}},
    }
    assert field_mapping(FieldSpec("integer", True), "zh_ik") == {"type": "long", "index": False}
    resources = fixture_resources()
    mappings = index_mappings({"text": FieldSpec("string", True, searchable=True)}, {}, resources.profiles, "zh_ik")
    assert mappings["dynamic"] == "strict" and mappings["properties"]["metadata"]["enabled"] is False


def test_filters_translate_to_es_query_dsl() -> None:
    fields = {
        "title": FieldSpec("string", True, searchable=True, filterable=True),
        "price": FieldSpec("number", False, filterable=True),
    }
    clauses = filter_clauses(
        [
            {"field": "structdata.title", "operator": "eq", "value": "設備"},
            {
                "any": [
                    {"field": "structdata.price", "operator": "gte", "value": 300},
                    {"field": "structdata.price", "operator": "in", "value": [1, 2]},
                ]
            },
        ],
        fields,
    )
    assert clauses[0] == {"term": {"structdata.title.keyword": "設備"}}
    assert clauses[1]["bool"]["minimum_should_match"] == 1
    assert clauses[1]["bool"]["should"][0] == {"range": {"structdata.price": {"gte": 300}}}
