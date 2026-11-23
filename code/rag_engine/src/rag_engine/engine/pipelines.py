"""LangGraph pipelines built once per loaded System Config.

Each graph is compiled when the Runtime loads a Config Revision, so every request runs on the
fixed snapshot it started with. Per-request values (request parameters, request ID, deadline,
progress callback) travel in ``config["configurable"]``. No checkpointer is used: Runtime
work state lives in the accepting Pod's memory, not in LangGraph.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypedDict

import httpx
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from rag_engine.adapters.embedding import Embedder
from rag_engine.adapters.index_store import IndexStore, SearchRoute
from rag_engine.adapters.tokenizer import load_tokenizer
from rag_engine.components import results
from rag_engine.components.chunking import chunk_documents
from rag_engine.components.embedding import embed_documents
from rag_engine.components.remote import call_remote
from rag_engine.core.errors import RequestInvalid, UpstreamError
from rag_engine.core.filters import validate_filters
from rag_engine.core.types import Document
from rag_engine.engine.compiler import (
    BuiltinRetrieval,
    ChunkStage,
    CompiledSystem,
    EmbedStage,
    RemoteSegment,
)
from rag_engine.engine.documents import check_query_contexts, check_remote_documents
from rag_engine.engine.values import bind_request, resolve_parameters

ProgressCallback = Callable[[str], Awaitable[None] | None]


@dataclass(frozen=True)
class EngineDeps:
    embedder: Embedder
    http: httpx.AsyncClient


class IngestionState(TypedDict):
    documents: list[Document]


class InferenceState(TypedDict, total=False):
    initial: dict[str, Any]
    contexts: list[dict[str, Any]]
    query_variants: list[str]
    final: dict[str, Any]


def _configurable(config: RunnableConfig) -> dict[str, Any]:
    return config.get("configurable", {})


async def _progress(config: RunnableConfig, module: str) -> None:
    callback = _configurable(config).get("progress")
    if callback is not None:
        result = callback(module)
        if result is not None:
            await result


# ---------------------------------------------------------------------------- ingestion


def build_ingestion_graph(system: CompiledSystem, deps: EngineDeps) -> Any:
    """parse -> chunk -> embed, one node per effective stage. Indexing is done by the Runtime."""
    graph = StateGraph(IngestionState)
    previous = START
    for position, stage in enumerate(system.ingestion.stages):
        name = f"{position}_{_stage_name(stage)}"
        graph.add_node(name, _ingestion_node(stage, system, deps))
        graph.add_edge(previous, name)
        previous = name
    graph.add_edge(previous, END)
    return graph.compile()


def _stage_name(stage: object) -> str:
    if isinstance(stage, RemoteSegment):
        return f"remote_{stage.module}"
    if isinstance(stage, ChunkStage):
        return "chunking"
    if isinstance(stage, EmbedStage):
        return "embedding"
    return "parsing"


def _ingestion_node(stage: object, system: CompiledSystem, deps: EngineDeps) -> Any:
    if isinstance(stage, RemoteSegment):

        async def remote(state: IngestionState, config: RunnableConfig) -> dict[str, Any]:
            await _progress(config, stage.module)
            options = _configurable(config)
            documents = state["documents"]
            document_id = documents[0]["document_id"]
            parameters = resolve_parameters(
                stage.parameters, options.get("request_values", {}), system.values.variables
            )
            payload: Any = documents[0] if stage.module == "parsing" else documents
            output = await call_remote(
                deps.http,
                stage.call,
                payload,
                parameters,
                upstream_request_id=options.get("request_id"),
                deadline=options["deadline"],
            )
            chunked = "chunking" in stage.covered or stage.module == "embedding"
            checked = check_remote_documents(
                output,
                document_id,
                stage.output_fields or {},
                stage.output_vectors or {},
                stage.module,
                chunked=chunked,
            )
            return {"documents": checked}

        return remote
    if isinstance(stage, ChunkStage):

        async def chunk(state: IngestionState, config: RunnableConfig) -> dict[str, Any]:
            await _progress(config, "chunking")
            tokenizer = load_tokenizer(stage.tokenizer)
            return {"documents": chunk_documents(state["documents"], stage.settings, tokenizer)}

        return chunk
    if isinstance(stage, EmbedStage):

        async def embed(state: IngestionState, config: RunnableConfig) -> dict[str, Any]:
            await _progress(config, "embedding")
            tokenizer = load_tokenizer(stage.tokenizer) if stage.tokenizer else None
            documents = await embed_documents(
                state["documents"], stage.settings, stage.profile, deps.embedder, tokenizer
            )
            return {"documents": documents}

        return embed

    async def passthrough(state: IngestionState, config: RunnableConfig) -> dict[str, Any]:
        await _progress(config, "parsing")
        return {"documents": state["documents"]}

    return passthrough


# ---------------------------------------------------------------------------- inference


def build_inference_graph(
    system: CompiledSystem, deps: EngineDeps, store: IndexStore | None, index_name: str | None
) -> Any:
    plan = system.inference
    graph = StateGraph(InferenceState)
    graph.add_node("inference_input", _input_node(system))
    steps: list[tuple[str, Any]] = []
    if plan.transformation is not None:
        steps.append(
            (f"remote_{plan.transformation.module}", _remote_inference_node(plan.transformation, system, deps))
        )
    if isinstance(plan.retrieval, RemoteSegment):
        steps.append(("remote_retrieval", _remote_inference_node(plan.retrieval, system, deps)))
    elif isinstance(plan.retrieval, BuiltinRetrieval):
        assert store is not None and index_name is not None
        steps.append(("retrieval", _retrieval_node(plan.retrieval, system, deps, store, index_name)))
    if plan.rerank is not None:
        steps.append(("remote_rerank", _remote_inference_node(plan.rerank, system, deps)))
    graph.add_node("finalize", _finalize_node())
    graph.add_edge(START, "inference_input")
    previous = "inference_input"
    for name, node in steps:
        graph.add_node(name, node)
        graph.add_edge(previous, name)
        previous = name
    graph.add_edge(previous, "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()


def _input_node(system: CompiledSystem) -> Any:
    plan = system.inference

    async def inference_input(state: InferenceState, config: RunnableConfig) -> dict[str, Any]:
        request = _configurable(config)["request"]
        bound = bind_request(plan.request_parameters, request.get("parameters", {}))
        _configurable(config)["request_values"] = bound
        filters = request.get("filters", [])
        validate_filters(filters, plan.candidate_fields, "/filters", error=RequestInvalid)
        initial = {
            "ori_query": request["query"],
            "query": request["query"],
            "filters": [*plan.fixed_filters, *filters],
            "result_sets": [],
            "metadata": request.get("metadata", {}),
        }
        return {"initial": initial, "contexts": [initial], "query_variants": [request["query"]]}

    return inference_input


def _remote_inference_node(segment: RemoteSegment, system: CompiledSystem, deps: EngineDeps) -> Any:
    async def remote(state: InferenceState, config: RunnableConfig) -> dict[str, Any]:
        options = _configurable(config)
        parameters = resolve_parameters(segment.parameters, options.get("request_values", {}), system.values.variables)
        output = await call_remote(
            deps.http,
            segment.call,
            state["contexts"],
            parameters,
            upstream_request_id=options.get("request_id"),
            deadline=options["deadline"],
        )
        contexts = check_query_contexts(output, system.inference.candidate_fields, segment.module)
        update: dict[str, Any] = {"contexts": contexts}
        if segment.module == "query_transformation":
            update["query_variants"] = [context["query"] for context in contexts]
        if segment.through == "rerank" and (len(contexts) != 1 or len(contexts[0]["result_sets"]) != 1):
            raise UpstreamError(
                "a Remote segment ending the pipeline must return one Context and one ResultSet", module=segment.module
            )
        return update

    return remote


def _retrieval_node(
    plan: BuiltinRetrieval, system: CompiledSystem, deps: EngineDeps, store: IndexStore, index_name: str
) -> Any:
    fields = system.index.fields
    profiles = {name: system.index.vectors[name].embedding_profile_id for name in plan.vector_fields}

    async def retrieval(state: InferenceState, config: RunnableConfig) -> dict[str, Any]:
        resources_profiles = _configurable(config)["profiles"]
        contexts = []
        for context in state["contexts"]:
            route_lists: list[list[results.Item]] = []
            for field_name in plan.fulltext_fields:
                route = SearchRoute("fulltext", field_name, plan.per_route_k, context["filters"], text=context["query"])
                hits = await store.search(index_name, route, fields)
                route_lists.append([{"data": hit.document, "score": hit.score} for hit in hits])
            for vector_name in plan.vector_fields:
                profile = resources_profiles[profiles[vector_name]]
                query_vector = (await deps.embedder.embed([context["query"]], profile))[0]
                route = SearchRoute("vector", vector_name, plan.per_route_k, context["filters"], vector=query_vector)
                hits = await store.search(index_name, route, fields)
                route_lists.append([{"data": hit.document, "score": hit.score} for hit in hits])
            items = results.fuse(route_lists, plan.fusion, plan.rrf_k)
            items = results.top_n(results.group_by(items, list(plan.group_by)), plan.top_n)
            contexts.append({**context, "result_sets": [{"key": "retrieval", "items": items}]})
        return {"contexts": contexts}

    return retrieval


def _finalize_node() -> Any:
    async def finalize(state: InferenceState, config: RunnableConfig) -> dict[str, Any]:
        contexts = state["contexts"]
        merged = results.cross_query_merge(contexts, None, None) if len(contexts) > 1 else None
        return {"final": results.finalize(contexts, state["initial"], merged)}

    return finalize


def deadline_after(seconds: float) -> float:
    return time.monotonic() + seconds
