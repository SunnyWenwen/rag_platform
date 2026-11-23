"""MCP query tool over real HTTP with the official MCP Python SDK client."""

from __future__ import annotations

import asyncio
import socket
import threading
import time
from collections.abc import Iterator

import httpx
import httpx2
import pytest
import uvicorn
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from conftest import INFERENCE, INGESTION, SYSTEM_ID, RuntimeClient, make_settings
from rag_engine.runtime.app import create_app


@pytest.fixture
def server_url() -> Iterator[str]:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    app = create_app(make_settings())
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        assert time.monotonic() < deadline, "server did not start"
        time.sleep(0.02)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=10)


async def test_mcp_search_tool(server_url: str) -> None:
    async with httpx.AsyncClient(base_url=server_url) as http:
        runtime = RuntimeClient(http, None)
        await runtime.initialize()
        accepted = await runtime.ingest(
            [
                {"document_id": "guide-1", "structdata": {"body": "定期清潔散熱孔。", "title": "保養", "price": 350}},
            ]
        )
        await runtime.wait_run(accepted.json()["run_id"], {"completed"})

        url = f"{server_url}/internal/systems/{SYSTEM_ID}/mcp"
        assert (await http.get(url)).status_code == 405
        unauthenticated = await http.post(url, json={"jsonrpc": "2.0", "id": 1, "method": "ping"}, auth=INGESTION)
        assert unauthenticated.status_code == 401

    async with httpx2.AsyncClient(auth=httpx2.BasicAuth(*INFERENCE)) as client:
        async with streamable_http_client(url, http_client=client) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert [tool.name for tool in tools.tools] == ["search"]
                assert tools.tools[0].input_schema["required"] == ["query"]
                result = await session.call_tool("search", {"query": "散熱孔怎麼清潔？"})
                assert not result.is_error
                structured = result.structured_content
                assert structured["query_variants"] == ["散熱孔怎麼清潔？"]
                assert structured["contexts"][0]["result_sets"][0]["key"] == "final"
                assert "document_id=guide-1" in result.content[0].text
                failed = await session.call_tool(
                    "search", {"query": "x", "filters": [{"field": "structdata.body", "operator": "eq", "value": "x"}]}
                )
                assert failed.is_error
                assert failed.content[0].text.startswith("REQUEST_VALIDATION_FAILED")
    await asyncio.sleep(0)
