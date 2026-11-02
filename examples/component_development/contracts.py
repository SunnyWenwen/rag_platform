"""Demo Pydantic models for the repository's shared JSON Schemas.

Not a released SDK. The canonical schemas and docs 13/14 remain authoritative.
No FastAPI or Engine dependency is required by this module.
"""
import json
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

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


class IngestionDocument(BaseModel):
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


class ParsedDocument(BaseModel):
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


def validate_structured_json_output(source: IngestionDocument,
                                    documents: list[ParsedDocument]) -> None:
    """Semantic checks specific to this one-document demonstration Component.

    General Parsers may emit multiple documents, with an explicit ID policy.
    """
    if len(documents) != 1:
        raise ValueError("this Component must return exactly one document")
    document = documents[0]
    if (document.document_id, document.source_revision) != (source.document_id, source.source_revision):
        raise ValueError("document identity/revision must be inherited")
    if document.metadata != source.metadata:
        raise ValueError("document metadata must be preserved")
    if any(not isinstance(unit.get("text"), str) or not unit["text"].strip()
           for unit in document.units):
        raise ValueError("this Component must produce nonblank unit.text")
