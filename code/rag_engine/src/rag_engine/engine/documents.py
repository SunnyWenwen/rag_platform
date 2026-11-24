"""Validate Documents and QueryContexts against the System's effective schemas."""

from __future__ import annotations

import math
from typing import Any

from rag_engine.contracts import errors, schema_ref
from rag_engine.core.errors import EngineError, RequestInvalid, UpstreamError
from rag_engine.core.filters import value_matches_type
from rag_engine.core.types import Document, Fields, Vectors


def check_structdata(
    structdata: dict[str, Any], fields: Fields, path: str, *, error: type[EngineError], module: str | None = None
) -> None:
    for name, value in structdata.items():
        spec = fields.get(name)
        if spec is None:
            raise error(f"undeclared field {name}", path=f"{path}/{name}", module=module)
        if value is None:
            raise error(f"field {name} must not be null", path=f"{path}/{name}", module=module)
        if spec.type == "string_array":
            ok = isinstance(value, list) and all(isinstance(item, str) for item in value)
        else:
            ok = value_matches_type(spec.type, value)
        if not ok:
            raise error(f"field {name} must be {spec.type}", path=f"{path}/{name}", module=module)
    for name, spec in fields.items():
        if spec.required and name not in structdata:
            raise error(f"field {name} is required", path=f"{path}/{name}", module=module)


def check_ingestion_document(document: Document, fields: Fields, source: str, path: str) -> None:
    """Per-document Import validation, after the shared IngestionRequest shape check."""
    if source == "content" and "content" not in document:
        raise RequestInvalid("content is required", path=path + "/content")
    if source == "structdata" and "content" in document:
        raise RequestInvalid("this System imports structdata only", path=path + "/content")
    structdata = document.get("structdata", {})
    if source == "structdata" or structdata:
        check_structdata(structdata, fields, path + "/structdata", error=RequestInvalid)


def check_remote_documents(
    documents: list[Any], document_id: str, fields: Fields, vectors: Vectors, module: str, *, chunked: bool
) -> list[Document]:
    """Validate a Remote Ingestion segment's output (Document[])."""
    seen: set[str] = set()
    for index, document in enumerate(documents):
        path = f"/output/{index}"
        for problem in errors(schema_ref("document.schema.json"), document):
            raise UpstreamError(f"invalid Document: {problem.message}", module=module, path=path + problem.path)
        if document["document_id"] != document_id:
            raise UpstreamError("document_id changed", module=module, path=path + "/document_id")
        check_structdata(
            document.get("structdata", {}), fields, path + "/structdata", error=UpstreamError, module=module
        )
        if chunked:
            data_id = document.get("data_id")
            if not isinstance(data_id, str) or not data_id or data_id in seen:
                raise UpstreamError("data_id must be present and unique", module=module, path=path + "/data_id")
            seen.add(data_id)
        for name, spec in vectors.items():
            vector = document.get("vectors", {}).get(name)
            values = vector.get("values") if isinstance(vector, dict) else None
            if (
                not isinstance(values, list)
                or len(values) != spec.dimensions
                or not all(isinstance(v, int | float) and math.isfinite(v) for v in values)
            ):
                raise UpstreamError(
                    f"vector {name} is missing or has the wrong dimensions",
                    module=module,
                    path=f"{path}/vectors/{name}",
                )
    return documents


def check_query_contexts(contexts: Any, fields: Fields, module: str) -> list[dict[str, Any]]:
    """Validate a Remote Inference segment's output (QueryContext[])."""
    for problem in errors(schema_ref("query_context.schema.json"), contexts):
        raise UpstreamError(f"invalid QueryContext: {problem.message}", module=module, path="/output" + problem.path)
    for c_index, context in enumerate(contexts):
        for r_index, result_set in enumerate(context["result_sets"]):
            for i_index, item in enumerate(result_set["items"]):
                path = f"/output/{c_index}/result_sets/{r_index}/items/{i_index}/data"
                data = item["data"]
                check_structdata(data["structdata"], fields, path + "/structdata", error=UpstreamError, module=module)
    return list(contexts)
