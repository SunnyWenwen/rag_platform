"""Tokenizers measured in tokens but sliced by character offsets.

Chunking never decodes token IDs back to text. It uses the character offsets of each token
so every chunk is an exact substring of the source text (Q-004).
"""

from __future__ import annotations

import re
from functools import cache
from typing import Protocol

from rag_engine.core.errors import EngineError
from rag_engine.core.resources import TokenizerProfile

Span = tuple[int, int]


class Tokenizer(Protocol):
    revision: str

    def spans(self, text: str) -> list[Span]:
        """Character spans ``[start, end)`` of the tokens in ``text``."""
        ...


# One token per CJK character, otherwise runs of non-CJK word characters or single symbols.
_CJK = "\u3400-\u9fff\uf900-\ufaff\U00020000-\U0002ffff"
_SIMPLE_TOKEN = re.compile(rf"[{_CJK}]|[^\W{_CJK}]+|[^\w\s]", re.UNICODE)


class SimpleTokenizer:
    """Deterministic tokenizer for tests and fixtures. Not a model tokenizer."""

    def __init__(self, revision: str) -> None:
        self.revision = revision

    def spans(self, text: str) -> list[Span]:
        return [match.span() for match in _SIMPLE_TOKEN.finditer(text)]


class HuggingFaceTokenizer:
    """Loads a ``tokenizer.json`` (for example BAAI/bge-m3) with the tokenizers library."""

    def __init__(self, path: str, revision: str) -> None:
        from tokenizers import Tokenizer as HFTokenizer

        self.revision = revision
        self._tokenizer = HFTokenizer.from_file(path)
        self._tokenizer.no_truncation()
        self._tokenizer.no_padding()

    def spans(self, text: str) -> list[Span]:
        encoding = self._tokenizer.encode(text, add_special_tokens=False)
        # SentencePiece may emit empty-width pieces (for example the leading "▁"); drop them.
        return [(start, end) for start, end in encoding.offsets if end > start]


@cache
def load_tokenizer(profile: TokenizerProfile) -> Tokenizer:
    if profile.kind == "simple":
        return SimpleTokenizer(profile.revision)
    if profile.kind == "huggingface":
        if not profile.path:
            raise EngineError(f"tokenizer profile {profile.profile_id} has no path", code="RUNTIME_NOT_READY")
        return HuggingFaceTokenizer(profile.path, profile.revision)
    raise EngineError(f"unknown tokenizer kind {profile.kind}", code="RUNTIME_NOT_READY")
