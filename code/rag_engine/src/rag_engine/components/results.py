"""Result processing: fusion, group_by, Top N, cross-Query merge and the final Context.

Follows 03_engine_and_components.md#result-processing and #src-04-54-最終檢索輸出.
Items are ``{"data": Document, "score": float?}``; list order is the rank.
"""

from __future__ import annotations

from typing import Any

from rag_engine.core.errors import EngineError

Item = dict[str, Any]

DEFAULT_RRF_K = 60


def fuse(route_lists: list[list[Item]], method: str | None, rrf_k: int = DEFAULT_RRF_K) -> list[Item]:
    """Combine the per-route lists of one Query into one list keyed by ``data_id``."""
    if len(route_lists) == 1:
        return list(route_lists[0])
    if method is None:
        raise EngineError(
            "fusion is required for multiple search routes", code="CONFIG_VALIDATION_FAILED", module="retrieval"
        )
    best: dict[str, Item] = {}
    totals: dict[str, float] = {}
    first_seen: dict[str, tuple[int, int]] = {}
    for route_index, items in enumerate(route_lists):
        for rank, item in enumerate(items):
            data_id = item["data"]["data_id"]
            if method == "rrf":
                contribution = 1.0 / (rrf_k + rank + 1)
            else:
                score = item.get("score")
                if score is None:
                    raise EngineError(
                        "sum_score needs a score on every candidate", code="UPSTREAM_ERROR", module="retrieval"
                    )
                contribution = float(score)
            totals[data_id] = totals.get(data_id, 0.0) + contribution
            best.setdefault(data_id, item)
            first_seen.setdefault(data_id, (route_index, rank))
    ordered = sorted(totals, key=lambda data_id: (-totals[data_id], first_seen[data_id]))
    return [{"data": best[data_id]["data"], "score": totals[data_id]} for data_id in ordered]


def _group_key(data: dict[str, Any], fields: list[str]) -> tuple[Any, ...] | None:
    values = []
    for name in fields:
        if name == "document_id":
            value = data.get("document_id")
        else:
            value = data.get("structdata", {}).get(name.removeprefix("structdata."))
        if value is None:
            return None
        values.append(value)
    return tuple(values)


def group_by(items: list[Item], fields: list[str] | None) -> list[Item]:
    """Keep the highest-scored candidate per key; ties keep the earlier rank."""
    if not fields:
        return items
    winners: dict[tuple[Any, ...], int] = {}
    keep: list[bool] = [True] * len(items)
    for position, item in enumerate(items):
        key = _group_key(item["data"], fields)
        if key is None:
            continue  # Candidates missing a group field stay on their own.
        if key not in winners:
            winners[key] = position
            continue
        current = winners[key]
        current_score, score = items[current].get("score"), item.get("score")
        if score is not None and (current_score is None or score > current_score):
            keep[current] = False
            winners[key] = position
        else:
            keep[position] = False
    return [item for position, item in enumerate(items) if keep[position]]


def unique_data_ids(items: list[Item]) -> list[Item]:
    """Keep the first (best) candidate of each data_id. While a re-ingested document has its old
    and new batch both visible (06 D-60), one route may return the same data_id twice."""
    seen: set[str] = set()
    unique = []
    for item in items:
        data_id = item["data"]["data_id"]
        if data_id not in seen:
            seen.add(data_id)
            unique.append(item)
    return unique


def top_n(items: list[Item], limit: int | None) -> list[Item]:
    return items if limit is None else items[:limit]


def cross_query_merge(contexts: list[dict[str, Any]], group: list[str] | None, limit: int | None) -> list[Item]:
    """Merge each Context's single list by ``data_id`` keeping the best score."""
    best: dict[str, tuple[float, int, int, Item]] = {}
    for query_index, context in enumerate(contexts):
        result_sets = context["result_sets"]
        if len(result_sets) != 1:
            raise EngineError(
                "cross-query merge needs exactly one ResultSet per Context",
                code="UPSTREAM_ERROR",
                module="query_transformation",
            )
        for rank, item in enumerate(result_sets[0]["items"]):
            score = item.get("score")
            if score is None:
                raise EngineError(
                    "cross-query merge needs comparable scores", code="UPSTREAM_ERROR", module="query_transformation"
                )
            data_id = item["data"]["data_id"]
            candidate = (float(score), query_index, rank, item)
            current = best.get(data_id)
            if current is None or candidate[0] > current[0]:
                best[data_id] = candidate
    ordered = sorted(best.values(), key=lambda entry: (-entry[0], entry[1], entry[2]))
    return top_n(group_by([entry[3] for entry in ordered], group), limit)


def finalize(contexts: list[dict[str, Any]], initial: dict[str, Any], merged: list[Item] | None) -> dict[str, Any]:
    """Collapse the pipeline's Contexts into the single final Context of the HTTP response."""
    if merged is None:
        if len(contexts) != 1 or len(contexts[0]["result_sets"]) != 1:
            raise EngineError(
                "the pipeline must end with one Context and one ResultSet", code="UPSTREAM_ERROR", module="rerank"
            )
        merged = contexts[0]["result_sets"][0]["items"]
    return {
        "ori_query": initial["ori_query"],
        "query": initial["ori_query"],
        "filters": initial["filters"],
        "result_sets": [{"key": "final", "items": merged}],
        "metadata": initial["metadata"],
    }
