"""Loaded Systems and the DEV management lifecycle (06_runtime_api_and_deployment.md#system-lifecycle-api).

The Builder is authoritative for the published revision and the index binding. This module
checks the Builder's expectations against the local snapshot and the physical index, then
applies one operation per System at a time.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from rag_engine.adapters.index_store import (
    IndexAlreadyExists,
    IndexDefinition,
    IndexInfo,
    IndexStateUnknown,
    IndexStore,
)
from rag_engine.contracts import errors as contract_errors
from rag_engine.contracts import http_def
from rag_engine.core.canonical import sha256_hex
from rag_engine.core.errors import ConfigInvalid
from rag_engine.engine.catalog import Catalog
from rag_engine.engine.compiler import CompiledSystem, compile_system
from rag_engine.engine.index_writer import IndexWriter
from rag_engine.engine.pipelines import EngineDeps, build_inference_graph, build_ingestion_graph
from rag_engine.runtime.errors import ApiError
from rag_engine.runtime.inference import QueryService
from rag_engine.runtime.ingestion import IngestionControl
from rag_engine.runtime.settings import Settings
from rag_engine.runtime.snapshot import Snapshot, index_name
from rag_engine.runtime.stores import StoreProvider

_log = logging.getLogger(__name__)
PIPELINES = ("ingestion", "inference")
FINGERPRINT_VERSION = 1

# index_impact codes that block an apply, mapped to the HTTP error of the PUT.
_BLOCKED_ERRORS = {
    "PIPELINE_OPERATION_UNSUPPORTED": "PIPELINE_OPERATION_UNSUPPORTED",
    "INDEX_OWNERSHIP_UNVERIFIED": "INDEX_OWNERSHIP_UNVERIFIED",
    "INDEX_CHECK_UNAVAILABLE": "SYSTEM_STATE_UNKNOWN",
    "SYSTEM_STATE_CONFLICT": "SYSTEM_STATE_CONFLICT",
    "PUBLISHED_INDEX_MISSING": "INDEX_CONFLICT",
    "PUBLISHED_INDEX_PRESENT": "INDEX_CONFLICT",
    "INDEX_FINGERPRINT_MISMATCH": "INDEX_CONFLICT",
}


@dataclass
class PipelineState:
    loaded: bool = False
    ready: bool = False


@dataclass
class LoadedSystem:
    snapshot: Snapshot
    pipelines: dict[str, PipelineState] = field(default_factory=lambda: {p: PipelineState() for p in PIPELINES})
    index_ready: bool | None = True
    created_by_operation_id: str | None = None

    @property
    def loaded(self) -> bool:
        return any(state.loaded for state in self.pipelines.values())


@dataclass(frozen=True)
class _Replay:
    request_hash: str
    status: int
    body: dict[str, Any] | None
    expires: float


def _impact(action: str, code: str, message: str, fingerprint: str | None = None) -> dict[str, Any]:
    impact: dict[str, Any] = {"action": action, "code": code, "message": message}
    if fingerprint is not None:
        impact["index_fingerprint"] = fingerprint
    return impact


def mapping_compatible(expected: Any, actual: Any) -> bool:
    """Every expected mapping key must be present with the same value (Elasticsearch may add defaults)."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        return all(
            key in actual and mapping_compatible(value, actual[key])
            for key, value in expected.items()
            if not (key in ("dynamic_templates", "runtime") and value in ([], {}))
        )
    return bool(expected == actual)


