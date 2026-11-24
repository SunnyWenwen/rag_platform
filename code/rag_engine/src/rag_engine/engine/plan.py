"""Plan types produced by ``engine/compiler.py`` and executed by ``engine/pipelines.py``.

Plain frozen dataclasses with no logic, so every layer can read a compiled System
without importing the compiler.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rag_engine.components.chunking import RecursiveSettings
from rag_engine.components.embedding import DenseSettings
from rag_engine.components.remote import RemoteCall
from rag_engine.core.resources import EmbeddingProfile, TokenizerProfile
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
    settings: RecursiveSettings
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
class McpSettings:
    tool_name: str = "search"
    description: str | None = None
    text_field: str = "text"


@dataclass(frozen=True)
class InferencePlan:
    request_parameters: dict[str, RequestParameter]
    fixed_filters: list[dict[str, Any]]
    transformation: RemoteSegment | None
    retrieval: BuiltinRetrieval | RemoteSegment | None
    rerank: RemoteSegment | None
    candidate_fields: Fields
    mcp: McpSettings
    uses_platform_index: bool


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
