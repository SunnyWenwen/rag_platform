"""Runtime resources: the models, tokenizers and text analysis a Runtime deployment offers.

Resources are deployment settings, not System Config. The Catalog exposes their IDs and
labels to the Builder; System Config references them by ID (for example ``profile: bge-m3``).
Anything that changes indexed output (model revision, tokenizer revision, analyzer) is part
of the index fingerprint, so change it only together with a new Runtime release.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class EmbeddingProfile:
    profile_id: str
    label: str
    dimensions: int
    model_id: str
    model_revision: str
    # OpenAI-compatible base URL such as http://bge-m3-embedding/v1. None selects the
    # deterministic hash embedder, which is only for tests and local demos.
    endpoint: str | None = None
    request_model: str | None = None
    max_input_tokens: int = 8192
    batch_size: int = 32
    timeout_seconds: float = 30.0
    tokenizer_profile_id: str | None = None
    # Elasticsearch dense_vector index_options, for example {"type": "int8_hnsw"}.
    index_options: dict[str, Any] | None = None
    # Name of the environment variable holding the service token, sent as
    # "Authorization: Bearer <token>". The token itself never goes in the resources file.
    api_key_env: str | None = None


@dataclass(frozen=True)
class TokenizerProfile:
    profile_id: str
    label: str
    revision: str
    # "huggingface" loads tokenizer.json with the tokenizers library; "simple" is a
    # dependency-free tokenizer for tests (CJK characters and words).
    kind: str = "simple"
    path: str | None = None


@dataclass(frozen=True)
class ModelResource:
    model_id: str
    label: str


@dataclass(frozen=True)
class RuntimeResources:
    profiles: dict[str, EmbeddingProfile] = field(default_factory=dict)
    tokenizer_profiles: dict[str, TokenizerProfile] = field(default_factory=dict)
    models: dict[str, ModelResource] = field(default_factory=dict)
    # "zh_ik" (stconvert t2s + IK) for production, "standard" for fixtures.
    text_analysis: str = "zh_ik"

    def catalog_view(self) -> dict[str, Any]:
        return {
            "profiles": {
                key: {"label": value.label, "dimensions": value.dimensions} for key, value in self.profiles.items()
            },
            "tokenizer_profiles": {key: {"label": value.label} for key, value in self.tokenizer_profiles.items()},
            "models": {key: {"label": value.label} for key, value in self.models.items()},
            "elasticsearch_services": {},
        }

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> RuntimeResources:
        return cls(
            profiles={
                key: EmbeddingProfile(profile_id=key, **value) for key, value in data.get("profiles", {}).items()
            },
            tokenizer_profiles={
                key: TokenizerProfile(profile_id=key, **value)
                for key, value in data.get("tokenizer_profiles", {}).items()
            },
            models={key: ModelResource(model_id=key, **value) for key, value in data.get("models", {}).items()},
            text_analysis=data.get("text_analysis", "zh_ik"),
        )

    @classmethod
    def from_file(cls, path: str | Path) -> RuntimeResources:
        return cls.from_mapping(yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {})


def fixture_resources() -> RuntimeResources:
    """Resources matching the rag_platform contract fixtures (Catalog ``catalog-5``)."""
    return RuntimeResources.from_mapping(
        {
            "profiles": {
                "text-v1": {
                    "label": "text-v1",
                    "dimensions": 3,
                    "model_id": "fixture-model",
                    "model_revision": "1",
                    "tokenizer_profile_id": "fixture",
                }
            },
            "tokenizer_profiles": {"fixture": {"label": "DEV Tokenizer", "revision": "fixture@1"}},
            "models": {"default-llm": {"label": "DEV LLM"}},
            "text_analysis": "standard",
        }
    )
