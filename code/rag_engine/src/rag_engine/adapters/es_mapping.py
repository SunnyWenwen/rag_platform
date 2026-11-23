"""Elasticsearch mapping, analysis settings and query DSL derived from the compiled index plan.

The mapping and analysis settings are part of the index fingerprint projection, so keep this
module deterministic and change it only with a fingerprint-aware release.

Target cluster: Elasticsearch 8.19 with analysis-ik, analysis-stconvert and analysis-smartcn.
"""

from __future__ import annotations

from typing import Any

from rag_engine.core.resources import EmbeddingProfile
from rag_engine.core.types import Fields, FieldSpec, VectorSpec

ZH_INDEX_ANALYZER = "rag_zh_index"
ZH_SEARCH_ANALYZER = "rag_zh_search"

# Traditional Chinese is converted to Simplified before IK tokenization because the IK
# dictionaries are Simplified. Only analysis changes; _source keeps the original text.
_ZH_IK_ANALYSIS: dict[str, Any] = {
    "char_filter": {"rag_t2s": {"type": "stconvert", "convert_type": "t2s"}},
    "analyzer": {
        ZH_INDEX_ANALYZER: {
            "type": "custom",
            "char_filter": ["rag_t2s"],
            "tokenizer": "ik_max_word",
            "filter": ["lowercase"],
        },
        ZH_SEARCH_ANALYZER: {
            "type": "custom",
            "char_filter": ["rag_t2s"],
            "tokenizer": "ik_smart",
            "filter": ["lowercase"],
        },
    },
}

_SCALAR_TYPES = {
    "integer": {"type": "long"},
    "number": {"type": "double"},
    "boolean": {"type": "boolean"},
    "date": {"type": "date", "format": "strict_date"},
    "datetime": {"type": "date", "format": "strict_date_time_no_millis"},
}


def analysis_settings(text_analysis: str) -> dict[str, Any]:
    if text_analysis == "zh_ik":
        return _ZH_IK_ANALYSIS
    if text_analysis == "standard":
        return {}
    raise ValueError(f"unknown text analysis {text_analysis!r}")


def _text_mapping(text_analysis: str) -> dict[str, Any]:
    if text_analysis == "zh_ik":
        return {"type": "text", "analyzer": ZH_INDEX_ANALYZER, "search_analyzer": ZH_SEARCH_ANALYZER}
    return {"type": "text", "analyzer": "standard"}


def field_mapping(spec: FieldSpec, text_analysis: str) -> dict[str, Any]:
    if spec.type == "string" and spec.searchable:
        mapping = _text_mapping(text_analysis)
        if spec.filterable:
            mapping["fields"] = {"keyword": {"type": "keyword"}}
        return mapping
    mapping = {"type": "keyword"} if spec.type in ("string", "string_array") else dict(_SCALAR_TYPES[spec.type])
    if not spec.filterable:
        mapping["index"] = False
    return mapping


def filter_path(name: str, spec: FieldSpec) -> str:
    """Elasticsearch field used for exact filters on ``structdata.<name>``."""
    if spec.type == "string" and spec.searchable and spec.filterable:
        return f"structdata.{name}.keyword"
    return f"structdata.{name}"


def index_mappings(
    fields: Fields,
    vectors: dict[str, VectorSpec],
    profiles: dict[str, EmbeddingProfile],
    text_analysis: str,
) -> dict[str, Any]:
    """Mappings without ``_meta``, in the shape used by the fingerprint projection."""
    vector_properties: dict[str, Any] = {}
    for name, spec in vectors.items():
        values: dict[str, Any] = {
            "type": "dense_vector",
            "dims": spec.dimensions,
            "index": True,
            "similarity": "cosine",
        }
        profile = profiles.get(spec.embedding_profile_id)
        if profile is not None and profile.index_options:
            values["index_options"] = dict(profile.index_options)
        vector_properties[name] = {
            "type": "object",
            "properties": {
                "values": values,
                "embedding_profile_id": {"type": "keyword", "index": False},
                "source_field": {"type": "keyword", "index": False},
            },
        }
    return {
        "dynamic": "strict",
        "dynamic_templates": [],
        "runtime": {},
        "_source": {"enabled": True},
        "properties": {
            "document_id": {"type": "keyword"},
            "data_id": {"type": "keyword"},
            "source_revision": {"type": "keyword"},
            "write_id": {"type": "keyword"},
            "structdata": {"properties": {name: field_mapping(spec, text_analysis) for name, spec in fields.items()}},
            # Document.metadata is stored and returned whole; its keys are never indexed.
            "metadata": {"type": "object", "enabled": False},
            "vectors": {"properties": vector_properties},
        },
    }


def _condition(condition: dict[str, Any], fields: Fields) -> dict[str, Any]:
    name = condition["field"].removeprefix("structdata.")
    path = filter_path(name, fields[name])
    operator, value = condition["operator"], condition["value"]
    if operator == "eq":
        return {"term": {path: value}}
    if operator == "in":
        return {"terms": {path: value}}
    return {"range": {path: {operator: value}}}


def filter_clauses(filters: list[dict[str, Any]], fields: Fields) -> list[dict[str, Any]]:
    clauses = []
    for clause in filters:
        if "any" in clause:
            clauses.append(
                {
                    "bool": {
                        "should": [_condition(item, fields) for item in clause["any"]],
                        "minimum_should_match": 1,
                    }
                }
            )
        else:
            clauses.append(_condition(clause, fields))
    return clauses


def fulltext_query(field: str, text: str, filters: list[dict[str, Any]], fields: Fields) -> dict[str, Any]:
    return {
        "bool": {
            "must": [{"match": {f"structdata.{field}": {"query": text}}}],
            "filter": filter_clauses(filters, fields),
        }
    }


def knn_clause(
    vector_name: str, vector: list[float], k: int, filters: list[dict[str, Any]], fields: Fields
) -> dict[str, Any]:
    clause: dict[str, Any] = {
        "field": f"vectors.{vector_name}.values",
        "query_vector": vector,
        "k": k,
        "num_candidates": min(max(k * 10, 100), 10_000),
    }
    clauses = filter_clauses(filters, fields)
    if clauses:
        clause["filter"] = {"bool": {"filter": clauses}}
    return clause
