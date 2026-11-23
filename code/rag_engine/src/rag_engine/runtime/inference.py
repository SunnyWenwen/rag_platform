"""Synchronous queries with per-System rate and concurrency limits (D-64).

Full slots reject immediately: per-System limits answer 429 RATE_LIMITED, the Runtime-wide
limit answers 503 RUNTIME_CAPACITY_EXHAUSTED. There is no waiting queue for queries.
"""

from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass
from typing import Any

from rag_engine.core.resources import EmbeddingProfile
from rag_engine.runtime.errors import ApiError
from rag_engine.runtime.observability import request_id_var
from rag_engine.runtime.settings import Settings
from rag_engine.runtime.snapshot import Snapshot


@dataclass
class _Bucket:
    tokens: float
    updated: float


class QueryService:
    def __init__(self, settings: Settings, profiles: dict[str, EmbeddingProfile]) -> None:
        self._settings = settings
        self._profiles = profiles
        self._buckets: dict[str, _Bucket] = {}
        self._active: dict[str, int] = {}
        self._idle: dict[str, asyncio.Event] = {}

    def active(self, system_id: str) -> int:
        return self._active.get(system_id, 0)

    def _take_token(self, system_id: str) -> None:
        rate = self._settings.inference_rate_limit_per_system_rps
        capacity = max(1.0, rate)
        now = time.monotonic()
        bucket = self._buckets.setdefault(system_id, _Bucket(capacity, now))
        bucket.tokens = min(capacity, bucket.tokens + (now - bucket.updated) * rate)
        bucket.updated = now
        if bucket.tokens < 1:
            wait = math.ceil((1 - bucket.tokens) / rate)
            raise ApiError(
                "RATE_LIMITED", "Query rate limit reached for this System.", headers={"Retry-After": str(max(1, wait))}
            )
        bucket.tokens -= 1

    def _enter(self, system_id: str) -> None:
        if self._active.get(system_id, 0) >= self._settings.inference_max_concurrency_per_system:
            raise ApiError("RATE_LIMITED", "Too many concurrent queries for this System.", headers={"Retry-After": "1"})
        if sum(self._active.values()) >= self._settings.inference_max_concurrency_total:
            raise ApiError(
                "RUNTIME_CAPACITY_EXHAUSTED", "The Runtime is at its query capacity.", headers={"Retry-After": "1"}
            )
        self._active[system_id] = self._active.get(system_id, 0) + 1
        self._idle.setdefault(system_id, asyncio.Event()).clear()

    def _leave(self, system_id: str) -> None:
        self._active[system_id] -= 1
        if self._active[system_id] == 0:
            self._idle[system_id].set()

    async def drain(self, system_id: str, timeout: float) -> bool:
        """Wait until accepted queries of the System finish. False on timeout."""
        if self.active(system_id) == 0:
            return True
        try:
            async with asyncio.timeout(timeout):
                await self._idle[system_id].wait()
        except TimeoutError:
            return False
        return True

    async def run(self, snapshot: Snapshot, request: dict[str, Any]) -> dict[str, Any]:
        self._take_token(snapshot.system_id)
        self._enter(snapshot.system_id)
        deadline = self._settings.inference_timeout_seconds
        try:
            async with asyncio.timeout(deadline):
                state = await snapshot.inference_graph.ainvoke(
                    {},
                    config={
                        "configurable": {
                            "request": request,
                            "request_id": request_id_var.get(),
                            "deadline": time.monotonic() + deadline,
                            "profiles": self._profiles,
                        }
                    },
                )
        except TimeoutError as error:
            raise ApiError("DEADLINE_EXCEEDED", "The query exceeded its deadline.") from error
        finally:
            self._leave(snapshot.system_id)
        uses_index = snapshot.compiled.inference.uses_platform_index
        return {
            "contexts": [state["final"]],
            "query_variants": state["query_variants"],
            "config_revision": snapshot.config_revision,
            "index_generation": snapshot.index_generation if uses_index else None,
        }
