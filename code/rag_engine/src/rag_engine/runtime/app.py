"""FastAPI application: Health, DEV management API, System business API and MCP.

Run exactly one process per Pod (``uvicorn ... --workers 1``): Ingestion occupancy, the queue
and Run records are held in this process's memory.
"""

from __future__ import annotations

import base64
import binascii
import contextlib
import json
import logging
import os
from collections.abc import AsyncIterator
from typing import Any

import httpx
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.routing import Route

from rag_engine.adapters.embedding import HashEmbedder, OpenAICompatibleEmbedder
from rag_engine.contracts import errors as contract_errors
from rag_engine.contracts import http_def, schema_ref
from rag_engine.core.errors import EngineError
from rag_engine.core.resources import RuntimeResources, fixture_resources
from rag_engine.engine.catalog import build_catalog
from rag_engine.engine.documents import check_ingestion_document
from rag_engine.engine.pipelines import EngineDeps
from rag_engine.engine.values import bind_request
from rag_engine.runtime.auth import require
from rag_engine.runtime.errors import ApiError, api_error_handler, engine_error_handler
from rag_engine.runtime.inference import QueryService
from rag_engine.runtime.ingestion import IngestionControl
from rag_engine.runtime.mcp import McpEndpoint
from rag_engine.runtime.observability import RequestIdMiddleware, configure_logging
from rag_engine.runtime.settings import Settings
from rag_engine.runtime.stores import StoreProvider
from rag_engine.runtime.systems import SystemRegistry

_log = logging.getLogger(__name__)
UUID_SCHEMA = schema_ref("runtime_identity.schema.json", "/$defs/uuid_v4")


# ---------------------------------------------------------------------------- request helpers


async def json_body(request: Request, settings: Settings) -> Any:
    length = request.headers.get("content-length")
    if length is not None and length.isdigit() and int(length) > settings.max_body_bytes:
        raise ApiError("BODY_TOO_LARGE", "The request body is too large.")
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
        raise ApiError("UNSUPPORTED_MEDIA_TYPE", "Expected application/json.")
    raw = await request.body()
    if len(raw) > settings.max_body_bytes:
        raise ApiError("BODY_TOO_LARGE", "The request body is too large.")
    try:
        return json.loads(raw)
    except (UnicodeDecodeError, ValueError) as error:
        raise ApiError("INVALID_JSON", "The request body is not valid JSON.") from error


def check_body(schema: dict[str, Any], body: Any) -> None:
    for error in contract_errors(schema, body):
        raise ApiError("REQUEST_VALIDATION_FAILED", error.message, path=error.path or None)


def check_system_id(system_id: str) -> None:
    if any(True for _ in contract_errors(UUID_SCHEMA, system_id)):
        raise ApiError("SYSTEM_NOT_FOUND", "The System ID is not a lowercase UUIDv4.")


def encode_cursor(system_id: str, after: str) -> str:
    raw = json.dumps({"s": system_id, "a": after}, ensure_ascii=False).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(system_id: str, cursor: str) -> str:
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        if payload["s"] != system_id or not isinstance(payload["a"], str):
            raise ValueError
        return str(payload["a"])
    except (binascii.Error, ValueError, KeyError, TypeError, UnicodeDecodeError) as error:
        raise ApiError("INVALID_CURSOR", "The cursor is invalid for this System.", path="/cursor") from error


