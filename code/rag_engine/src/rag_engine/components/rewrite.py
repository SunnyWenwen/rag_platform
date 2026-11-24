"""Rewrite Query Transformation (03#rewrite-rules).

The company LLM rewrites the question into ``count`` queries returned as {"queries": [...]}.
A format error is retried once; if the answer is still unusable, or the model refused or was
cut off, the query falls back to the original question. Service failures are raised.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import httpx

from rag_engine.adapters.llm import chat_json
from rag_engine.core.errors import RequestInvalid, UpstreamError
from rag_engine.core.resources import ModelResource

MODULE = "query_transformation"
MAX_CALLS = 2  # one retry (03#rewrite-rules)
_REFERENCE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")
_log = logging.getLogger(__name__)


def system_message(count: int) -> str:
    return (
        "你負責把使用者的問題改寫成檢索用的查詢。依使用者的指示產生剛好 "
        f'{count} 個查詢，只回傳 JSON 物件 {{"queries": [...]}}：'
        "陣列的每一項都是非空字串，彼此不重複。"
    )


def output_schema(count: int) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {"queries": {"type": "array", "items": {"type": "string"}, "minItems": count, "maxItems": count}},
        "required": ["queries"],
        "additionalProperties": False,
    }


def render_prompt(
    template: str, query: str, count: int, request_values: dict[str, Any], variables: dict[str, str]
) -> str:
    """Fill ``{{query}}``, ``{{count}}`` and other ``{{KEY}}`` (request value first, then Variable)."""

    def value(match: re.Match[str]) -> str:
        key = match[1]
        if key == "query":
            return query
        if key == "count":
            return str(count)
        if key in request_values:
            found = request_values[key]
        elif key in variables:
            found = variables[key]
        else:
            raise RequestInvalid(
                f"no value for {key}, used by the rewrite prompt", path=f"/parameters/{key}", module=MODULE
            )
        return found if isinstance(found, str) else json.dumps(found, ensure_ascii=False)

    return _REFERENCE.sub(value, template)


def parse_rewrites(content: str | None, count: int) -> list[str] | None:
    """The trimmed queries, or None when the answer breaks the format rules."""
    try:
        data = json.loads(content or "")
    except ValueError:
        return None
    if not isinstance(data, dict) or set(data) != {"queries"}:
        return None
    queries = data["queries"]
    if not isinstance(queries, list) or len(queries) != count:
        return None
    if not all(isinstance(query, str) for query in queries):
        return None
    cleaned = [query.strip() for query in queries]
    if any(not query for query in cleaned) or len(set(cleaned)) != len(cleaned):
        return None
    return cleaned


def final_queries(original: str, rewrites: list[str] | None, include_original: bool) -> list[str]:
    """Original first when included (or as the fallback), then the rewrites; exact duplicates removed."""
    queries = [original] if include_original or rewrites is None else []
    for query in rewrites or []:
        if query not in queries:
            queries.append(query)
    return queries


async def rewrite_queries(
    client: httpx.AsyncClient,
    model: ModelResource,
    prompt: str,
    original: str,
    count: int,
    include_original: bool,
    deadline: float,
) -> list[str]:
    """Ask the LLM for ``count`` rewrites and return the queries to search."""
    messages = [{"role": "system", "content": system_message(count)}, {"role": "user", "content": prompt}]
    schema = output_schema(count)
    rewrites: list[str] | None = None
    reason = "invalid format"
    for attempt in range(1, MAX_CALLS + 1):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise UpstreamError("the query deadline passed during the rewrite", code="DEADLINE_EXCEEDED", module=MODULE)
        try:
            reply = await chat_json(
                client, model, messages, "rewrite_queries", schema, min(model.timeout_seconds, remaining), MODULE
            )
        except UpstreamError as error:
            if error.retryable and attempt < MAX_CALLS:
                continue
            raise
        if reply.refusal is not None or reply.finish_reason == "length":
            reason = "refused" if reply.refusal is not None else "truncated"
            break  # not retried
        rewrites = parse_rewrites(reply.content, count)
        if rewrites is not None:
            break
    if rewrites is None:
        _log.warning("rewrite fell back to the original query", extra={"code": "REWRITE_FALLBACK", "status": reason})
    return final_queries(original, rewrites, include_original)
