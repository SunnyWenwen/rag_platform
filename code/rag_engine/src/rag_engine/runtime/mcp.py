"""Inference MCP endpoint (06_runtime_api_and_deployment.md#inference-mcp).

Uses the official MCP Python SDK in stateless Streamable HTTP mode with JSON responses, so
protocol-version negotiation follows the SDK. Our ASGI wrapper authenticates with the System's
Inference credentials and resolves the System snapshot before the SDK sees the request.
"""

from __future__ import annotations

import json
from typing import Any

import mcp_types as types
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import Receive, Scope, Send

from rag_engine import __version__
from rag_engine.contracts import errors as contract_errors
from rag_engine.contracts import load_json, schema_ref
from rag_engine.core.errors import EngineError
from rag_engine.engine.plan import CompiledSystem
from rag_engine.runtime.auth import require
from rag_engine.runtime.errors import ApiError
from rag_engine.runtime.inference import QueryService
from rag_engine.runtime.observability import request_id_var
from rag_engine.runtime.snapshot import Snapshot
from rag_engine.runtime.systems import SystemRegistry

DEFAULT_DESCRIPTION = "Search this retrieval System and return ranked source passages."


def _filters_schema() -> dict[str, Any]:
    """Inline the shared Filter schema so MCP clients need no external $ref resolution."""
    query_context = load_json("schemas/query_context.schema.json")
    return {"type": "array", "items": {"$ref": "#/$defs/filter"}, "$defs": query_context["$defs"]}


def tool_definition(compiled: CompiledSystem) -> types.Tool:
    plan = compiled.inference
    properties: dict[str, Any] = {"query": {"type": "string", "minLength": 1}, "filters": _filters_schema()}
    if plan.request_parameters:
        properties["parameters"] = {
            "type": "object",
            "properties": {name: {"type": spec.type} for name, spec in plan.request_parameters.items()},
            "required": [
                name for name, spec in plan.request_parameters.items() if spec.required and not spec.has_default
            ],
            "additionalProperties": False,
        }
    return types.Tool(
        name=plan.mcp.tool_name,
        description=plan.mcp.description or DEFAULT_DESCRIPTION,
        input_schema={"type": "object", "properties": properties, "required": ["query"], "additionalProperties": False},
        output_schema={
            "type": "object",
            "properties": {
                "contexts": {"type": "array"},
                "query_variants": {"type": "array", "items": {"type": "string"}},
                "config_revision": {"type": "string"},
                "index_generation": {"type": ["string", "null"]},
            },
            "required": ["contexts", "query_variants", "config_revision", "index_generation"],
        },
    )


def render_text(response: dict[str, Any], text_field: str) -> str:
    items = response["contexts"][0]["result_sets"][0]["items"]
    if not items:
        return "No results."
    lines = []
    for rank, item in enumerate(items, 1):
        data = item["data"]
        score = item.get("score")
        head = f"{rank}. score={score:.4g}" if isinstance(score, int | float) else f"{rank}."
        lines.append(f"{head} document_id={data['document_id']}")
        text = data.get("structdata", {}).get(text_field)
        if isinstance(text, str):
            lines.append("   " + text.replace("\n", " "))
    return "\n".join(lines)


def _error_result(code: str, message: str) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(type="text", text=f"{code}: {message}")], is_error=True)


class McpEndpoint:
    """ASGI app mounted at /internal/systems/{system_id}/mcp (DEV) or /mcp (standalone)."""

    def __init__(self, registry: SystemRegistry, queries: QueryService, standalone_system_id: str | None) -> None:
        self._registry = registry
        self._queries = queries
        self._standalone = standalone_system_id
        server: Server[Any] = Server(
            "rag-runtime", version=__version__, on_list_tools=self._list_tools, on_call_tool=self._call_tool
        )
        self.manager = StreamableHTTPSessionManager(app=server, json_response=True, stateless=True)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope, receive)
        if request.method != "POST":
            await Response(status_code=405, headers={"Allow": "POST"})(scope, receive, send)
            return
        try:
            system_id = request.path_params.get("system_id") or self._standalone
            system = self._registry.business(system_id or "")
            require(request, system.snapshot.compiled.values.credentials("inference"))
            snapshot = self._registry.gate(system, "inference")
        except ApiError as error:
            await JSONResponse(error.body(), status_code=error.status, headers=error.headers)(scope, receive, send)
            return
        scope.setdefault("state", {})["rag_snapshot"] = snapshot
        await self.manager.handle_request(scope, receive, send)

    @staticmethod
    def _snapshot(ctx: Any) -> Snapshot:
        snapshot: Snapshot = ctx.request.state.rag_snapshot
        request_id = getattr(ctx.request.state, "request_id", None)
        if request_id:
            request_id_var.set(request_id)
        return snapshot

    async def _list_tools(self, ctx: Any, params: Any) -> types.ListToolsResult:
        return types.ListToolsResult(tools=[tool_definition(self._snapshot(ctx).compiled)])

    async def _call_tool(self, ctx: Any, params: types.CallToolRequestParams) -> types.CallToolResult:
        snapshot = self._snapshot(ctx)
        plan = snapshot.compiled.inference
        if params.name != plan.mcp.tool_name:
            return _error_result("REQUEST_VALIDATION_FAILED", f"unknown tool {params.name}")
        arguments = dict(params.arguments or {})
        request: dict[str, Any] = {
            key: arguments[key] for key in ("query", "filters", "parameters") if key in arguments
        }
        for problem in contract_errors(schema_ref("inference_request.schema.json"), request):
            return _error_result("REQUEST_VALIDATION_FAILED", f"{problem.message} at {problem.path or '/'}")
        try:
            response = await self._queries.run(snapshot, request)
        except ApiError as error:
            return _error_result(error.code, error.message)
        except EngineError as error:
            mapped = ApiError.from_engine(error)
            return _error_result(mapped.code, mapped.message)
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=render_text(response, plan.mcp.text_field))],
            structured_content=json.loads(json.dumps(response)),
        )