# ---------------------------------------------------------------------------- application


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()  # type: ignore[call-arg]
    resources = RuntimeResources.from_file(settings.resources_file) if settings.resources_file else fixture_resources()
    catalog = build_catalog(settings.runtime_ref, resources)
    stores = StoreProvider(settings)
    http = httpx.AsyncClient()
    embedder = HashEmbedder() if settings.embedding_backend == "hash" else OpenAICompatibleEmbedder(http)
    deps = EngineDeps(embedder=embedder, http=http)
    ingestion = IngestionControl(settings)
    queries = QueryService(settings, resources.profiles)
    registry = SystemRegistry(settings, catalog, stores, deps, ingestion, queries)
    standalone_id: str | None = None
    if settings.mode == "standalone" and settings.config_file:
        with open(settings.config_file, encoding="utf-8") as handle:
            standalone_body = json.load(handle)
        standalone_id = standalone_body["system_id"]
    mcp = McpEndpoint(registry, queries, standalone_id)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(settings.log_level)
        ingestion.start()
        async with mcp.manager.run():
            if settings.mode == "standalone":
                await registry.load_standalone(standalone_body, dict(os.environ))
            app.state.ready = True
            try:
                yield
            finally:
                app.state.ready = False
                await ingestion.stop()
                await http.aclose()
                await stores.close()

    # The contract is the vendored OpenAPI (contracts/data/openapi), so FastAPI's generated one is off.
    app = FastAPI(
        title="Retrieval Runtime", version="0.1.0", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None
    )
    app.state.ready = False
    app.state.settings = settings
    app.state.registry = registry
    app.state.ingestion = ingestion
    app.state.queries = queries
    app.state.stores = stores
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(EngineError, engine_error_handler)
    app.add_middleware(RequestIdMiddleware)

    # ------------------------------------------------------------------ health (no auth)

    @app.get("/health/live")
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    async def ready() -> dict[str, str]:
        if not app.state.ready:
            raise ApiError("RUNTIME_NOT_READY", "The Runtime is starting.")
        if settings.mode == "standalone" and standalone_id:
            system = registry.systems.get(standalone_id)
            if system is None or system.index_ready is not True:
                raise ApiError("RUNTIME_NOT_READY", "The System index is not ready.")
        return {"status": "ok"}

    # ------------------------------------------------------------------ DEV management API

    management = APIRouter(prefix="/internal/v1")
    management_credentials = (
        (settings.management_username, settings.management_password.get_secret_value())
        if settings.management_username and settings.management_password
        else None
    )

    def manage(request: Request) -> None:
        require(request, management_credentials)

    @management.get("/catalog")
    async def get_catalog(request: Request) -> dict[str, Any]:
        manage(request)
        return catalog.response()

    @management.get("/systems")
    async def list_systems(request: Request) -> dict[str, Any]:
        manage(request)
        return registry.list_status()

    @management.post("/systems/{system_id}/config:validate")
    async def validate(system_id: str, request: Request) -> dict[str, Any]:
        manage(request)
        check_system_id(system_id)
        return await registry.validate(system_id, await json_body(request, settings))

    @management.post("/systems/{system_id}:detach", status_code=204)
    async def detach(system_id: str, request: Request) -> Response:
        manage(request)
        check_system_id(system_id)
        pipeline = request.query_params.get("pipeline")
        if pipeline not in (None, "ingestion", "inference"):
            raise ApiError("REQUEST_VALIDATION_FAILED", "pipeline must be ingestion or inference.", path="/pipeline")
        headers = request.headers
        key = headers.get("idempotency-key")
        expected = {
            "revision": headers.get("x-expected-config-revision"),
            "generation": headers.get("x-expected-index-generation"),
            "fingerprint": headers.get("x-expected-index-fingerprint"),
        }
        if not key or any(value is None for value in expected.values()):
            raise ApiError(
                "REQUEST_VALIDATION_FAILED", "Idempotency-Key and the three expected binding headers are required."
            )
        await registry.detach(system_id, pipeline, key, {k: v for k, v in expected.items() if v is not None})
        return Response(status_code=204)

    @management.put("/systems/{system_id}")
    async def apply(system_id: str, request: Request) -> dict[str, Any]:
        manage(request)
        check_system_id(system_id)
        key = request.headers.get("idempotency-key")
        if not key:
            raise ApiError("REQUEST_VALIDATION_FAILED", "Idempotency-Key is required.")
        return await registry.apply(system_id, await json_body(request, settings), key)

    @management.get("/systems/{system_id}")
    async def get_system(system_id: str, request: Request) -> dict[str, Any]:
        manage(request)
        check_system_id(system_id)
        headers = request.headers
        return await registry.observe(
            system_id,
            {
                "revision": headers.get("x-expected-config-revision"),
                "generation": headers.get("x-expected-index-generation"),
                "fingerprint": headers.get("x-expected-index-fingerprint"),
            },
        )

    @management.delete("/systems/{system_id}", status_code=204)
    async def delete(system_id: str, request: Request) -> Response:
        manage(request)
        check_system_id(system_id)
        headers = request.headers
        key = headers.get("idempotency-key")
        revision = headers.get("x-expected-config-revision")
        if not key or not revision:
            raise ApiError("REQUEST_VALIDATION_FAILED", "Idempotency-Key and X-Expected-Config-Revision are required.")
        await registry.delete(
            system_id,
            key,
            {
                "revision": revision,
                "generation": headers.get("x-expected-index-generation"),
                "fingerprint": headers.get("x-expected-index-fingerprint"),
            },
        )
        return Response(status_code=204)

    # ------------------------------------------------------------------ System business API

    business = APIRouter()

    def system_for(request: Request, pipeline: str) -> Any:
        system_id = request.path_params.get("system_id") or standalone_id or ""
        if settings.mode == "dev":
            check_system_id(system_id)
        system = registry.business(system_id)
        require(request, system.snapshot.compiled.values.credentials(pipeline))
        return registry.gate(system, pipeline)

    def prefix(request: Request) -> str:
        system_id = request.path_params.get("system_id")
        return f"/internal/systems/{system_id}/v1" if system_id else "/v1"

    @business.post("/ingestions", status_code=202)
    async def submit(request: Request) -> JSONResponse:
        snapshot = system_for(request, "ingestion")
        body = await json_body(request, settings)
        check_body(schema_ref("ingestion_request.schema.json"), body)
        documents = body["documents"]
        if len(documents) > settings.ingestion_max_documents:
            raise ApiError(
                "REQUEST_VALIDATION_FAILED",
                f"At most {settings.ingestion_max_documents} documents per request.",
                path="/documents",
            )
        seen: set[str] = set()
        plan = snapshot.compiled.ingestion
        for index, document in enumerate(documents):
            if document["document_id"] in seen:
                raise ApiError(
                    "REQUEST_VALIDATION_FAILED",
                    "Duplicate document_id in the batch.",
                    path=f"/documents/{index}/document_id",
                )
            seen.add(document["document_id"])
            check_ingestion_document(document, plan.import_fields, plan.import_source, f"/documents/{index}")
        parameters = bind_request(plan.request_parameters, body.get("parameters", {}))
        run = registry.ingestion.submit(snapshot, documents, parameters)
        accepted = {
            "run_id": run.run_id,
            "status": "queued",
            "config_revision": snapshot.config_revision,
            "documents": [{"document_id": item["document_id"], "status": "queued"} for item in documents],
        }
        return JSONResponse(
            accepted, status_code=202, headers={"Location": f"{prefix(request)}/ingestions/{run.run_id}"}
        )

    @business.get("/ingestions/{run_id}")
    async def run_status(run_id: str, request: Request) -> dict[str, Any]:
        snapshot = system_for(request, "ingestion")
        return registry.ingestion.run_status(snapshot.system_id, run_id)

    @business.post("/ingestions/{run_id}/cancel")
    async def cancel(run_id: str, request: Request) -> dict[str, Any]:
        snapshot = system_for(request, "ingestion")
        body = await json_body(request, settings)
        check_body(schema_ref("ingestion_cancel_request.schema.json"), body)
        return registry.ingestion.cancel(snapshot.system_id, run_id, body["document_ids"])

    @business.get("/documents/{document_id:path}/ingestion-status")
    async def document_status(document_id: str, request: Request) -> dict[str, Any]:
        snapshot = system_for(request, "ingestion")
        return registry.ingestion.document_status(snapshot.system_id, document_id)

    @business.get("/documents/{document_id:path}/exists")
    async def exists(document_id: str, request: Request) -> dict[str, Any]:
        snapshot = system_for(request, "ingestion")
        found = await snapshot.store.document_exists(snapshot.index_name, document_id)
        return {"document_id": document_id, "exists": found}

    @business.get("/documents")
    async def list_documents(request: Request) -> dict[str, Any]:
        snapshot = system_for(request, "ingestion")
        query: dict[str, Any] = dict(request.query_params)
        if "limit" in query:
            try:
                query["limit"] = int(query["limit"])
            except ValueError as error:
                raise ApiError("REQUEST_VALIDATION_FAILED", "limit must be an integer.", path="/limit") from error
        check_body(http_def("document_list_query"), query)
        after = decode_cursor(snapshot.system_id, query["cursor"]) if "cursor" in query else None
        page, next_after = await snapshot.store.list_documents(snapshot.index_name, after, query.get("limit", 100))
        return {
            "documents": [{"document_id": doc_id, "source_revisions": revisions} for doc_id, revisions in page],
            "next_cursor": encode_cursor(snapshot.system_id, next_after) if next_after else None,
        }

    @business.post("/documents/{document_id:path}:retire")
    async def retire(document_id: str, request: Request) -> dict[str, Any]:
        snapshot = system_for(request, "ingestion")
        with registry.ingestion.retire_guard(snapshot.system_id, document_id):
            deleted = await snapshot.store.delete_document(snapshot.index_name, document_id)
        return {"document_id": document_id, "result": "deleted" if deleted else "not_found"}

    @business.post("/queries")
    async def query(request: Request) -> JSONResponse:
        snapshot = system_for(request, "inference")
        body = await json_body(request, settings)
        check_body(schema_ref("inference_request.schema.json"), body)
        result = await registry.queries.run(snapshot, body)
        headers = {"X-Config-Revision": result["config_revision"]}
        if result["index_generation"] is not None:
            headers["X-Index-Generation"] = result["index_generation"]
        return JSONResponse(result, headers=headers)

    if settings.mode == "dev":
        app.include_router(management)
        app.include_router(business, prefix="/internal/systems/{system_id}/v1")
        app.router.routes.append(
            Route("/internal/systems/{system_id}/mcp", endpoint=mcp, methods=["GET", "POST", "DELETE"])
        )
    else:
        app.include_router(business, prefix="/v1")
        app.router.routes.append(Route("/mcp", endpoint=mcp, methods=["GET", "POST", "DELETE"]))
    return app
