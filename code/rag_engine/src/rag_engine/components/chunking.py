"""Recursive Chunking measured in tokens (03_engine_and_components.md#chunking).

Chunks are exact substrings of the source text. Token counts come from the configured
tokenizer's character spans, so no token IDs are decoded back into text.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass
from typing import Any

from rag_engine.adapters.tokenizer import Span, Tokenizer
from rag_engine.core.canonical import chunk_data_id
from rag_engine.core.errors import DocumentFailed
from rag_engine.core.types import Document

DEFAULT_SEPARATORS = ["\n\n", "\n", " ", ""]


@dataclass(frozen=True)
class RecursiveSettings:
    split_field: str
    output_field: str
    copy_fields: tuple[tuple[str, str], ...]
    max_tokens: int
    overlap_tokens: int
    separators: tuple[str, ...]
    keep_separator: bool

    @classmethod
    def from_parameters(cls, values: dict[str, Any]) -> RecursiveSettings:
        return cls(
            split_field=values["split_field"],
            output_field=values["output_field"],
            copy_fields=tuple((item["source_field"], item["output_field"]) for item in values["copy_fields"]),
            max_tokens=values["max_tokens"],
            overlap_tokens=values["overlap_tokens"],
            separators=tuple(values.get("separators", DEFAULT_SEPARATORS)),
            keep_separator=values.get("keep_separator", False),
        )


class _TokenIndex:
    def __init__(self, spans: list[Span]) -> None:
        self.starts = [start for start, _ in spans]
        self.ends = [end for _, end in spans]

    def count(self, start: int, end: int) -> int:
        """Tokens fully inside ``[start, end)``."""
        first = bisect.bisect_left(self.starts, start)
        last = bisect.bisect_right(self.ends, end)
        return max(0, last - first)

    def token_ranges(self, start: int, end: int, size: int) -> list[tuple[int, int]]:
        """Split ``[start, end)`` into windows of at most ``size`` tokens."""
        first = bisect.bisect_left(self.starts, start)
        last = bisect.bisect_right(self.ends, end)
        ranges = []
        for offset in range(first, last, size):
            stop = min(offset + size, last) - 1
            ranges.append((self.starts[offset], self.ends[stop]))
        return ranges


def _split(text: str, start: int, end: int, separator: str, keep: bool) -> list[tuple[int, int]]:
    pieces = []
    cursor = start
    while True:
        found = text.find(separator, cursor, end)
        if found < 0:
            pieces.append((cursor, end))
            return [piece for piece in pieces if piece[1] > piece[0]]
        pieces.append((cursor, found + len(separator) if keep else found))
        cursor = found + len(separator)


def _pieces(
    text: str, start: int, end: int, settings: RecursiveSettings, index: _TokenIndex, separators: tuple[str, ...]
) -> list[tuple[int, int]]:
    if index.count(start, end) <= settings.max_tokens:
        return [(start, end)]
    for position, separator in enumerate(separators):
        if separator == "":
            return index.token_ranges(start, end, settings.max_tokens)
        if text.find(separator, start, end) >= 0:
            result = []
            for piece_start, piece_end in _split(text, start, end, separator, settings.keep_separator):
                result.extend(_pieces(text, piece_start, piece_end, settings, index, separators[position + 1 :]))
            return result
    return index.token_ranges(start, end, settings.max_tokens)


def split_text(text: str, settings: RecursiveSettings, tokenizer: Tokenizer) -> list[str]:
    """Split ``text`` into chunks of at most ``max_tokens`` with about ``overlap_tokens`` overlap."""
    index = _TokenIndex(tokenizer.spans(text))
    pieces = [
        piece for piece in _pieces(text, 0, len(text), settings, index, settings.separators) if index.count(*piece) > 0
    ]
    chunks: list[tuple[int, int]] = []
    current: list[tuple[int, int]] = []
    for piece in pieces:
        if current and index.count(current[0][0], piece[1]) > settings.max_tokens:
            chunks.append((current[0][0], current[-1][1]))
            # Carry trailing pieces forward as overlap while the new chunk still fits.
            carried: list[tuple[int, int]] = []
            for previous in reversed(current):
                if index.count(previous[0], current[-1][1]) > settings.overlap_tokens:
                    break
                if index.count(previous[0], piece[1]) > settings.max_tokens:
                    break
                carried.insert(0, previous)
            current = carried
        current.append(piece)
    if current:
        chunks.append((current[0][0], current[-1][1]))
    return [text[start:end].strip() for start, end in chunks if text[start:end].strip()]


def chunk_documents(units: list[Document], settings: RecursiveSettings, tokenizer: Tokenizer) -> list[Document]:
    """Chunk each parsed unit of one source document. Overlap never crosses units."""
    output: list[Document] = []
    for unit_ordinal, unit in enumerate(units):
        structdata = unit.get("structdata", {})
        source = structdata.get(settings.split_field)
        if not isinstance(source, str) or not source.strip():
            raise DocumentFailed(
                f"split field {settings.split_field} is missing or blank",
                code="CHUNK_SOURCE_INVALID",
                module="chunking",
            )
        texts = split_text(source, settings, tokenizer)
        if not texts:
            raise DocumentFailed("chunking produced no chunks", code="CHUNK_SOURCE_INVALID", module="chunking")
        for chunk_ordinal, text in enumerate(texts):
            fields: dict[str, Any] = {settings.output_field: text}
            for source_field, output_field in settings.copy_fields:
                if source_field in structdata:
                    fields[output_field] = structdata[source_field]
            chunk: Document = {
                "document_id": unit["document_id"],
                "data_id": chunk_data_id(unit["document_id"], unit_ordinal, chunk_ordinal),
                "structdata": fields,
            }
            if "source_revision" in unit:
                chunk["source_revision"] = unit["source_revision"]
            if "metadata" in unit:
                chunk["metadata"] = unit["metadata"]
            output.append(chunk)
    return output
