"""Loaded Systems and the DEV management lifecycle (06_runtime_api_and_deployment.md#system-lifecycle-api).

The Builder is authoritative for the published revision and the index binding. This module
checks the Builder's expectations against the local snapshot and the physical index, then
applies one operation per System at a time.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
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
from rag_engine.contracts import http_def, schema_ref
from rag_engine.core.canonical import sha256_hex
from rag_engine.core.errors import ConfigInvalid
from rag_engine.engine.catalog import Catalog
from rag_engine.engine.compiler import compile_system
from rag_engine.engine.index_writer import IndexWriter
from rag_engine.engine.pipelines import EngineDeps, build_inference_graph, build_ingestion_graph
from rag_engine.engine.plan import CompiledSystem
from rag_engine.runtime.errors import ApiError
from rag_engine.runtime.idempotency import IdempotencyStore
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
    "INDEX_RECONNECT_INCOMPATIBLE": "INDEX_CONFLICT",
    "INDEX_BINDING_CONFLICT": "INDEX_CONFLICT",
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
    # (Idempotency-Key, request hash) of a rebuild that started deleting the old index. Only that
    # same operation may run again to finish it.
    pending_rebuild: tuple[str, str] | None = None

    @property
    def loaded(self) -> bool:
        return any(state.loaded for state in self.pipelines.values())


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
        # system_id -> Idempotency-Key of the management operation running now. A resend of that
        # same operation waits for its result instead of being refused (06 line 134).
        self._in_flight: dict[str, str] = {}
        self.idempotency = IdempotencyStore(settings.idempotency_retention_seconds)

    # ------------------------------------------------------------------ status

    def _lock(self, system_id: str) -> asyncio.Lock:
        return self._locks.setdefault(system_id, asyncio.Lock())

    @contextlib.asynccontextmanager
    async def _operation(self, system_id: str, key: str) -> AsyncIterator[None]:
        """One management operation per System at a time. Another operation is refused with
        SYSTEM_BUSY; a resend of the running one (same Idempotency-Key) waits for it."""
        lock = self._lock(system_id)
        if lock.locked() and self._in_flight.get(system_id) != key:
            raise ApiError("SYSTEM_BUSY", "Another management operation is running for this System.")
        async with lock:
            self._in_flight[system_id] = key
            try:
                yield
            finally:
                self._in_flight.pop(system_id, None)

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
            # A half-done rebuild also blocks other management changes until it is resent.
            "busy": self._lock(snapshot.system_id).locked()
            or self.ingestion.has_active_work(snapshot.system_id)
            or system.pending_rebuild is not None,
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
            # Loaded and ready come from this Runtime; the creator comes from the specified index (06).
            loaded = self.status(local)
            loaded.pop("created_by_operation_id", None)
            if info is not None and info.meta.get("created_by_operation_id"):
                loaded["created_by_operation_id"] = info.meta["created_by_operation_id"]
            return loaded
        if info is None:
            self._raise_if_cluster_unknown()
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

    def _context_revision(
        self, system_id: str, compiled: CompiledSystem, body: dict[str, Any], impact: dict[str, Any]
    ) -> str:
        """Binds target, Catalog, Config, draft, pipeline, operation, expected binding and the
        preview result (06 config validation), plus the local state they were checked against."""
        local = self.systems.get(system_id)
        state = {
            "system_id": system_id,
            "catalog": self.catalog.catalog_revision,
            "config": sha256_hex(compiled.config),
            "draft": body.get("draft_revision"),
            "pipeline": body.get("pipeline"),
            "operation": body.get("operation"),
            "expected": [
                body.get("expected_active_revision"),
                body.get("expected_index_generation"),
                body.get("expected_index_fingerprint"),
            ],
            "impact": impact,
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
        # The Builder names the binding it expects; when this Runtime has a System loaded it must be
        # that one, or a check of B would end in changing or deleting A.
        if (
            local is not None
            and local.loaded
            and (
                expected_generation != local.snapshot.index_generation
                or expected_fingerprint != local.snapshot.compiled.fingerprint
            )
        ):
            return _impact("blocked", "INDEX_BINDING_CONFLICT", "預期的索引綁定與本機載入的不同。")
        if operation == "recover_index":
            recovery = body["recovery_from"]
            # recovery_from describes the published binding being recovered (06 恢復查核).
            if recovery["index_generation"] != expected_generation:
                raise ApiError(
                    "REQUEST_VALIDATION_FAILED",
                    "recovery_from must name the expected index generation.",
                    path="/recovery_from/index_generation",
                )
            if body["expected_active_revision"] not in (None, recovery["config_revision"]):
                raise ApiError(
                    "REQUEST_VALIDATION_FAILED",
                    "recovery_from must name the expected active revision.",
                    path="/recovery_from/config_revision",
                )
            try:
                old = await self._owned(store, system_id, recovery["index_generation"], None)
            except ApiError as error:
                return self._blocked_from(error)
            if old is not None:
                return _impact("blocked", "PUBLISHED_INDEX_PRESENT", "原索引仍存在，請改用 reload。")
            if expected_fingerprint is not None and fingerprint != expected_fingerprint:
                return _impact("blocked", "INDEX_RECONNECT_INCOMPATIBLE", "Config 與已發布版本的索引不符。")
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
            if operation == "update" and fingerprint != expected_fingerprint:
                # A rebuild deletes the old index anyway. It may already be gone because a rebuild of
                # this plan was interrupted (06 失敗與交接), so the plan can continue.
                return _impact(
                    "rebuild_required",
                    "INDEX_FINGERPRINT_CHANGED",
                    "原索引已不存在。確認後以新世代建立索引並重新匯入。",
                    fingerprint,
                )
            return _impact("blocked", "PUBLISHED_INDEX_MISSING", "已發布的索引不存在，請確認後改用 recover_index。")
        # _meta already proved the ownership. The mapping is compared with the published version:
        # the candidate when it keeps the index, else the active snapshot. A candidate that changes
        # the mapping is a rebuild, not a mismatch.
        if fingerprint == expected_fingerprint:
            published: dict[str, Any] | None = compiled.index.mappings
        elif local is not None and local.snapshot.compiled.fingerprint == expected_fingerprint:
            published = local.snapshot.compiled.index.mappings
        else:
            published = None
        if published is not None and not mapping_compatible(
            published["properties"], info.mappings.get("properties", {})
        ):
            return _impact("blocked", "INDEX_OWNERSHIP_UNVERIFIED", "實際 mapping 與已發布設定不符。")
        if operation == "reload":
            if fingerprint != expected_fingerprint:
                return _impact("blocked", "INDEX_RECONNECT_INCOMPATIBLE", "Config 與已發布版本的索引不符。")
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
            "context_revision": self._context_revision(system_id, compiled, body, impact),
            "active_config_revision": local.snapshot.config_revision if local and local.loaded else None,
            "loaded": loaded,
            "index_impact": impact,
        }
        if "pipeline" in body:
            result["pipeline"] = body["pipeline"]
        return result

    async def apply(self, system_id: str, body: dict[str, Any], key: str) -> dict[str, Any]:
        request_hash = sha256_hex(body)
        replay = self.idempotency.find(system_id, "apply", key, request_hash)
        if replay is not None and replay.body is not None:
            return replay.body
        async with self._operation(system_id, key):
            replay = self.idempotency.find(system_id, "apply", key, request_hash)
            if replay is not None and replay.body is not None:
                return replay.body  # the original finished while this resend waited
            system = await self._apply(system_id, body, key, request_hash)
        result = self.status(system)
        self.idempotency.remember(system_id, "apply", key, request_hash, 200, result)
        return result

    async def _apply(self, system_id: str, body: dict[str, Any], key: str, request_hash: str) -> LoadedSystem:
        self._check_envelope("apply_request", body)
        compiled = self._compile(body)
        local = self.systems.get(system_id)
        if local is not None and local.pending_rebuild is not None:
            if local.pending_rebuild != (key, request_hash):
                self._raise_if_rebuild_pending(local)
            return await self._rebuild(system_id, local, compiled, body, key)
        if body["operation"] == "recover_index" and body["config_revision"] != body["recovery_from"]["config_revision"]:
            raise ApiError(
                "REQUEST_VALIDATION_FAILED",
                "recover_index keeps the published revision: config_revision must equal recovery_from.config_revision.",
                path="/config_revision",
            )
        impact = await self._index_impact(system_id, compiled, body)
        if body["context_revision"] != self._context_revision(system_id, compiled, body, impact):
            raise ApiError("STALE_CONTEXT", "The Runtime state changed since validation. Validate again.")
        if impact["action"] == "blocked":  # the same reason the preview reported
            code = _BLOCKED_ERRORS.get(impact["code"], "SYSTEM_STATE_CONFLICT")
            raise ApiError(code, impact["message"])
        if local is not None and local.loaded and body["expected_active_revision"] != local.snapshot.config_revision:
            raise ApiError("REVISION_CONFLICT", "The expected active revision does not match this Runtime.")
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
        # A rebuild may continue without a loaded System (after a restart); keeping the index needs one.
        if operation == "update" and impact["action"] != "rebuild_required" and (local is None or not local.loaded):
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
            assert target is not None
            await self._check_rebuild_target(compiled, system_id, body["expected_index_generation"], target, key)
            if local is not None:
                await self._close_and_drain(local)
                local.pending_rebuild = (key, request_hash)  # from here only this operation may continue
            system = await self._rebuild(system_id, local, compiled, body, key)
        else:  # reuse
            generation = body["expected_index_generation"]
            if (
                local is not None
                and local.snapshot.config_revision == revision
                and local.snapshot.index_generation == generation
                and local.snapshot.compiled.config == compiled.config  # e.g. a rotated password
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

    async def _check_rebuild_target(
        self, compiled: CompiledSystem, system_id: str, old_generation: str, target: str, key: str
    ) -> None:
        """Before anything is closed or deleted: the target must be a new generation that no other
        operation has created."""
        if target == old_generation:
            raise ApiError(
                "INDEX_CONFLICT",
                "target_index_generation must be a new generation.",
                path="/target_index_generation",
            )
        store = self.stores.for_connection(compiled.index.connection)
        try:
            existing = await store.get_index(index_name(self.settings.env, system_id, target))
        except IndexStateUnknown as error:
            raise ApiError("SYSTEM_STATE_UNKNOWN", error.message) from error
        if existing is not None and existing.meta.get("created_by_operation_id") != key:
            raise ApiError("INDEX_CONFLICT", "The target index generation is already used by another operation.")

    async def _rebuild(
        self,
        system_id: str,
        local: LoadedSystem | None,
        compiled: CompiledSystem,
        body: dict[str, Any],
        key: str,
    ) -> LoadedSystem:
        """Delete the old index and create the target one. Safe to run again with the same
        operation, also after a restart: a missing old index and a target created by this
        operation are both fine."""
        old_store = local.snapshot.store if local is not None else self.stores.for_connection(compiled.index.connection)
        if local is not None:
            local.index_ready = False  # entries are closed; the old index is about to go
        try:
            await old_store.delete_index(index_name(self.settings.env, system_id, body["expected_index_generation"]))
        except IndexStateUnknown as error:
            raise ApiError("SYSTEM_STATE_UNKNOWN", error.message) from error
        snapshot = self._build(system_id, body["config_revision"], compiled, body["target_index_generation"])
        await self._create_index(snapshot, key)
        system = LoadedSystem(snapshot, created_by_operation_id=key)
        if local is not None:
            system.pipelines = {
                name: PipelineState(state.loaded, state.loaded) for name, state in local.pipelines.items()
            }
        self._load(system, self._pipelines(body))
        return system

    @staticmethod
    def _raise_if_rebuild_pending(local: LoadedSystem | None) -> None:
        if local is not None and local.pending_rebuild is not None:
            raise ApiError(
                "SYSTEM_BUSY", "A rebuild is half done. Resend it with its original Idempotency-Key and body first."
            )

    def _load(self, system: LoadedSystem, pipelines: tuple[str, ...]) -> None:
        for name in pipelines:
            system.pipelines[name] = PipelineState(loaded=True, ready=True)
        system.index_ready = True
        self.systems[system.snapshot.system_id] = system

    async def detach(self, system_id: str, pipeline: str | None, key: str, expected: dict[str, str]) -> None:
        request_hash = sha256_hex({"pipeline": pipeline, **expected})
        if self.idempotency.find(system_id, "detach", key, request_hash) is not None:
            return
        local = self.systems.get(system_id)
        if local is None:
            raise ApiError("SYSTEM_NOT_FOUND", "The System is not loaded in this Runtime.")
        self._raise_if_rebuild_pending(local)
        self._check_binding(local, expected)
        async with self._operation(system_id, key):
            if self.idempotency.find(system_id, "detach", key, request_hash) is not None:
                return
            targets = (pipeline,) if pipeline else PIPELINES
            # Close the entries first, so nothing new is accepted while this operation waits.
            previous = {name: local.pipelines[name].ready for name in targets}
            for name in targets:
                local.pipelines[name].ready = False
            if "ingestion" in targets and self.ingestion.has_active_work(system_id):
                self._reopen(local, previous)
                raise ApiError("SYSTEM_BUSY", "Ingestion work is still queued or running for this System.")
            drains = "inference" in targets and local.pipelines["inference"].loaded
            if drains and not await self.queries.drain(system_id, self.settings.inference_timeout_seconds):
                self._reopen(local, previous)
                raise ApiError("DEADLINE_EXCEEDED", "Accepted queries did not finish within the query deadline.")
            for name in targets:
                local.pipelines[name] = PipelineState()
        self.idempotency.remember(system_id, "detach", key, request_hash, 204, None)

    def _raise_if_cluster_unknown(self) -> None:
        """An unloaded System was looked up on the default ES only. When the deployment can also
        reach PLED clusters, "not found there" does not mean missing, so report it as unknown."""
        if self.stores.pled_configured():
            raise ApiError(
                "SYSTEM_STATE_UNKNOWN",
                "The System is not loaded and its index may be on a PLED cluster this Runtime cannot locate. "
                "Reload the System with its published Config first.",
            )

    @staticmethod
    def _reopen(local: LoadedSystem, previous: dict[str, bool]) -> None:
        for name, ready in previous.items():
            local.pipelines[name].ready = ready

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
        if self.idempotency.find(system_id, "delete", key, request_hash) is not None:
            return
        local = self.systems.get(system_id)
        self._raise_if_rebuild_pending(local)
        generation, fingerprint = expected.get("generation"), expected.get("fingerprint")
        if local is None and generation is None:
            raise ApiError("SYSTEM_NOT_FOUND", "The System is not loaded and no index generation was given.")
        async with self._operation(system_id, key):
            if self.idempotency.find(system_id, "delete", key, request_hash) is not None:
                return
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
            if info is None and local is None:
                self._raise_if_cluster_unknown()
            if info is not None:
                try:
                    await store.delete_index(info.name)
                except IndexStateUnknown as error:
                    raise ApiError("SYSTEM_STATE_UNKNOWN", error.message) from error
            self.systems.pop(system_id, None)
        self.idempotency.remember(system_id, "delete", key, request_hash, 204, None)

    # ------------------------------------------------------------------ standalone

    async def load_standalone(self, snapshot_body: dict[str, Any], environment: dict[str, str]) -> None:
        """FTEST/ENT: load one Config at startup. The index must already exist (Q-021)."""
        system_id = snapshot_body["system_id"]
        try:
            compiled = compile_system(
                snapshot_body["config"], self.catalog, environment=environment, pipeline=self.settings.pipeline
            )
        except ConfigInvalid as error:
            raise RuntimeError(f"invalid System Config: {error}") from error
        generation = self.settings.index_generation
        if not generation:
            raise RuntimeError("RAG_INDEX_GENERATION is required in standalone mode")
        uuid_v4 = schema_ref("runtime_identity.schema.json", "/$defs/uuid_v4")
        if next(contract_errors(uuid_v4, generation), None) is not None:
            raise RuntimeError("RAG_INDEX_GENERATION must be the UUID v4 of the index generation")
        snapshot = self._build(system_id, snapshot_body["config_revision"], compiled, generation)
        expected = self.settings.index_fingerprint or compiled.fingerprint
        if expected != compiled.fingerprint:
            raise RuntimeError("RAG_INDEX_FINGERPRINT does not match the Config")
        info = await self._owned(snapshot.store, system_id, generation, expected)
        index_ready = info is not None
        if info is not None and not mapping_compatible(
            compiled.index.mappings["properties"], info.mappings.get("properties", {})
        ):
            # Ownership alone is not enough to serve (06: 歸屬、指紋與實際 mapping 均符合才能沿用).
            _log.error("index mapping does not match the Config", extra={"code": "INDEX_OWNERSHIP_UNVERIFIED"})
            index_ready = False
        system = LoadedSystem(snapshot, index_ready=index_ready)
        pipelines = (self.settings.pipeline,) if self.settings.pipeline else PIPELINES
        for name in pipelines:
            system.pipelines[name] = PipelineState(loaded=True, ready=True)
        self.systems[system_id] = system
