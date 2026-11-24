"""An immutable, fully built System snapshot. Requests keep the snapshot they started with."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rag_engine.adapters.index_store import IndexStore
from rag_engine.engine.index_writer import IndexWriter
from rag_engine.engine.plan import CompiledSystem


@dataclass(frozen=True)
class Snapshot:
    system_id: str
    config_revision: str
    compiled: CompiledSystem
    index_name: str
    index_generation: str
    store: IndexStore
    writer: IndexWriter
    ingestion_graph: Any
    inference_graph: Any


def index_name(env: str, system_id: str, generation: str) -> str:
    """``rag-<env>-<system_id>-<index_generation>`` (06#runtime-index-ownership)."""
    return f"rag-{env}-{system_id}-{generation}"
