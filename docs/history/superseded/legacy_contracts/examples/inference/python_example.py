"""Offline reference operations for QueryContext[]; no Engine/model/API calls.

items order is rank. Each operation replaces the current effective results.
History belongs in logs. Same-query fusion uses chunk_id; document grouping
selects a representative afterwards, never adds scores of sibling chunks.
"""
from copy import deepcopy
import json
from pathlib import Path
from typing import Any, TypedDict, NotRequired


class FilterCondition(TypedDict):
    field: str
    operator: str
    value: str | list[str]


class ResultItem(TypedDict):
    chunk: dict[str, Any]  # canonical Chunk schema
    score: NotRequired[float | None]


class ResultSet(TypedDict):
    key: str
    items: list[ResultItem]


class QueryContext(TypedDict):
    ori_query: str
    query: str
    filters: list[FilterCondition]
    result_sets: list[ResultSet]
    metadata: dict[str, Any]


def load_example(filename: str) -> list[QueryContext]:
    return json.loads(Path(__file__).with_name(filename).read_text())


def top_n(result: ResultSet, n: int) -> ResultSet:
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        raise ValueError('Top N must be a positive integer')
    # Input adapter/scoring/fusion already established the effective order.
    return {'key': result['key'], 'items': deepcopy(result['items'][:n])}


def rrf(results: list[ResultSet], key: str = 'merged', k: int = 60) -> ResultSet:
    if not isinstance(k, int) or isinstance(k, bool) or k < 1:
        raise ValueError('RRF k must be a positive integer')
    scores: dict[str, float] = {}; chunks = {}
    for result in results:
        seen = set()
        for rank, item in enumerate(result['items'], start=1):
            cid = item['chunk']['chunk_id']
            if cid in seen:
                raise ValueError('duplicate chunk_id within one input list')
            seen.add(cid)
            if cid in chunks and chunks[cid] != item['chunk']:
                raise ValueError('same chunk_id has inconsistent content')
            chunks[cid] = deepcopy(item['chunk'])
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
    # Stable deterministic tie break without storing a redundant rank field.
    ordered = sorted(scores, key=lambda cid: (-scores[cid], cid))
    return {'key': key, 'items': [{'chunk': chunks[cid], 'score': scores[cid]} for cid in ordered]}


def same_query_merge(context: QueryContext, n: int) -> QueryContext:
    output = deepcopy(context)
    output['result_sets'] = [top_n(rrf(context['result_sets']), n)]
    return output


def cross_query_merge(contexts: list[QueryContext], n: int) -> list[QueryContext]:
    if not contexts:
        return []
    first = contexts[0]
    # Current prototype keeps metadata only when identical; no silent conflict.
    for other in contexts[1:]:
        if any(other[name] != first[name] for name in ('ori_query', 'filters', 'metadata')):
            raise ValueError('cross-query merge requires same request, filters and metadata')
    groups: dict[str, list[ResultSet]] = {}
    for context in contexts:
        for result in context['result_sets']:
            groups.setdefault(result['key'], []).append(result)
    output = deepcopy(first)
    output['query'] = output['ori_query']
    output['result_sets'] = [top_n(rrf(group, key), n) for key, group in groups.items()]
    return [output]


def rerank(contexts: list[QueryContext], scores: dict[str, float], n: int) -> list[QueryContext]:
    """Scores supplied by caller for demonstration, not a model implementation."""
    from math import isfinite
    output = deepcopy(contexts)
    for context in output:
        for result in context['result_sets']:
            for item in result['items']:
                score = scores[item['chunk']['chunk_id']]
                if not isfinite(score):
                    raise ValueError('non-finite model score')
                item['score'] = score  # overwrite prior score, no history
            result['items'].sort(key=lambda item: (-item['score'], item['chunk']['chunk_id']))
            result['items'] = top_n(result, n)['items']
    return output


def print_results(contexts: list[QueryContext]) -> None:
    for context in contexts:
        for result in context['result_sets']:
            for rank, item in enumerate(result['items'], start=1):
                print(context['query'], result['key'], rank, item.get('score'), item['chunk']['chunk_id'])


if __name__ == '__main__':
    original = load_example('01_retrieval.json')
    print_results([same_query_merge(context, 3) for context in original])
