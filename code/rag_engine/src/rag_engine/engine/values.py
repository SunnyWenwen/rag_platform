"""System Variables and Secrets (05_system_config.md#system-secret) and request parameters."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from rag_engine.core.errors import ConfigInvalid, RequestInvalid

RESERVED_SECRET_KEYS = (
    "INGESTION_API_USERNAME",
    "INGESTION_API_PASSWORD",
    "INFERENCE_API_USERNAME",
    "INFERENCE_API_PASSWORD",
)
EXPRESSION = re.compile(r"^\{\{([A-Za-z_][A-Za-z0-9_]*)\}\}$")
REFERENCE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")
_JSON_TYPES: dict[str, type | tuple[type, ...]] = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
}


@dataclass(frozen=True)
class SystemValues:
    secrets: dict[str, str] = field(default_factory=dict)
    variables: dict[str, str] = field(default_factory=dict)

    def credentials(self, pipeline: str) -> tuple[str, str] | None:
        prefix = pipeline.upper()
        username = self.secrets.get(f"{prefix}_API_USERNAME")
        password = self.secrets.get(f"{prefix}_API_PASSWORD")
        return (username, password) if username and password else None


def load_values(
    config: dict[str, Any], environment: Mapping[str, str] | None, optional: set[str] | None = None
) -> SystemValues:
    """DEV takes the values carried in the Config; standalone reads same-named env vars.

    Keys in ``optional`` may be missing (they are left out of the result)."""
    optional = optional or set()
    secrets = config.get("secret", {})
    variables = config.get("variable", {})
    reserved = sorted(set(variables) & set(RESERVED_SECRET_KEYS))
    if reserved:
        raise ConfigInvalid("reserved System API key cannot be a Variable", path=f"/config/variable/{reserved[0]}")
    duplicates = sorted(set(secrets) & set(variables))
    if duplicates:
        raise ConfigInvalid("key is declared as both Secret and Variable", path=f"/config/variable/{duplicates[0]}")

    def resolve(scope: str, declared: dict[str, Any]) -> dict[str, str]:
        resolved: dict[str, str] = {}
        for key, value in declared.items():
            if environment is not None:
                value = environment.get(key)
            if not isinstance(value, str):
                if key in optional:
                    continue
                raise ConfigInvalid(f"missing value for {key}", path=f"/config/{scope}/{key}")
            resolved[key] = value
        return resolved

    return SystemValues(resolve("secret", secrets), resolve("variable", variables))


def references(value: Any, path: str) -> list[tuple[str, str]]:
    """All ``{{KEY}}`` references inside a JSON value with their JSON Pointer."""
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            found.extend(references(item, f"{path}/{key.replace('~', '~0').replace('/', '~1')}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(references(item, f"{path}/{index}"))
    elif isinstance(value, str):
        found.extend((match[1], path) for match in REFERENCE.finditer(value))
    return found


@dataclass(frozen=True)
class RequestParameter:
    name: str
    type: str
    required: bool
    default: Any = None
    has_default: bool = False


def request_parameters(declarations: list[dict[str, Any]], path: str) -> dict[str, RequestParameter]:
    specs: dict[str, RequestParameter] = {}
    for index, item in enumerate(declarations):
        if item["name"] in specs:
            raise ConfigInvalid("duplicate request parameter", path=f"{path}/{index}/name")
        has_default = "default_value" in item
        default = None
        if has_default:
            try:
                default = json.loads(item["default_value"])
            except ValueError as error:
                raise ConfigInvalid("default_value must be JSON text", path=f"{path}/{index}/default_value") from error
            if not type_ok(item["type"], default):
                raise ConfigInvalid("default_value does not match type", path=f"{path}/{index}/default_value")
        specs[item["name"]] = RequestParameter(item["name"], item["type"], item["required"], default, has_default)
    return specs


def type_ok(kind: str, value: Any) -> bool:
    if kind in ("integer", "number") and isinstance(value, bool):
        return False
    return isinstance(value, _JSON_TYPES[kind])


def bind_request(specs: dict[str, RequestParameter], supplied: dict[str, Any]) -> dict[str, Any]:
    """Validate a request's ``parameters`` against the declarations and apply defaults."""
    bound: dict[str, Any] = {}
    for name in supplied:
        if name not in specs:
            raise RequestInvalid(f"undeclared parameter {name}", path=f"/parameters/{name}")
    for name, spec in specs.items():
        if name in supplied:
            if not type_ok(spec.type, supplied[name]):
                raise RequestInvalid(f"parameter {name} must be {spec.type}", path=f"/parameters/{name}")
            bound[name] = supplied[name]
        elif spec.has_default:
            bound[name] = spec.default
        elif spec.required:
            raise RequestInvalid(f"parameter {name} is required", path=f"/parameters/{name}")
    return bound


def resolve_parameters(value: Any, request: dict[str, Any], variables: dict[str, str]) -> Any:
    """Resolve whole-value ``{{KEY}}`` expressions: request value first, then Variable."""
    if isinstance(value, dict):
        return {key: resolve_parameters(item, request, variables) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_parameters(item, request, variables) for item in value]
    if isinstance(value, str):
        match = EXPRESSION.match(value)
        if match:
            key = match[1]
            if key in request:
                return request[key]
            if key in variables:
                return variables[key]
            raise RequestInvalid(f"no value for parameter {key}", path=f"/parameters/{key}")
    return value
