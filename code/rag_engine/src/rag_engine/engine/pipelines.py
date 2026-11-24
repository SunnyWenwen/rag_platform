"""LangGraph pipelines built once per loaded System Config.

Each graph is compiled when the Runtime loads a Config Revision, so every request runs on the
fixed snapshot it started with. Per-request values (request parameters, request ID, deadline,
progress callback) travel in ``config["configurable"]``. No checkpointer is used: Runtime
work state lives in the accepting Pod's memory, not in LangGraph.
"""

from __future__ import annotations

import time
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
from rag_engine.engine.compiler import resolve_retrieval
from rag_engine.engine.documents import check_query_contexts, check_remote_documents
from rag_engine.engine.plan import (
    BuiltinRetrieval,
    ChunkStage,
    CompiledSystem,
    EmbedStage,
    IngestionStage,
    RemoteSegment,
)
from rag_engine.engine.values import bind_request, resolve_parameters


@dataclass(frozen=True)
class EngineDeps:
    embedder: Embedder
    http: httpx.AsyncClient


class IngestionState(TypedDict):
    documents: list[Document]


class InferenceState(TypedDict, total=False):
    # Values a node computes for later nodes live in the state: LangGraph gives each node
    # its own copy of config["configurable"], so writes there are not seen downstream.
    request_values: dict[str, Any]  # validated request parameters with declared defaults
    retrieval: BuiltinRetrieval | None  # per-request settings when parameters use {{KEY}}
    initial: dict[str, Any]
    contexts: list[dict[str, Any]]
    query_variants: list[str]
    final: dict[str, Any]


def _configurable(config: RunnableConfig) -> dict[str, Any]:
    return config.get("configurable", {})


# ---------------------------------------------------------------------------- ingestion


def build_ingestion_graph(system: CompiledSystem, deps: EngineDeps) -> Any:
    """One node per effective stage, in order. Indexing is done by the Runtime, not the graph."""
    graph = StateGraph(IngestionState)
    previous = START
    for position, stage in enumerate(system.ingestion.stages):
        name = f"{position}_{_stage_module(stage)}"
        graph.add_node(name, _make_ingestion_node(stage, system, deps))
        graph.add_edge(previous, name)
        previous = name
    graph.add_edge(previous, END)
    return graph.compile()


def _stage_module(stage: IngestionStage) -> str:
    if isinstance(stage, RemoteSegment):
        return stage.module
    if isinstance(stage, ChunkStage):
        return "chunking"
    if isinstance(stage, EmbedStage):
        return "embedding"
    return "parsing"


def _make_ingestion_node(stage: IngestionStage, system: CompiledSystem, deps: EngineDeps) -> Any:
    async def node(state: IngestionState, config: RunnableConfig) -> dict[str, Any]:
        options = _configurable(config)
        documents = await run_ingestion_stage(stage, state["documents"], system, deps, options)
        return {"documents": documents}

    return node


async def run_ingestion_stage(
    stage: IngestionStage,
    documents: list[Document],
    system: CompiledSystem,
    deps: EngineDeps,
    options: dict[str, Any],
) -> list[Document]:
    """Run one Ingestion stage on the Documents of one source document."""
    progress = options.get("progress")
    if progress is not None:
        progress(_stage_module(stage))

    if isinstance(stage, ChunkStage):
        tokenizer = load_tokenizer(stage.tokenizer)
        return chunk_documents(documents, stage.settings, tokenizer)

    if isinstance(stage, EmbedStage):
        embed_tokenizer = load_tokenizer(stage.tokenizer) if stage.tokenizer else None
        return await embed_documents(documents, stage.settings, stage.profile, deps.embedder, embed_tokenizer)

    if isinstance(stage, RemoteSegment):
        parameters = resolve_parameters(stage.parameters, options.get("request_values", {}), system.values.variables)
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
        return check_remote_documents(
            output,
            documents[0]["document_id"],
            stage.output_fields or {},
            stage.output_vectors or {},
            stage.module,
            chunked=chunked,
        )

    return documents  # Passthrough parsing keeps structured Documents as they are.


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
        retrieval = None
        if plan.retrieval_references is not None:
            # Resolve "{{KEY}}" Retrieval parameters before any Remote call so a bad value fails fast.
            retrieval = resolve_retrieval(plan.retrieval_references, system.index, bound)
        filters = request.get("filters", [])
        validate_filters(filters, plan.candidate_fields, "/filters", error=RequestInvalid)
        initial = {
            "ori_query": request["query"],
            "query": request["query"],
            "filters": [*plan.fixed_filters, *filters],
            "result_sets": [],
            "metadata": request.get("metadata", {}),
        }
        return {
            "request_values": bound,
            "retrieval": retrieval,
            "initial": initial,
            "contexts": [initial],
            "query_variants": [request["query"]],
        }

    return inference_input


def _remote_inference_node(segment: RemoteSegment, system: CompiledSystem, deps: EngineDeps) -> Any:
    async def remote(state: InferenceState, config: RunnableConfig) -> dict[str, Any]:
        options = _configurable(config)
        parameters = resolve_parameters(segment.parameters, state["request_values"], system.values.variables)
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

    async def retrieval(state: InferenceState, config: RunnableConfig) -> dict[str, Any]:
        options = _configurable(config)
        resources_profiles = options["profiles"]
        settings = state.get("retrieval") or plan
        contexts = []
        for context in state["contexts"]:
            route_lists: list[list[results.Item]] = []
            for field_name in settings.fulltext_fields:
                route = SearchRoute(
                    "fulltext", field_name, settings.per_route_k, context["filters"], text=context["query"]
                )
                hits = await store.search(index_name, route, fields)
                route_lists.append([{"data": hit.document, "score": hit.score} for hit in hits])
            for vector_name in settings.vector_fields:
                profile = resources_profiles[system.index.vectors[vector_name].embedding_profile_id]
                query_vector = (await deps.embedder.embed([context["query"]], profile))[0]
                route = SearchRoute(
                    "vector", vector_name, settings.per_route_k, context["filters"], vector=query_vector
                )
                hits = await store.search(index_name, route, fields)
                route_lists.append([{"data": hit.document, "score": hit.score} for hit in hits])
            items = results.fuse(route_lists, settings.fusion, settings.rrf_k)
            items = results.top_n(results.group_by(items, list(settings.group_by)), settings.top_n)
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
