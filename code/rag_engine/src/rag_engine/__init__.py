"""Retrieval Engine, Components and Runtime API.

Layering (enforced by import-linter, see pyproject.toml):
    runtime  -> HTTP service, pod-local job control, lifecycle
    engine   -> Config compiler, fingerprint, LangGraph pipelines, result processing
    components -> built-in methods (chunking, embedding, retrieval helpers, remote adapter)
    adapters -> external systems (Elasticsearch, embedding service, tokenizer files)
    contracts -> vendored JSON Schemas shared with the Builder
"""

__version__ = "0.1.0"
