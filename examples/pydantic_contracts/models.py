"""Pydantic draft for the contract objects named in diagram 03.

Not a released SDK. The canonical schemas and docs 13/14 remain authoritative.
No FastAPI or Engine dependency. IndexBinding is a NEW field-level proposal.
Use validators in addition to generated JSON Schema; schema generation cannot
encode every cross-field/semantic check below.
"""
import json
from typing import Annotated, ClassVar, Generic, Literal, TypeVar
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, JsonValue, field_validator, model_validator

NonEmptyText = Annotated[str, Field(min_length=1)]
ContentObject = Annotated[dict[str, JsonValue], Field(min_length=1)]
SOURCES = ("content", "base64", "uri")


def ingestion_json_schema(schema: dict) -> None:
    # Omission is permitted; an explicitly supplied null is not.
    # Keep FastAPI's advertised schema aligned with runtime validation.
    for name, prop in schema.get("properties", {}).items():
        if "anyOf" in prop:
            variants = [x for x in prop["anyOf"] if x != {"type": "null"}]
            if len(variants) == 1:
                prop.pop("anyOf")
                prop.update(variants[0])
            else:
                prop["anyOf"] = variants
        if prop.get("default", object()) is None:
            prop.pop("default", None)
    schema["oneOf"] = [{"required": [name]} for name in SOURCES]


class WireModel(BaseModel):
    """Strict JSON DTO; use to_payload() to omit unset optional fields."""
    model_config = ConfigDict(extra="forbid", strict=True)

    @model_validator(mode="after")
    def finite_json(self):
        json.dumps(self.model_dump(mode="python", by_alias=True, exclude_unset=True), allow_nan=False)
        return self

    def to_payload(self) -> dict:
        return self.model_dump(mode="json", by_alias=True, exclude_unset=True)


class OmittableModel(WireModel):
    """Fields can be omitted, but declared optional fields cannot be null."""
    model_config = ConfigDict(extra="forbid", strict=True, json_schema_extra=lambda schema: clean_omittable_schema(schema))

    @model_validator(mode="before")
    @classmethod
    def reject_explicit_null(cls, value):
        if isinstance(value, dict) and any(k in cls.model_fields and v is None for k,v in value.items()):
            raise ValueError("omit optional fields instead of supplying null")
        return value


def unique(values: list, name: str) -> None:
    encoded = [json.dumps(v, sort_keys=True, ensure_ascii=False, allow_nan=False) for v in values]
    if len(encoded) != len(set(encoded)):
        raise ValueError(f"duplicate values in {name}")


class IngestionDocument(WireModel):
    model_config = ConfigDict(extra="forbid", strict=True, json_schema_extra=ingestion_json_schema)

    document_id: NonEmptyText
    source_revision: NonEmptyText | None = None
    content: NonEmptyText | ContentObject | None = None
    base64: NonEmptyText | None = None
    uri: NonEmptyText | None = None
    media_type: NonEmptyText | None = None
    schema_id: NonEmptyText | None = None
    parsing_profile: NonEmptyText | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def check_wire_input(cls, value):
        if isinstance(value, dict):
            if any(item is None for item in value.values()):
                raise ValueError("omit optional root fields instead of sending null")
            if sum(name in value for name in SOURCES) != 1:
                raise ValueError("provide exactly one of content/base64/uri")
            json.dumps(value, allow_nan=False)
        return value

    def to_payload(self) -> dict:
        # Preserve omitted fields; do not send unused nullable Python defaults.
        return self.model_dump(mode="json", exclude_unset=True)


class ParsedDocument(WireModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    document_id: NonEmptyText
    source_revision: NonEmptyText
    units: list[dict[str, JsonValue]] = Field(min_length=1)
    metadata: dict[str, JsonValue]

    @field_validator("units")
    @classmethod
    def check_units(cls, units):
        for unit in units:
            if not unit or any(not key for key in unit):
                raise ValueError("each unit must contain named fields")
            if "text" in unit and not isinstance(unit["text"], str):
                raise ValueError("unit.text must be a string when present")
        json.dumps(units, allow_nan=False)
        return units

    @field_validator("metadata")
    @classmethod
    def check_metadata(cls, value):
        json.dumps(value, allow_nan=False)
        return value



def clean_omittable_schema(schema: dict) -> None:
    for prop in schema.get("properties", {}).values():
        if "anyOf" in prop:
            variants = [v for v in prop["anyOf"] if v != {"type":"null"}]
            if len(variants) == 1:
                prop.pop("anyOf"); prop.update(variants[0])
            else:
                prop["anyOf"] = variants
        if prop.get("default", object()) is None:
            prop.pop("default", None)


NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(ge=1)]


class ChunkSourceRef(OmittableModel):
    """Chunk metadata._rag.source_refs: document/unit/text provenance."""
    unit_index: NonNegativeInt
    field: NonEmptyText
    output_field: NonEmptyText
    role: Literal["split", "copy"]
    start: NonNegativeInt | None = None
    end: NonNegativeInt | None = None
    chunk_start: NonNegativeInt | None = None
    chunk_end: NonNegativeInt | None = None

    @model_validator(mode="after")
    def paired_offsets(self):
        for a,b in (("start","end"),("chunk_start","chunk_end")):
            left,right=getattr(self,a),getattr(self,b)
            if (left is None) != (right is None):
                raise ValueError(f"{a}/{b} must be supplied together")
            if left is not None and left >= right:
                raise ValueError("offsets must describe a nonempty [start,end) range")
        if self.role == "copy" and (self.start is not None or self.chunk_start is not None):
            raise ValueError("copy references a complete field")
        return self


