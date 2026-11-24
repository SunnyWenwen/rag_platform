"""Plan types produced by ``engine/compiler.py`` and executed by ``engine/pipelines.py``.

Plain frozen dataclasses with no logic, so every layer can read a compiled System
without importing the compiler.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rag_engine.components.chunking import ChunkSettings
from rag_engine.components.embedding import DenseSettings
from rag_engine.components.remote import RemoteCall
from rag_engine.core.resources import EmbeddingProfile, ModelResource, TokenizerProfile
from rag_engine.core.types import Fields, Vectors
from rag_engine.engine.values import RequestParameter, SystemValues


@dataclass(frozen=True)
class RemoteSegment:
    module: str
    through: str
    covered: tuple[str, ...]
    call: RemoteCall
    parameters: dict[str, Any]
    runtime_only: frozenset[str]
    revision: str | None
    output_fields: Fields | None = None
    output_vectors: Vectors | None = None


@dataclass(frozen=True)
class ChunkStage:
    settings: ChunkSettings
    tokenizer: TokenizerProfile


@dataclass(frozen=True)
class EmbedStage:
    settings: DenseSettings
    profile: EmbeddingProfile
    tokenizer: TokenizerProfile | None


IngestionStage = RemoteSegment | ChunkStage | EmbedStage | str  # "passthrough"


@dataclass(frozen=True)
class IngestionPlan:
    import_source: str
    import_fields: Fields
    request_parameters: dict[str, RequestParameter]
    stages: tuple[IngestionStage, ...]


@dataclass(frozen=True)
class IndexPlan:
    component_id: str
    component_version: str
    fields: Fields
    vectors: Vectors
    mappings: dict[str, Any]
    analysis: dict[str, Any]
    connection: dict[str, Any]
    projection: dict[str, Any]
    fingerprint: str


@dataclass(frozen=True)
class BuiltinRetrieval:
    vector_fields: tuple[str, ...]
    fulltext_fields: tuple[str, ...]
    per_route_k: int
    fusion: str | None
    rrf_k: int
    group_by: tuple[str, ...]
    top_n: int | None


@dataclass(frozen=True)
class ParameterReferences:
    """Built-in Inference parameters written as ``"{{KEY}}"``, resolved for each request.

    Rule (05#parameter-references): the request value first (declared defaults included),
    then the same-named System Variable parsed to the parameter type.
    """

    parameters: dict[str, Any]  # parameters as written in the Config
    references: dict[str, str]  # parameter name -> KEY
    variable_values: dict[str, Any]  # parameter name -> parsed System Variable value
    schema: dict[str, Any]  # the Descriptor's parameters_schema


@dataclass(frozen=True)
class RewriteStage:
    """Built-in Rewrite Query Transformation (03#rewrite-rules)."""

    model: ModelResource  # from llm_ref; a fixed choice
    prompt: str
    count: int
    include_original: bool
    cross_query_at: str  # "after_retrieval" or "after_rerank"
    cross_query_group_by: tuple[str, ...]
    cross_query_top_n: int | None


@dataclass(frozen=True)
class McpSettings:
    tool_name: str = "search"
    description: str | None = None
    text_field: str = "text"


@dataclass(frozen=True)
class InferencePlan:
    request_parameters: dict[str, RequestParameter]
    fixed_filters: list[dict[str, Any]]
    transformation: RemoteSegment | RewriteStage | None
    retrieval: BuiltinRetrieval | RemoteSegment | None
    rerank: RemoteSegment | None
    candidate_fields: Fields
    mcp: McpSettings
    uses_platform_index: bool
    # Module key ("query_transformation", "retrieval") -> parameters resolved per request.
    references: dict[str, ParameterReferences] = field(default_factory=dict)


@dataclass(frozen=True)
class CompiledSystem:
    config: dict[str, Any]
    values: SystemValues
    ingestion: IngestionPlan
    index: IndexPlan
    inference: InferencePlan
    warnings: list[str] = field(default_factory=list)

    @property
    def fingerprint(self) -> str:
        return self.index.fingerprint
