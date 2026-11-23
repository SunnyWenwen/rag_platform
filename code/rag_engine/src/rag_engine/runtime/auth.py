"""HTTP Basic authentication per route (06_runtime_api_and_deployment.md#runtime-basic-authentication).

* /internal/v1/**: Runtime management credentials (only the Builder holds them).
* /ingestions, /documents: the System's INGESTION_API_USERNAME / PASSWORD.
* /queries and MCP: the System's INFERENCE_API_USERNAME / PASSWORD.
* /health/*: no authentication.
"""

from __future__ import annotations

import base64
import binascii
from hmac import compare_digest

from fastapi import Request

from rag_engine.runtime.errors import CHALLENGE, ApiError


def _unauthenticated() -> ApiError:
    return ApiError("UNAUTHENTICATED", "Credentials are missing or invalid.", headers={"WWW-Authenticate": CHALLENGE})


def basic_credentials(request: Request) -> tuple[str, str]:
    header = request.headers.get("authorization", "")
    scheme, _, encoded = header.partition(" ")
    if scheme.lower() != "basic" or not encoded:
        raise _unauthenticated()
    try:
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError) as error:
        raise _unauthenticated() from error
    username, separator, password = decoded.partition(":")
    if not separator:
        raise _unauthenticated()
    return username, password


def require(request: Request, expected: tuple[str, str] | None) -> None:
    """Compare in constant time; a missing expected pair rejects every caller."""
    username, password = basic_credentials(request)
    if expected is None:
        raise _unauthenticated()
    user_ok = compare_digest(username.encode(), expected[0].encode())
    password_ok = compare_digest(password.encode(), expected[1].encode())
    if not (user_ok and password_ok):
        raise _unauthenticated()
