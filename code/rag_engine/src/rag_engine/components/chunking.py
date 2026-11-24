"""Chunking measured in tokens: Recursive, Fixed-size and Header-aware (03#chunking).

Token rules (03#chunk-token-rules): special tokens are not counted, chunks are cut at the
character offsets of tokens so every chunk is a substring of the source, and the count at
split time is final (no re-encoding).
"""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass
from typing import Any

from rag_engine.adapters.tokenizer import Span, Tokenizer
from rag_engine.core.canonical import chunk_data_id
from rag_engine.core.errors import DocumentFailed
from rag_engine.core.types import Document

DEFAULT_SEPARATORS = ["\n\n", "\n", " ", ""]
DEFAULT_HEADER_LEVELS = (1, 2, 3)
METHODS = ("recursive", "fixed_size", "header_aware")


@dataclass(frozen=True)
class ChunkSettings:
    split_field: str
    output_field: str
    copy_fields: tuple[tuple[str, str], ...]
    max_tokens: int
    overlap_tokens: int
    separators: tuple[str, ...]  # recursive and header_aware
    keep_separator: bool  # recursive and header_aware
    method: str = "recursive"  # one of METHODS (the Config component_id)
    header_levels: tuple[int, ...] = DEFAULT_HEADER_LEVELS  # header_aware only

    @classmethod
    def from_parameters(cls, method: str, values: dict[str, Any]) -> ChunkSettings:
        return cls(
            split_field=values["split_field"],
            output_field=values["output_field"],
            copy_fields=tuple((item["source_field"], item["output_field"]) for item in values["copy_fields"]),
            max_tokens=values["max_tokens"],
            overlap_tokens=values["overlap_tokens"],
            separators=tuple(values.get("separators", DEFAULT_SEPARATORS)),
            keep_separator=values.get("keep_separator", False),
            method=method,
            header_levels=tuple(sorted(set(values.get("header_levels", DEFAULT_HEADER_LEVELS)))),
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
    text: str, start: int, end: int, settings: ChunkSettings, index: _TokenIndex, separators: tuple[str, ...]
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


def split_text(text: str, settings: ChunkSettings, tokenizer: Tokenizer) -> list[str]:
    """Split ``text`` with the configured method."""
    index = _TokenIndex(tokenizer.spans(text))
    if settings.method == "fixed_size":
        return fixed_windows(text, settings, index)
    if settings.method == "header_aware":
        chunks: list[str] = []
        for start, end in markdown_sections(text, settings.header_levels):
            chunks.extend(_recursive(text, start, end, settings, index))
        return chunks
    return _recursive(text, 0, len(text), settings, index)


def fixed_windows(text: str, settings: ChunkSettings, index: _TokenIndex) -> list[str]:
    """Fixed token windows: step ``max_tokens - overlap_tokens``, stop once a window reaches the end.

    Example from 03#chunking: 11 tokens, size 4, overlap 1 -> [0:4] [3:7] [6:10] [9:11].
    """
    total = len(index.starts)
    step = settings.max_tokens - settings.overlap_tokens
    chunks = []
    first = 0
    while first < total:
        last = min(first + settings.max_tokens, total)
        chunks.append(text[index.starts[first] : index.ends[last - 1]])
        if last == total:
            break
        first += step
    return chunks


# ATX headings (03#header-aware-rules): up to 3 leading spaces, 1-6 "#", then a space, tab or end.
_HEADING = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]|$)")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


def markdown_sections(text: str, levels: tuple[int, ...]) -> list[tuple[int, int]]:
    """Character ranges of ``text`` split before each heading whose level is in ``levels``.

    Text before the first heading is its own section. Lines inside fenced code blocks are
    never headings. Without any matching heading the whole text is one section.
    """
    starts = [0]
    fence = ""  # the opening fence while inside a fenced code block
    position = 0
    for raw_line in text.split("\n"):
        line = raw_line.rstrip("\r")
        fence_match = _FENCE.match(line)
        if fence:
            closing = fence_match is not None and fence_match[1][0] == fence[0] and len(fence_match[1]) >= len(fence)
            if closing and fence_match is not None and not fence_match[2].strip():
                fence = ""
        elif fence_match:
            fence = fence_match[1]
        else:
            heading = _HEADING.match(line)
            if heading and len(heading[1]) in levels and position > 0:
                starts.append(position)
        position += len(raw_line) + 1
    ends = [*starts[1:], len(text)]
    return [(start, end) for start, end in zip(starts, ends, strict=True) if text[start:end].strip()]


def _recursive(text: str, start: int, end: int, settings: ChunkSettings, index: _TokenIndex) -> list[str]:
    """Recursive split of ``text[start:end]``: at most ``max_tokens``, about ``overlap_tokens`` overlap."""
    pieces = [
        piece for piece in _pieces(text, start, end, settings, index, settings.separators) if index.count(*piece) > 0
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
    return [text[first:last].strip() for first, last in chunks if text[first:last].strip()]


def chunk_documents(units: list[Document], settings: ChunkSettings, tokenizer: Tokenizer) -> list[Document]:
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
