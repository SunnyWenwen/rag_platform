"""Idempotency-Key replay for DEV management requests (06#system-lifecycle-api).

A key is remembered per ``(system_id, operation, key)`` together with the request hash
and the response. The same key with the same request returns the stored response; the
same key with a different request is ``IDEMPOTENCY_CONFLICT``. Entries expire after
``idempotency_retention_seconds``. State lives in this Pod only.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from rag_engine.runtime.errors import ApiError


@dataclass(frozen=True)
class Replay:
    request_hash: str
    status: int
    body: dict[str, Any] | None
    expires: float


class IdempotencyStore:
    def __init__(self, retention_seconds: int) -> None:
        self.retention_seconds = retention_seconds
        self._entries: dict[tuple[str, str, str], Replay] = {}

    def find(self, system_id: str, operation: str, key: str, request_hash: str) -> Replay | None:
        """Return the stored response for this key, or None when the key is new."""
        now = time.monotonic()
        expired = [entry_key for entry_key, entry in self._entries.items() if entry.expires < now]
        for entry_key in expired:
            del self._entries[entry_key]

        replay = self._entries.get((system_id, operation, key))
        if replay is not None and replay.request_hash != request_hash:
            raise ApiError("IDEMPOTENCY_CONFLICT", "The Idempotency-Key was used for a different request.")
        return replay

    def remember(
        self, system_id: str, operation: str, key: str, request_hash: str, status: int, body: dict[str, Any] | None
    ) -> None:
        expires = time.monotonic() + self.retention_seconds
        self._entries[(system_id, operation, key)] = Replay(request_hash, status, body, expires)