class ChunkingIdentity(WireModel):
    chunking_fingerprint: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    chunk_ordinal: NonNegativeInt
    task_id: NonEmptyText


class RagMetadata(OmittableModel):
    # Retain existing trusted extensions as JSON; _rag is the current wire key.
    model_config = ConfigDict(extra="allow", strict=True, json_schema_extra=clean_omittable_schema)
    __pydantic_extra__: dict[str, JsonValue] = Field(init=False)
    source_refs: Annotated[list[ChunkSourceRef], Field(min_length=1)] | None = None
    chunking: ChunkingIdentity | None = None


class DenseVector(WireModel):
    values: Annotated[list[FiniteFloat], Field(min_length=1)]
    embedding_profile_id: NonEmptyText
    source_field: NonEmptyText  # key within Chunk.fields, not a new fields wrapper


class Chunk(WireModel):
    chunk_id: NonEmptyText
    document_id: NonEmptyText
    source_revision: NonEmptyText
    fields: Annotated[dict[NonEmptyText, JsonValue], Field(min_length=1)]
    metadata: dict[str, JsonValue]
    vectors: dict[NonEmptyText, DenseVector]

    @field_validator("metadata")
    @classmethod
    def validate_reserved_metadata(cls, metadata):
        if "_rag" in metadata:
            RagMetadata.model_validate(metadata["_rag"])
        return metadata

    @model_validator(mode="after")
    def vector_sources_exist(self):
        if any(v.source_field not in self.fields for v in self.vectors.values()):
            raise ValueError("a vector refers to a missing Chunk field")
        return self


class FilterCondition(WireModel):
    field: NonEmptyText
    operator: Literal["eq", "in"]
    value: str | list[str]

    @model_validator(mode="after")
    def operator_value(self):
        if self.operator == "eq" and not isinstance(self.value, str):
            raise ValueError("eq requires a string")
        if self.operator == "in" and (not isinstance(self.value, list) or not self.value):
            raise ValueError("in requires a nonempty string list")
        return self


class ResultItem(WireModel):
    chunk: Chunk
    score: FiniteFloat | None = None


class ResultSet(WireModel):
    key: NonEmptyText
    items: list[ResultItem] = Field(default_factory=list)


class QueryContext(WireModel):
    ori_query: NonEmptyText
    query: NonEmptyText
    filters: list[FilterCondition] = Field(default_factory=list)
    result_sets: list[ResultSet] = Field(default_factory=list)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def unique_keys(self):
        unique([r.key for r in self.result_sets], "ResultSet.key within QueryContext")
        return self


class VectorIndexBinding(WireModel):
    """Proposed entry under IndexBinding.vector_bindings; key is vector name."""
    embedding_profile_id: NonEmptyText
    source_field: NonEmptyText
    dimensions: PositiveInt


class IndexBinding(WireModel):
    """NEW PROPOSAL: field names/requiredness await review; not frozen SDK."""
    contract_version: Literal["index-binding-0.1-proposal"]
    index_ref: NonEmptyText
    system_id: NonEmptyText
    backend: Literal["elasticsearch", "local_search"]
    collection: NonEmptyText
    index_generation: NonEmptyText
    mapping_version: NonEmptyText
    document_schema_version: NonEmptyText
    capabilities: list[Literal["fulltext", "dense_vector", "filter"]]
    fulltext_fields: list[NonEmptyText]
    filter_fields: list[NonEmptyText]
    vector_bindings: dict[NonEmptyText, VectorIndexBinding]
    searchable: bool

    @model_validator(mode="after")
    def capability_consistency(self):
        for name in ("capabilities","fulltext_fields","filter_fields"):
            unique(getattr(self,name),name)
        for cap, configured in (("fulltext",self.fulltext_fields),
                                ("filter",self.filter_fields),
                                ("dense_vector",self.vector_bindings)):
            if bool(configured) != (cap in self.capabilities):
                raise ValueError(f"{cap} capability differs from configured fields")
        return self


T = TypeVar("T")


class ModuleResult(WireModel, Generic[T]):
    """Success-only teaching envelope; metrics/errors and lifecycle remain pending."""
    data: T


def validate_result_order(result: ResultSet) -> None:
    """Positions are ranks. If every score exists, require higher scores first.

    Rank-only results preserve the adapter's order; RRF uses positions directly.
    """
    scores = [item.score for item in result.items]
    if all(score is not None for score in scores) and scores != sorted(scores, reverse=True):
        raise ValueError("numeric scores must be ordered higher first")


def require_sum_scores(results: list[ResultSet]) -> None:
    """Presence check only; comparability/normalization is separate Config."""
    if any(item.score is None for result in results for item in result.items):
        raise ValueError("Sum Score requires every score; use RRF for rank-only output")


def validate_chunk_binding(chunk: Chunk, binding: IndexBinding) -> None:
    """Validate a full stored Chunk's vectors against a trusted Binding.

    Retrieval projections may omit vectors; do not use this function to infer
    completeness or authorization of an untrusted request.
    """
    if set(chunk.vectors) != set(binding.vector_bindings):
        raise ValueError("full Chunk vectors differ from configured vector bindings")
    for name,vector in chunk.vectors.items():
        target=binding.vector_bindings[name]
        if (vector.embedding_profile_id,vector.source_field,len(vector.values)) != (
            target.embedding_profile_id,target.source_field,target.dimensions):
            raise ValueError(f"vector binding mismatch: {name}")


PUBLIC_MODELS = [IngestionDocument, ParsedDocument, ChunkSourceRef, ChunkingIdentity,
                 RagMetadata, DenseVector, Chunk, FilterCondition, ResultItem,
                 ResultSet, QueryContext, VectorIndexBinding, IndexBinding]
