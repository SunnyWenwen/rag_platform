"""Typed views of the shared data contracts used inside the Engine.

Documents and QueryContexts stay plain JSON dicts so they round-trip the HTTP and Remote
contracts unchanged. Field and vector declarations are typed because the compiler derives
them module by module.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any

Document = dict[str, Any]
QueryContext = dict[str, Any]

FIELD_TYPES = ("string", "string_array", "integer", "number", "boolean", "date", "datetime")
RANGE_TYPES = frozenset({"integer", "number", "date", "datetime"})


@dataclass(frozen=True)
class FieldSpec:
    """One ``structdata`` field as declared by Data Meta Schema."""

    type: str
    required: bool = True
    searchable: bool = False
    filterable: bool = False

    @classmethod
    def from_meta(cls, meta: dict[str, Any]) -> FieldSpec:
        return cls(
            type=meta["type"],
            required=meta["required"],
            searchable=meta.get("searchable", False),
            filterable=meta.get("filterable", False),
        )

    def override(self, values: dict[str, Any]) -> FieldSpec:
        return replace(self, **{key: values[key] for key in ("searchable", "filterable") if key in values})

    def as_meta(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VectorSpec:
    """A named dense vector produced by Embedding (or declared by a Remote segment)."""

    source_field: str
    embedding_profile_id: str
    dimensions: int


Fields = dict[str, FieldSpec]
Vectors = dict[str, VectorSpec]


def fields_meta(fields: Fields) -> dict[str, dict[str, Any]]:
    return {name: spec.as_meta() for name, spec in fields.items()}
