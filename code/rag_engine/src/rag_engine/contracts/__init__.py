"""Shared contracts vendored from rag_platform.

The JSON Schemas under ``data/schemas`` are the single source of truth shared with the
Builder. Do not edit them here; change them in rag_platform and run
``scripts/sync_contracts.py``.
"""

from rag_engine.contracts.registry import (
    SCHEMA_BASE,
    ContractError,
    check,
    errors,
    http_def,
    load_json,
    schema_ref,
)

__all__ = ["SCHEMA_BASE", "ContractError", "check", "errors", "http_def", "load_json", "schema_ref"]
