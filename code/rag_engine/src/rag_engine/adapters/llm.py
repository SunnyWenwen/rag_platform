"""LLM client for the company LLM service: OpenAI-compatible Chat Completions (06#llm-service-deployment).

Only transport lives here. What to ask and how to judge the answer belong to the component
that calls it (for example components/rewrite.py).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx

from rag_engine.core.errors import UpstreamError
from rag_engine.core.resources import ModelResource


@dataclass(frozen=True)
class ChatReply:
    content: str | None  # the message text; None when the model refused
    refusal: str | None  # the refusal text when the model declined
    finish_reason: str | None  # "length" means the answer was cut off


async def chat_json(
    client: httpx.AsyncClient,
    model: ModelResource,
    messages: list[dict[str, str]],
    schema_name: str,
    schema: dict[str, Any],
    timeout: float,
    module: str,
) -> ChatReply:
    """One Chat Completions call that asks for JSON matching ``schema`` (strict structured output).

    Service failures raise UpstreamError; ``retryable`` marks 429, 5xx, timeouts and lost connections.
    """
    if not model.endpoint:
        raise UpstreamError(f"model {model.model_id} has no endpoint", module=module)
    payload = {
        "model": model.request_model or model.model_id,
        "messages": messages,
        "temperature": model.temperature,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": schema_name, "strict": True, "schema": schema},
        },
    }
    headers = {}
    if model.api_key_env:
        headers["Authorization"] = f"Bearer {os.environ.get(model.api_key_env, '')}"
    url = model.endpoint.rstrip("/") + "/chat/completions"
    try:
        response = await client.post(url, json=payload, headers=headers, timeout=timeout)
    except httpx.TimeoutException as error:
        raise UpstreamError("LLM service timed out", code="DEADLINE_EXCEEDED", module=module, retryable=True) from error
    except httpx.HTTPError as error:
        raise UpstreamError(f"LLM service unreachable: {error}", module=module, retryable=True) from error
    if response.status_code != 200:
        raise UpstreamError(
            f"LLM service returned HTTP {response.status_code}",
            module=module,
            retryable=response.status_code in (429, 500, 502, 503, 504),
        )
    try:
        choice = response.json()["choices"][0]
        message = choice["message"]
        return ChatReply(message.get("content"), message.get("refusal"), choice.get("finish_reason"))
    except (ValueError, KeyError, IndexError, TypeError) as error:
        raise UpstreamError("LLM service returned an invalid Chat Completions body", module=module) from error
