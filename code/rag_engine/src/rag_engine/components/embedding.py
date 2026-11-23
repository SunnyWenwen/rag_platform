"""Dense Embedding: attach named vectors to chunked Documents."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from rag_engine.adapters.embedding import Embedder
from rag_engine.adapters.tokenizer import Tokenizer
from rag_engine.core.errors import DocumentFailed
from rag_engine.core.resources import EmbeddingProfile
from rag_engine.core.types import Document

TEMPLATE_FIELD = re.compile(r"\{\{\s*structdata\.([^{}]+?)\s*\}\}")


@dataclass(frozen=True)
class DenseSettings:
    profile: str
    mappings: tuple[tuple[str, str], ...]  # (source_field, vector_name)
    compose_text: bool
    composition_field: str | None
    composition_template: str | None

    @classmethod
    def from_parameters(cls, values: dict[str, Any]) -> DenseSettings:
        compose = values.get("compose_text", False)
        return cls(
            profile=values["profile"],
            mappings=tuple((item["source_field"], item["vector_name"]) for item in values["mappings"]),
            compose_text=compose,
            composition_field=values.get("composition_field", "embedding_text") if compose else None,
            composition_template=values.get("composition_template") if compose else None,
        )


def render_template(template: str, structdata: dict[str, Any]) -> str:
    return TEMPLATE_FIELD.sub(lambda match: str(structdata.get(match[1].strip(), "")), template)


async def embed_documents(
    documents: list[Document],
    settings: DenseSettings,
    profile: EmbeddingProfile,
    embedder: Embedder,
    tokenizer: Tokenizer | None,
) -> list[Document]:
    output = [dict(document, structdata=dict(document["structdata"])) for document in documents]
    if settings.compose_text and settings.composition_field and settings.composition_template:
        for document in output:
            document["structdata"][settings.composition_field] = render_template(
                settings.composition_template, document["structdata"]
            )
    for source_field, vector_name in settings.mappings:
        texts = [document["structdata"][source_field] for document in output]
        if tokenizer is not None:
            for text in texts:
                if len(tokenizer.spans(text)) > profile.max_input_tokens:
                    raise DocumentFailed(
                        f"{source_field} exceeds {profile.max_input_tokens} tokens for {profile.profile_id}",
                        code="EMBEDDING_INPUT_TOO_LONG",
                        module="embedding",
                    )
        vectors = await embedder.embed(texts, profile)
        for document, values in zip(output, vectors, strict=True):
            document.setdefault("vectors", {})[vector_name] = {
                "values": values,
                "embedding_profile_id": profile.profile_id,
                "source_field": source_field,
            }
    return output
