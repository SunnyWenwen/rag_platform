"""HTTP error envelope (06_runtime_api_and_deployment.md#runtime-http-errors)."""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from rag_engine.core.errors import EngineError
from rag_engine.runtime.observability import request_id_var

CHALLENGE = 'Basic realm="retrieval-runtime"'

# Engine error codes that are not 500. Anything else from the Engine is an internal error.
STATUS_BY_CODE: dict[str, int] = {
    "INVALID_JSON": 400,
    "UNAUTHENTICATED": 401,
    "FORBIDDEN": 403,
    "SYSTEM_NOT_FOUND": 404,
    "INGESTION_RUN_NOT_FOUND": 404,
    "STALE_CATALOG": 409,
    "STALE_CONTEXT": 409,
    "REVISION_CONFLICT": 409,
    "REBUILD_CONFIRMATION_REQUIRED": 409,
    "SYSTEM_STATE_CONFLICT": 409,
    "IDEMPOTENCY_CONFLICT": 409,
    "SYSTEM_BUSY": 409,
    "DOCUMENT_BUSY": 409,
    "INDEX_OWNERSHIP_UNVERIFIED": 409,
    "INDEX_CONFLICT": 409,
    "PIPELINE_NOT_ENABLED": 409,
    "PIPELINE_OPERATION_UNSUPPORTED": 409,
    "BODY_TOO_LARGE": 413,
    "UNSUPPORTED_MEDIA_TYPE": 415,
    "REQUEST_VALIDATION_FAILED": 422,
    "CONFIG_VALIDATION_FAILED": 422,
    "INVALID_CURSOR": 422,
    "RATE_LIMITED": 429,
    "INTERNAL_ERROR": 500,
    "OPERATION_UNSUPPORTED": 501,
    "UPSTREAM_ERROR": 502,
    "RUNTIME_NOT_READY": 503,
    "RUNTIME_CAPACITY_EXHAUSTED": 503,
    "INDEX_NOT_READY": 503,
    "PIPELINE_NOT_READY": 503,
    "SYSTEM_STATE_UNKNOWN": 503,
    "DEADLINE_EXCEEDED": 504,
}


class ApiError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        module: str | None = None,
        path: str | None = None,
        run_id: str | None = None,
        extra: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.module = module
        self.path = path
        self.run_id = run_id
        self.extra = extra or {}
        self.headers = headers or {}
        self.status = status or STATUS_BY_CODE.get(code, 500)

    @classmethod
    def from_engine(cls, error: EngineError) -> ApiError:
        status = STATUS_BY_CODE.get(error.code)
        if status is None:
            # Document-level codes (for example CHUNK_SOURCE_INVALID) surface as upstream failures.
            return cls("UPSTREAM_ERROR", error.message, module=error.module, path=error.path)
        return cls(error.code, error.message, module=error.module, path=error.path)

    def body(self) -> dict[str, Any]:
        error: dict[str, Any] = {"code": self.code, "message": self.message, "module": self.module}
        if self.path:
            error["path"] = self.path
        if self.run_id:
            error["run_id"] = self.run_id
        error.update(self.extra)
        request_id = request_id_var.get()
        if request_id:
            error["request_id"] = request_id
        return {"error": error}


async def api_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApiError)
    return JSONResponse(exc.body(), status_code=exc.status, headers=exc.headers)


async def engine_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, EngineError)
    error = ApiError.from_engine(exc)
    return JSONResponse(error.body(), status_code=error.status)
