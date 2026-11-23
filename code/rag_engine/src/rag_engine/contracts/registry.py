"""Load the vendored JSON Schemas and validate instances against them."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from functools import cache
from importlib import resources
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

SCHEMA_BASE = "https://rag-builder.example/schemas/"
_DATA = resources.files("rag_engine.contracts") / "data"


@dataclass(frozen=True)
class ContractError(Exception):
    """A contract violation located by a JSON Pointer into the validated instance."""

    message: str
    path: str = ""

    def __str__(self) -> str:
        return f"{self.message} at {self.path or '/'}"


def load_json(relative: str) -> Any:
    """Read a vendored JSON file, for example ``schemas/runtime_http.schema.json``."""
    return json.loads((_DATA / relative).read_text(encoding="utf-8"))


@cache
def _schemas() -> dict[str, dict[str, Any]]:
    """Vendored schemas keyed by file name."""
    return {
        entry.name: json.loads(entry.read_text(encoding="utf-8"))
        for entry in (_DATA / "schemas").iterdir()
        if entry.name.endswith(".schema.json")
    }


@cache
def _registry() -> Registry:
    registry: Registry = Registry()
    for schema in _schemas().values():
        resource = Resource.from_contents(schema, default_specification=DRAFT202012)
        registry = registry.with_resource(schema["$id"], resource)
    return registry


def schema_ref(file_name: str, pointer: str = "") -> dict[str, Any]:
    """Return a schema that references ``file_name`` and an optional JSON Pointer fragment."""
    schema_id = _schemas()[file_name]["$id"]
    return {"$ref": f"{schema_id}{'#' + pointer if pointer else ''}"}


def http_def(name: str) -> dict[str, Any]:
    """Schema for one ``$defs`` entry of runtime_http.schema.json."""
    return schema_ref("runtime_http.schema.json", f"/$defs/{name}")


@cache
def _validator(serialized: str) -> Draft202012Validator:
    return Draft202012Validator(json.loads(serialized), registry=_registry(), format_checker=FormatChecker())


def _pointer(error: ValidationError) -> str:
    return "".join(f"/{str(part).replace('~', '~0').replace('/', '~1')}" for part in error.absolute_path)


def errors(schema: dict[str, Any], instance: Any) -> Iterator[ContractError]:
    validator = _validator(json.dumps(schema, sort_keys=True))
    for error in sorted(validator.iter_errors(instance), key=lambda item: list(item.absolute_path)):
        yield ContractError(error.message, _pointer(error))


def check(schema: dict[str, Any], instance: Any, *, prefix: str = "") -> None:
    """Raise the first ContractError, with its path prefixed by ``prefix``."""
    for error in errors(schema, instance):
        raise ContractError(error.message, prefix + error.path)
