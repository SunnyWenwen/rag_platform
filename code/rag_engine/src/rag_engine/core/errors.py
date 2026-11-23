"""Engine errors. The Runtime maps ``code`` to the HTTP status of the Runtime API contract."""

from __future__ import annotations


class EngineError(Exception):
    """A located failure. ``module`` is the Config module key, ``path`` a JSON Pointer."""

    code = "INTERNAL_ERROR"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        module: str | None = None,
        path: str | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        self.module = module
        self.path = path
        self.retryable = retryable

    def __str__(self) -> str:
        location = f" at {self.path}" if self.path else ""
        return f"{self.code}: {self.message}{location}"


class ConfigInvalid(EngineError):
    """The System Config failed shape or cross-node validation (HTTP 422)."""

    code = "CONFIG_VALIDATION_FAILED"


class RequestInvalid(EngineError):
    """A business request failed validation against the active Config (HTTP 422)."""

    code = "REQUEST_VALIDATION_FAILED"


class UpstreamError(EngineError):
    """A dependency such as a Remote API, model service or Elasticsearch failed (HTTP 502)."""

    code = "UPSTREAM_ERROR"


class DocumentFailed(EngineError):
    """A single Ingestion document failed after acceptance; recorded on the Run."""

    code = "DOCUMENT_FAILED"