class SystemRegistry:
    def __init__(
        self,
        settings: Settings,
        catalog: Catalog,
        stores: StoreProvider,
        deps: EngineDeps,
        ingestion: IngestionControl,
        queries: QueryService,
    ) -> None:
        self.settings = settings
        self.catalog = catalog
        self.stores = stores
        self.deps = deps
        self.ingestion = ingestion
        self.queries = queries
        self.systems: dict[str, LoadedSystem] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._replays: dict[tuple[str, str, str], _Replay] = {}

    # ------------------------------------------------------------------ status

    def _lock(self, system_id: str) -> asyncio.Lock:
        return self._locks.setdefault(system_id, asyncio.Lock())

    def status(self, system: LoadedSystem) -> dict[str, Any]:
        snapshot = system.snapshot
        uses_index = snapshot.compiled.inference.uses_platform_index
        generation = snapshot.index_generation if (system.index_ready is not False or not system.loaded) else None
        pipelines = {}
        for name, state in system.pipelines.items():
            if state.loaded:
                pipelines[name] = {
                    "loaded": True,
                    "ready": state.ready,
                    "config_revision": snapshot.config_revision,
                    "index_generation": generation,
                }
            else:
                pipelines[name] = {"loaded": False, "ready": False, "config_revision": None, "index_generation": None}
        ingestion, inference = system.pipelines["ingestion"], system.pipelines["inference"]
        body: dict[str, Any] = {
            "system_id": snapshot.system_id,
            "active_config_revision": snapshot.config_revision,
            "loaded": system.loaded,
            "busy": self._lock(snapshot.system_id).locked() or self.ingestion.has_active_work(snapshot.system_id),
            "index_ready": system.index_ready,
            "index_generation": generation,
            "can_ingest": ingestion.loaded and ingestion.ready and system.index_ready is True,
            "can_query": inference.loaded and inference.ready and (system.index_ready is True or not uses_index),
            "pipelines": pipelines,
        }
        if system.created_by_operation_id:
            body["created_by_operation_id"] = system.created_by_operation_id
        return body

    def list_status(self) -> dict[str, Any]:
        return {"systems": [self.status(item) for item in self.systems.values() if item.loaded]}

    async def observe(self, system_id: str, headers: dict[str, str | None]) -> dict[str, Any]:
        local = self.systems.get(system_id)
        provided = {key: value for key, value in headers.items() if value is not None}
        if not provided:
            if local is None:
                raise ApiError("SYSTEM_NOT_FOUND", "The System is not loaded in this Runtime.")
            return self.status(local)
        if len(provided) != 3:
            raise ApiError("REQUEST_VALIDATION_FAILED", "Send all three expected binding headers together.")
        revision = provided["revision"]
        generation = provided["generation"]
        fingerprint = provided["fingerprint"]
        store = local.snapshot.store if local else self.stores.default()
        info = await self._owned(store, system_id, generation, fingerprint)
        if local is not None:
            if local.snapshot.index_generation == generation and info is None:
                local.index_ready = False
            return self.status(local)
        if info is None:
            raise ApiError("SYSTEM_NOT_FOUND", "No loaded System and no index for the expected generation.")
        body: dict[str, Any] = {
            "system_id": system_id,
            "active_config_revision": revision,
            "loaded": False,
            "busy": False,
            "index_ready": True,
            "index_generation": generation,
            "can_ingest": False,
            "can_query": False,
            "pipelines": {
                name: {"loaded": False, "ready": False, "config_revision": None, "index_generation": None}
                for name in PIPELINES
            },
        }
        if info.meta.get("created_by_operation_id"):
            body["created_by_operation_id"] = info.meta["created_by_operation_id"]
        return body

    # ------------------------------------------------------------------ business gate

    def business(self, system_id: str) -> LoadedSystem:
        system = self.systems.get(system_id)
        if system is None:
            raise ApiError("SYSTEM_NOT_FOUND", "The System is not loaded in this Runtime.")
        return system

    @staticmethod
    def gate(system: LoadedSystem, pipeline: str) -> Snapshot:
        state = system.pipelines[pipeline]
        if not state.loaded:
            raise ApiError(
                "PIPELINE_NOT_ENABLED", f"The {pipeline} pipeline is not loaded for this System.", module=None
            )
        if not state.ready:
            raise ApiError("PIPELINE_NOT_READY", f"The {pipeline} pipeline is switching versions.")
        uses_index = pipeline == "ingestion" or system.snapshot.compiled.inference.uses_platform_index
        if uses_index and system.index_ready is not True:
            raise ApiError("INDEX_NOT_READY", "The System index is not ready.")
        return system.snapshot

    # ------------------------------------------------------------------ helpers

    def _expected_meta(self, system_id: str, fingerprint: str, operation_id: str | None) -> dict[str, Any]:
        meta: dict[str, Any] = {
            "env": self.settings.env,
            "system_id": system_id,
            "index_fingerprint": fingerprint,
            "index_fingerprint_version": FINGERPRINT_VERSION,
        }
        if operation_id:
            meta["created_by_operation_id"] = operation_id
        return meta

    async def _owned(
        self, store: IndexStore, system_id: str, generation: str, fingerprint: str | None
    ) -> IndexInfo | None:
        """Read the physical index for a generation and verify ``_meta`` ownership."""
        try:
            info = await store.get_index(index_name(self.settings.env, system_id, generation))
        except IndexStateUnknown as error:
            raise ApiError("SYSTEM_STATE_UNKNOWN", f"Cannot read the index: {error.message}") from error
        if info is None:
            return None
        meta = info.meta
        if (
            meta.get("env") != self.settings.env
            or meta.get("system_id") != system_id
            or meta.get("index_fingerprint_version") != FINGERPRINT_VERSION
            or (fingerprint is not None and meta.get("index_fingerprint") != fingerprint)
        ):
            raise ApiError("INDEX_OWNERSHIP_UNVERIFIED", "The index ownership could not be verified.")
        return info

    def _compile(self, body: dict[str, Any]) -> CompiledSystem:
        if body["runtime_ref"] != self.catalog.runtime_ref or body["catalog_revision"] != self.catalog.catalog_revision:
            raise ApiError("STALE_CATALOG", "Reload the Catalog: runtime_ref or catalog_revision does not match.")
        try:
            return compile_system(body["config"], self.catalog)
        except ConfigInvalid as error:
            raise ApiError("CONFIG_VALIDATION_FAILED", error.message, module=error.module, path=error.path) from error

    def _context_revision(self, system_id: str, compiled: CompiledSystem) -> str:
        local = self.systems.get(system_id)
        state = {
            "catalog": self.catalog.catalog_revision,
            "config": sha256_hex(compiled.config),
            "active": local.snapshot.config_revision if local and local.loaded else None,
            "generation": local.snapshot.index_generation if local else None,
        }
        return "ctx-" + sha256_hex(state)[:16]

    async def _index_impact(self, system_id: str, compiled: CompiledSystem, body: dict[str, Any]) -> dict[str, Any]:
        operation = body.get("operation")
        pipeline = body.get("pipeline")
        fingerprint = compiled.fingerprint
        if operation is None:
            return _impact("none", "CONFIG_VALID", "Config 驗證通過。")
        if pipeline == "inference" and operation in ("initialize", "update", "recover_index"):
            return _impact("blocked", "PIPELINE_OPERATION_UNSUPPORTED", "Inference 請使用 reload。")
        local = self.systems.get(system_id)
        expected_generation = body["expected_index_generation"]
        expected_fingerprint = body["expected_index_fingerprint"]
        store = self.stores.for_connection(compiled.index.connection)
        if operation == "initialize":
            if (
                body["expected_active_revision"] is not None
                or expected_generation is not None
                or (local and local.loaded)
            ):
                return _impact("blocked", "SYSTEM_STATE_CONFLICT", "System 已有發布版本或已載入。")
            return _impact("create", "INDEX_MISSING", "建立空索引。", fingerprint)
        if operation == "recover_index":
            recovery = body["recovery_from"]
            try:
                old = await self._owned(store, system_id, recovery["index_generation"], None)
            except ApiError as error:
                return self._blocked_from(error)
            if old is not None:
                return _impact("blocked", "PUBLISHED_INDEX_PRESENT", "原索引仍存在，請改用 reload。")
            if expected_fingerprint is not None and fingerprint != expected_fingerprint:
                return _impact("blocked", "INDEX_FINGERPRINT_MISMATCH", "Config 與已發布版本的索引不符。")
            return _impact(
                "recover",
                "PUBLISHED_INDEX_MISSING",
                "索引已遺失。請確認建立同版本的新空索引，再重新匯入。",
                fingerprint,
            )
        if expected_generation is None:
            return _impact("blocked", "SYSTEM_STATE_CONFLICT", "沒有可接回的已發布索引。")
        try:
            info = await self._owned(store, system_id, expected_generation, expected_fingerprint)
        except ApiError as error:
            return self._blocked_from(error)
        if info is None:
            return _impact("blocked", "PUBLISHED_INDEX_MISSING", "已發布的索引不存在，請確認後改用 recover_index。")
        if not mapping_compatible(compiled.index.mappings["properties"], info.mappings.get("properties", {})):
            return _impact("blocked", "INDEX_OWNERSHIP_UNVERIFIED", "實際 mapping 與已發布設定不符。")
        if operation == "reload":
            if fingerprint != expected_fingerprint:
                return _impact("blocked", "INDEX_FINGERPRINT_MISMATCH", "Config 與已發布版本的索引不符。")
            return _impact("reuse", "INDEX_COMPATIBLE", "接回已發布的索引。", fingerprint)
        if fingerprint == expected_fingerprint:
            return _impact("reuse", "INDEX_COMPATIBLE", "沿用索引。", fingerprint)
        return _impact(
            "rebuild_required", "INDEX_FINGERPRINT_CHANGED", "索引相關設定已變更，發布時停查並重建索引。", fingerprint
        )

    @staticmethod
    def _blocked_from(error: ApiError) -> dict[str, Any]:
        if error.code == "SYSTEM_STATE_UNKNOWN":
            return _impact("blocked", "INDEX_CHECK_UNAVAILABLE", "目前無法確認 ES 索引是否存在。")
        return _impact("blocked", "INDEX_OWNERSHIP_UNVERIFIED", "目標索引的歸屬無法確認。")

    def _replay(self, system_id: str, kind: str, key: str, request_hash: str) -> _Replay | None:
        now = time.monotonic()
        for stale in [k for k, v in self._replays.items() if v.expires < now]:
            del self._replays[stale]
        replay = self._replays.get((system_id, kind, key))
        if replay is not None and replay.request_hash != request_hash:
            raise ApiError("IDEMPOTENCY_CONFLICT", "The Idempotency-Key was used for a different request.")
        return replay

    def _remember(
        self, system_id: str, kind: str, key: str, request_hash: str, status: int, body: dict[str, Any] | None
    ) -> None:
        expires = time.monotonic() + self.settings.idempotency_retention_seconds
        self._replays[(system_id, kind, key)] = _Replay(request_hash, status, body, expires)

    def _build(self, system_id: str, revision: str, compiled: CompiledSystem, generation: str) -> Snapshot:
        store = self.stores.for_connection(compiled.index.connection)
        name = index_name(self.settings.env, system_id, generation)
        writer = IndexWriter(store, name, compiled.index.vectors, self.settings.es_bulk_timeout_seconds)
        return Snapshot(
            system_id=system_id,
            config_revision=revision,
            compiled=compiled,
            index_name=name,
            index_generation=generation,
            store=store,
            writer=writer,
            ingestion_graph=build_ingestion_graph(compiled, self.deps),
            inference_graph=build_inference_graph(compiled, self.deps, store, name),
        )

    async def _create_index(self, snapshot: Snapshot, operation_id: str) -> None:
        compiled = snapshot.compiled
        settings: dict[str, Any] = {
            "number_of_shards": self.settings.es_number_of_shards,
            "number_of_replicas": self.settings.es_number_of_replicas,
        }
        if compiled.index.analysis:
            settings["analysis"] = compiled.index.analysis
        meta = self._expected_meta(snapshot.system_id, compiled.fingerprint, operation_id)
        definition = IndexDefinition(snapshot.index_name, {**compiled.index.mappings, "_meta": meta}, settings)
        try:
            await snapshot.store.create_index(definition)
        except IndexAlreadyExists:
            existing = await snapshot.store.get_index(snapshot.index_name)
            if existing is None or existing.meta.get("created_by_operation_id") != operation_id:
                raise ApiError("INDEX_CONFLICT", "The target index already exists.") from None
        except IndexStateUnknown as error:
            raise ApiError("SYSTEM_STATE_UNKNOWN", error.message) from error

    def _pipelines(self, body: dict[str, Any]) -> tuple[str, ...]:
        pipeline = body.get("pipeline")
        return (pipeline,) if pipeline else PIPELINES

    async def _close_and_drain(self, system: LoadedSystem) -> None:
        for state in system.pipelines.values():
            state.ready = False
        if not await self.queries.drain(system.snapshot.system_id, self.settings.inference_timeout_seconds):
            for state in system.pipelines.values():
                state.ready = state.loaded
            raise ApiError("DEADLINE_EXCEEDED", "Accepted queries did not finish within the query deadline.")

    # ------------------------------------------------------------------ operations

    @staticmethod
    def _check_envelope(definition: str, body: Any) -> None:
        """Envelope errors are request errors; errors inside ``config`` are reported by the compiler."""
        for error in contract_errors(http_def(definition), body):
            if error.path == "/config" or error.path.startswith("/config/"):
                continue
            raise ApiError("REQUEST_VALIDATION_FAILED", error.message, path=error.path or None)

    async def validate(self, system_id: str, body: dict[str, Any]) -> dict[str, Any]:
        self._check_envelope("validate_request", body)
        compiled = self._compile(body)
        impact = await self._index_impact(system_id, compiled, body)
        local = self.systems.get(system_id)
        pipelines = self._pipelines(body)
        loaded = bool(local) and any(local.pipelines[name].loaded for name in pipelines)  # type: ignore[union-attr]
        result: dict[str, Any] = {
            "runtime_ref": self.catalog.runtime_ref,
            "catalog_revision": self.catalog.catalog_revision,
            "draft_revision": body["draft_revision"],
            "context_revision": self._context_revision(system_id, compiled),
            "active_config_revision": local.snapshot.config_revision if local and local.loaded else None,
            "loaded": loaded,
            "index_impact": impact,
        }
        if "pipeline" in body:
            result["pipeline"] = body["pipeline"]
        return result

    async def apply(self, system_id: str, body: dict[str, Any], key: str) -> dict[str, Any]:
        request_hash = sha256_hex(body)
        replay = self._replay(system_id, "apply", key, request_hash)
        if replay is not None and replay.body is not None:
            return replay.body
        lock = self._lock(system_id)
        if lock.locked():
            raise ApiError("SYSTEM_BUSY", "Another management operation is running for this System.")
        async with lock:
            system = await self._apply(system_id, body, key)
        result = self.status(system)
        self._remember(system_id, "apply", key, request_hash, 200, result)
        return result

    async def _apply(self, system_id: str, body: dict[str, Any], key: str) -> LoadedSystem:
        self._check_envelope("apply_request", body)
        compiled = self._compile(body)
        if body["context_revision"] != self._context_revision(system_id, compiled):
            raise ApiError("STALE_CONTEXT", "The Runtime state changed since validation. Validate again.")
        local = self.systems.get(system_id)
        if local is not None and local.loaded and body["expected_active_revision"] != local.snapshot.config_revision:
            raise ApiError("REVISION_CONFLICT", "The expected active revision does not match this Runtime.")
        impact = await self._index_impact(system_id, compiled, body)
        if impact["action"] == "blocked":
            code = _BLOCKED_ERRORS.get(impact["code"], "SYSTEM_STATE_CONFLICT")
            raise ApiError(code, impact["message"])
        operation = body["operation"]
        revision = body["config_revision"]
        pipelines = self._pipelines(body)
        target = body.get("target_index_generation")
        if impact["action"] in ("create", "recover", "rebuild_required") and target is None:
            raise ApiError(
                "REQUEST_VALIDATION_FAILED", "target_index_generation is required.", path="/target_index_generation"
            )
        if impact["action"] == "rebuild_required" and not body.get("allow_rebuild", False):
            raise ApiError("REBUILD_CONFIRMATION_REQUIRED", impact["message"])
        if operation == "update" and (local is None or not local.loaded):
            raise ApiError("SYSTEM_STATE_CONFLICT", "Reload the published revision before updating.")
        if local is not None and operation in ("update", "recover_index") and self.ingestion.has_active_work(system_id):
            raise ApiError("SYSTEM_BUSY", "Ingestion work is still queued or running for this System.")

        if impact["action"] == "create":
            assert target is not None
            snapshot = self._build(system_id, revision, compiled, target)
            await self._create_index(snapshot, key)
            system = LoadedSystem(snapshot, created_by_operation_id=key)
            self._load(system, pipelines)
        elif impact["action"] == "recover":
            assert target is not None
            snapshot = self._build(system_id, revision, compiled, target)
            await self._create_index(snapshot, key)
            previous = local.pipelines if local else None
            system = LoadedSystem(snapshot, created_by_operation_id=key)
            if previous is not None:
                system.pipelines = {name: PipelineState(state.loaded, state.loaded) for name, state in previous.items()}
            self._load(system, pipelines)
        elif impact["action"] == "rebuild_required":
            assert local is not None
            await self._close_and_drain(local)
            old_name = local.snapshot.index_name
            try:
                await local.snapshot.store.delete_index(old_name)
            except IndexStateUnknown as error:
                raise ApiError("SYSTEM_STATE_UNKNOWN", error.message) from error
            assert target is not None
            snapshot = self._build(system_id, revision, compiled, target)
            await self._create_index(snapshot, key)
            system = LoadedSystem(snapshot, created_by_operation_id=key)
            system.pipelines = {
                name: PipelineState(state.loaded, state.loaded) for name, state in local.pipelines.items()
            }
            self._load(system, pipelines)
        else:  # reuse
            generation = body["expected_index_generation"]
            if (
                local is not None
                and local.snapshot.config_revision == revision
                and local.snapshot.index_generation == generation
            ):
                system = local
            else:
                snapshot = self._build(system_id, revision, compiled, generation)
                system = LoadedSystem(
                    snapshot, created_by_operation_id=local.created_by_operation_id if local else None
                )
                if local is not None:
                    system.pipelines = {
                        name: PipelineState(state.loaded, state.loaded) for name, state in local.pipelines.items()
                    }
            self._load(system, pipelines)
        _log.info("system applied", extra={"code": operation, "status": revision})
        return system

    def _load(self, system: LoadedSystem, pipelines: tuple[str, ...]) -> None:
        for name in pipelines:
            system.pipelines[name] = PipelineState(loaded=True, ready=True)
        system.index_ready = True
        self.systems[system.snapshot.system_id] = system

    async def detach(self, system_id: str, pipeline: str | None, key: str, expected: dict[str, str]) -> None:
        request_hash = sha256_hex({"pipeline": pipeline, **expected})
        if self._replay(system_id, "detach", key, request_hash) is not None:
            return
        local = self.systems.get(system_id)
        if local is None:
            raise ApiError("SYSTEM_NOT_FOUND", "The System is not loaded in this Runtime.")
        self._check_binding(local, expected)
        lock = self._lock(system_id)
        if lock.locked():
            raise ApiError("SYSTEM_BUSY", "Another management operation is running for this System.")
        async with lock:
            targets = (pipeline,) if pipeline else PIPELINES
            if "ingestion" in targets and self.ingestion.has_active_work(system_id):
                raise ApiError("SYSTEM_BUSY", "Ingestion work is still queued or running for this System.")
            if "inference" in targets and local.pipelines["inference"].loaded:
                local.pipelines["inference"].ready = False
                if not await self.queries.drain(system_id, self.settings.inference_timeout_seconds):
                    local.pipelines["inference"].ready = True
                    raise ApiError("DEADLINE_EXCEEDED", "Accepted queries did not finish within the query deadline.")
            for name in targets:
                local.pipelines[name] = PipelineState()
        self._remember(system_id, "detach", key, request_hash, 204, None)

    @staticmethod
    def _check_binding(local: LoadedSystem, expected: dict[str, str]) -> None:
        if expected.get("revision") != local.snapshot.config_revision:
            raise ApiError("REVISION_CONFLICT", "The expected revision does not match this Runtime.")
        generation = expected.get("generation")
        if generation is not None and generation != local.snapshot.index_generation:
            raise ApiError("INDEX_CONFLICT", "The expected index generation does not match this Runtime.")
        fingerprint = expected.get("fingerprint")
        if fingerprint is not None and fingerprint != local.snapshot.compiled.fingerprint:
            raise ApiError("INDEX_CONFLICT", "The expected index fingerprint does not match this Runtime.")

    async def delete(self, system_id: str, key: str, expected: dict[str, str | None]) -> None:
        request_hash = sha256_hex(expected)
        if self._replay(system_id, "delete", key, request_hash) is not None:
            return
        local = self.systems.get(system_id)
        generation, fingerprint = expected.get("generation"), expected.get("fingerprint")
        if local is None and generation is None:
            raise ApiError("SYSTEM_NOT_FOUND", "The System is not loaded and no index generation was given.")
        lock = self._lock(system_id)
        if lock.locked():
            raise ApiError("SYSTEM_BUSY", "Another management operation is running for this System.")
        async with lock:
            if local is not None:
                self._check_binding(local, {k: v for k, v in expected.items() if v is not None})
                if self.ingestion.has_active_work(system_id):
                    raise ApiError("SYSTEM_BUSY", "Ingestion work is still queued or running for this System.")
                await self._close_and_drain(local)
                store = local.snapshot.store
                generation = generation or local.snapshot.index_generation
            else:
                store = self.stores.default()
            assert generation is not None
            try:
                info = await self._owned(store, system_id, generation, fingerprint)
            except ApiError:
                if local is not None:
                    for state in local.pipelines.values():
                        state.ready = state.loaded
                raise
            if info is not None:
                try:
                    await store.delete_index(info.name)
                except IndexStateUnknown as error:
                    raise ApiError("SYSTEM_STATE_UNKNOWN", error.message) from error
            self.systems.pop(system_id, None)
        self._remember(system_id, "delete", key, request_hash, 204, None)

    # ------------------------------------------------------------------ standalone

    async def load_standalone(self, snapshot_body: dict[str, Any], environment: dict[str, str]) -> None:
        """FTEST/ENT: load one Config at startup. The index must already exist (Q-021)."""
        system_id = snapshot_body["system_id"]
        try:
            compiled = compile_system(snapshot_body["config"], self.catalog, environment=environment)
        except ConfigInvalid as error:
            raise RuntimeError(f"invalid System Config: {error}") from error
        generation = self.settings.index_generation
        if not generation:
            raise RuntimeError("RAG_INDEX_GENERATION is required in standalone mode")
        snapshot = self._build(system_id, snapshot_body["config_revision"], compiled, generation)
        expected = self.settings.index_fingerprint or compiled.fingerprint
        if expected != compiled.fingerprint:
            raise RuntimeError("RAG_INDEX_FINGERPRINT does not match the Config")
        info = await self._owned(snapshot.store, system_id, generation, expected)
        system = LoadedSystem(snapshot, index_ready=info is not None)
        pipelines = (self.settings.pipeline,) if self.settings.pipeline else PIPELINES
        for name in pipelines:
            system.pipelines[name] = PipelineState(loaded=True, ready=True)
        self.systems[system_id] = system
