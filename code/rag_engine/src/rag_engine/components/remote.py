"""User Remote API adapter (wire contract v1, 03_engine_and_components.md#remote-api)."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx

from rag_engine.contracts import errors as contract_errors
from rag_engine.contracts import schema_ref
from rag_engine.core.errors import EngineError, UpstreamError

_log = logging.getLogger(__name__)
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class RemoteCall:
    """A Remote node with connection values already resolved from Variables and Secrets."""

    module: str
    through: str
    contract_version: str
    url: str
    timeout_seconds: float
    headers: dict[str, str] = field(default_factory=dict)
    bearer_token: str | None = None


async def call_remote(
    client: httpx.AsyncClient,
    call: RemoteCall,
    payload_input: Any,
    parameters: dict[str, Any],
    *,
    upstream_request_id: str | None,
    deadline: float,
) -> list[Any]:
    """POST one logical Remote call. Retries keep the same ``X-Request-Id``.

    ``deadline`` is an absolute ``time.monotonic()`` value; retries stop when it is near.
    Returns the validated ``output`` array of the success envelope.
    """
    request_id = str(uuid.uuid4())
    body = {
        "contract_version": call.contract_version,
        "segment": {"module": call.module, "through": call.through},
        "input": payload_input,
        "parameters": parameters,
    }
    headers = {**call.headers, "X-Request-Id": request_id}
    if call.bearer_token:
        headers["Authorization"] = f"Bearer {call.bearer_token}"
    _log.info(
        "remote call",
        extra={
            "remote_request_id": request_id,
            "upstream_request_id": upstream_request_id,
            "segment": f"{call.module}->{call.through}",
        },
    )
    last_error: EngineError | None = None
    for attempt in range(MAX_ATTEMPTS):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            response = await client.post(
                call.url, json=body, headers=headers, timeout=min(call.timeout_seconds, remaining)
            )
        except httpx.TimeoutException:
            last_error = UpstreamError(
                "Remote API timed out", code="DEADLINE_EXCEEDED", module=call.module, retryable=True
            )
        except httpx.HTTPError as error:
            last_error = UpstreamError(f"Remote API unreachable: {error}", module=call.module, retryable=True)
        else:
            outcome = _interpret(response, call.module)
            if isinstance(outcome, list):
                return outcome
            last_error = outcome
        if not last_error.retryable or attempt == MAX_ATTEMPTS - 1:
            break
        await asyncio.sleep(min(0.5 * 2**attempt, max(0.0, deadline - time.monotonic())))
    raise last_error or UpstreamError("Remote API deadline exceeded", code="DEADLINE_EXCEEDED", module=call.module)


def _interpret(response: httpx.Response, module: str) -> list[Any] | EngineError:
    try:
        body = response.json()
    except ValueError:
        body = None
    if 200 <= response.status_code < 300:
        if body is None or any(
            True for _ in contract_errors(schema_ref("remote_api.schema.json", "/$defs/success"), body)
        ):
            return UpstreamError("Remote API returned an invalid success envelope", module=module)
        output: list[Any] = body["output"]
        return output
    failure_ok = body is not None and not any(
        True for _ in contract_errors(schema_ref("remote_api.schema.json", "/$defs/failure"), body)
    )
    if failure_ok:
        error = body["error"]
        return UpstreamError(
            f"Remote API error {error['code']}: {error['message']}", module=module, retryable=bool(error["retryable"])
        )
    return UpstreamError(
        f"Remote API returned HTTP {response.status_code}",
        module=module,
        retryable=response.status_code in RETRYABLE_STATUS,
    )
