"""Request tracing (X-Request-Id) and JSON logs carrying request_id, system_id and run_id."""

from __future__ import annotations

import json
import logging
import re
import sys
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
system_id_var: ContextVar[str | None] = ContextVar("system_id", default=None)
run_id_var: ContextVar[str | None] = ContextVar("run_id", default=None)

_REDACTED_KEYS = ("authorization", "password", "token", "secret")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, var in (("request_id", request_id_var), ("system_id", system_id_var), ("run_id", run_id_var)):
            value = var.get()
            if value:
                entry[key] = value
        for key, value in record.__dict__.items():
            if key in ("remote_request_id", "upstream_request_id", "segment", "document_id", "code", "status"):
                entry[key] = value
            if any(marker in key.lower() for marker in _REDACTED_KEYS):
                entry[key] = "***"
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)


def effective_request_id(header: str | None) -> str:
    """Accept a caller ID that matches the contract, otherwise assign a UUIDv4."""
    if header and REQUEST_ID_PATTERN.match(header):
        return header
    return str(uuid.uuid4())
