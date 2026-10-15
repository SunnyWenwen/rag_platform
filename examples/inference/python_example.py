"""Inference Schema 與資料操作範例，使用 Python 3.10+ 標準函式庫。

執行：python examples/inference/python_example.py
TypedDict 提供型別提示，不會自動執行 JSON Schema 或引用／分數驗證。
Rerank 的分數讀自示例 JSON，沒有呼叫真實模型。
"""

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Literal, TypedDict, cast


class Chunk(TypedDict):
    chunk_id: str
    document_id: str
    source_revision: str
    fields: dict[str, Any]
    vectors: dict[str, list[float]]
    metadata: dict[str, Any]


class SourceRef(TypedDict):
    result_set_id: str
    chunk_id: str


class RetrievalSource(TypedDict):
    route_id: str
    index_ref: str
    field_path: str


class Operation(TypedDict):
    method: str
    parameters: dict[str, Any]
    model_ref: str | None
    scoring_query_id: str | None


class ResultItem(TypedDict):
    chunk: Chunk
    score: float
    rank: int
    source_refs: list[SourceRef]


class ResultSet(TypedDict):
    result_set_id: str
    stage: Literal["retrieval", "filter", "sort", "fusion", "rerank"]
    input_result_set_ids: list[str]
    source: RetrievalSource | None
    operation: Operation
    score_kind: str
    score_order: Literal["higher_is_better", "lower_is_better"]
    items: list[ResultItem]


class QueryContext(TypedDict):
    query_id: str
    query: str
    ori_query_id: str
    ori_query: str
    source_query_ids: list[str]
    result_sets: list[ResultSet]
    active_result_set_ids: list[str]


class InferenceState(TypedDict):
    contract_version: Literal["inference-0.1-draft"]
    query_contexts: list[QueryContext]
    active_query_ids: list[str]


def load_example(filename: str) -> InferenceState:
    """讀取同目錄內已驗證的 JSON；cast 不會進行執行期驗證。"""
    path = Path(__file__).parent / filename
    return cast(InferenceState, json.loads(path.read_text(encoding="utf-8")))


def active_results(state: InferenceState) -> list[ResultSet]:
    """依 active IDs 的順序取出下一步使用的結果。"""
    queries = {q["query_id"]: q for q in state["query_contexts"]}
    selected = []
    for query_id in state["active_query_ids"]:
        query = queries[query_id]
        results = {r["result_set_id"]: r for r in query["result_sets"]}
        selected.extend(results[rid] for rid in query["active_result_set_ids"])
    return selected


def filter_example() -> InferenceState:
    """從三路 Retrieval 的 r1 篩選，保留原結果並新增第四份清單。"""
    state = deepcopy(load_example("01_retrieval.json"))
    query = state["query_contexts"][0]
    source = next(r for r in query["result_sets"] if r["result_set_id"] == "r1")
    kept = [item for item in source["items"] if item["score"] >= 10]

    result: ResultSet = {
        "result_set_id": "r4-filter",
        "stage": "filter",
        "input_result_set_ids": ["r1"],
        "source": None,
        "operation": {
            "method": "score_threshold",
            "parameters": {"min_score": 10},
            "model_ref": None,
            "scoring_query_id": None,
        },
        "score_kind": source["score_kind"],
        "score_order": source["score_order"],
        "items": [
            {
                "chunk": deepcopy(item["chunk"]),
                "score": item["score"],
                "rank": rank,
                "source_refs": [
                    {"result_set_id": "r1", "chunk_id": item["chunk"]["chunk_id"]}
                ],
            }
            for rank, item in enumerate(kept, start=1)
        ],
    }
    query["result_sets"].append(result)
    query["active_result_set_ids"] = ["r4-filter"]
    return state


def print_results(state: InferenceState) -> None:
    for result in active_results(state):
        items = [
            (item["chunk"]["chunk_id"], item["score"], item["rank"])
            for item in result["items"]
        ]
        print(result["result_set_id"], items)


def main() -> None:
    print("例一：三路 Retrieval；每組 tuple 為 (chunk_id, score, rank)")
    print_results(load_example("01_retrieval.json"))

    print("\n例二：篩選後共四份結果，下游只使用 r4-filter")
    filtered = filter_example()
    assert filtered == load_example("02_filter.json")
    print("result_sets 數量：", len(filtered["query_contexts"][0]["result_sets"]))
    print_results(filtered)

    print("\n例三：Rerank 的示例分數；原始 r1 仍保留")
    print_results(load_example("03_rerank.json"))

    print("\n例四：跨 Query RRF；q0／q1／q2 保留，下一步只讀 q-merged")
    merged = load_example("04_cross_query_fusion.json")
    print("active_query_ids：", merged["active_query_ids"])
    print_results(merged)


if __name__ == "__main__":
    main()
