"""RFC 8785 JSON Canonicalization and the SHA-256 identifiers built on it."""

from __future__ import annotations

import hashlib
from typing import Any

import rfc8785


def canonical_bytes(value: Any) -> bytes:
    return rfc8785.dumps(value)


def sha256_hex(value: Any) -> str:
    """Lowercase hex SHA-256 of the canonical UTF-8 JSON encoding of ``value``."""
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def chunk_data_id(document_id: str, unit_ordinal: int, chunk_ordinal: int) -> str:
    """Built-in Chunking ``data_id`` (02_data_contracts.md#document-identities)."""
    return sha256_hex([document_id, unit_ordinal, chunk_ordinal])


def es_document_id(document_id: str, write_id: str, data_id: str) -> str:
    """Elasticsearch ``_id`` for one chunk of one write batch."""
    return sha256_hex([document_id, write_id, data_id])
