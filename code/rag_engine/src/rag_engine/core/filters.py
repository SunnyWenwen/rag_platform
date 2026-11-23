"""Filter validation and evaluation, following the Filter contract in 02_data_contracts.md.

* Top-level conditions are ANDed, ``{"any": [...]}`` groups are ORed.
* ``eq`` takes one value, ``in`` a non-empty array. Values are strictly typed.
* ``string_array`` fields match element-wise. Missing fields and empty arrays never match.
* ``datetime`` values compare as UTC instants; ``date`` values as calendar dates.
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime
from typing import Any

from rag_engine.core.errors import EngineError
from rag_engine.core.types import RANGE_TYPES, Fields, FieldSpec

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})$")


def _value_ok(kind: str, value: Any) -> bool:
    if kind in ("string", "string_array"):
        return isinstance(value, str)
    if kind == "boolean":
        return isinstance(value, bool)
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number":
        return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)
    if kind == "date":
        if not (isinstance(value, str) and _DATE.match(value)):
            return False
        try:
            date.fromisoformat(value)
        except ValueError:
            return False
        return True
    if kind == "datetime":
        if not (isinstance(value, str) and _DATETIME.match(value)):
            return False
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return False
        return True
    return False


def filter_fields(fields: Fields) -> dict[str, FieldSpec]:
    """Filterable fields keyed by their reference ``structdata.<name>``."""
    return {f"structdata.{name}": spec for name, spec in fields.items() if spec.filterable}


def validate_filters(
    filters: list[dict[str, Any]], fields: Fields, path: str, *, error: type[EngineError] = EngineError
) -> None:
    """Validate shape-checked filters against the effective filterable fields."""
    available = filter_fields(fields)
    for index, clause in enumerate(filters):
        conditions = clause.get("any", [clause])
        for position, condition in enumerate(conditions):
            location = f"{path}/{index}" + (f"/any/{position}" if "any" in clause else "")
            spec = available.get(condition["field"])
            if spec is None:
                raise error("field is not filterable", path=location + "/field")
            operator = condition["operator"]
            if operator not in ("eq", "in") and spec.type not in RANGE_TYPES:
                raise error(f"operator {operator} is not valid for {spec.type}", path=location + "/operator")
            values = condition["value"] if operator == "in" else [condition["value"]]
            if not values or not all(_value_ok(spec.type, value) for value in values):
                raise error(f"value does not match field type {spec.type}", path=location + "/value")


def _comparable(kind: str, value: Any) -> Any:
    if kind == "datetime":
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


def _condition_matches(condition: dict[str, Any], structdata: dict[str, Any], fields: Fields) -> bool:
    name = condition["field"].removeprefix("structdata.")
    spec = fields[name]
    if name not in structdata or structdata[name] is None:
        return False
    stored = structdata[name]
    candidates = stored if spec.type == "string_array" else [stored]
    if not candidates:
        return False
    operator, wanted = condition["operator"], condition["value"]
    for item in candidates:
        left = _comparable(spec.type, item)
        if operator == "eq" and left == _comparable(spec.type, wanted):
            return True
        if operator == "in" and any(left == _comparable(spec.type, value) for value in wanted):
            return True
        if operator in ("gt", "gte", "lt", "lte"):
            right = _comparable(spec.type, wanted)
            if (
                (operator == "gt" and left > right)
                or (operator == "gte" and left >= right)
                or (operator == "lt" and left < right)
                or (operator == "lte" and left <= right)
            ):
                return True
    return False


def matches(filters: list[dict[str, Any]], structdata: dict[str, Any], fields: Fields) -> bool:
    """Evaluate validated filters against one candidate's structdata."""
    for clause in filters:
        if "any" in clause:
            if not any(_condition_matches(item, structdata, fields) for item in clause["any"]):
                return False
        elif not _condition_matches(clause, structdata, fields):
            return False
    return True
