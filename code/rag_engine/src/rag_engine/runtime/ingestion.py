"""Pod-local Ingestion control (06_runtime_api_and_deployment.md#pod-local-ingestion-control).

Everything here lives in this process's memory: document occupancy, the queue, Runs and
per-document status. A restart starts empty. The Runtime must therefore run exactly one
process per Pod (uvicorn --workers 1).

State changes happen in synchronous sections without ``await``, so they are atomic on the
single asyncio event loop. Keep it that way when editing.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from rag_engine.core.errors import DocumentFailed, EngineError
from rag_engine.core.types import Document
from rag_engine.engine.index_writer import CleanupUnknown
from rag_engine.runtime.errors import ApiError
from rag_engine.runtime.observability import request_id_var, run_id_var, system_id_var
from rag_engine.runtime.settings import Settings
from rag_engine.runtime.snapshot import Snapshot

_log = logging.getLogger(__name__)

ACTIVE = frozenset({"queued", "running", "cancelling"})
TERMINAL = frozenset({"completed", "cancelled", "failed", "unknown"})
COUNT_KEYS = ("queued", "running", "cancelling", "completed", "cancelled", "failed", "unknown")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass
class DocRecord:
    document_id: str
    token: str
    payload: Document | None
    status: str = "queued"
    module: str | None = None
    updated_at: str = field(default_factory=_now)
    error: dict[str, Any] | None = None
    write_acquired: bool = False

    def view(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "status": self.status,
            "module": self.module,
            "updated_at": self.updated_at,
            "error": self.error,
        }


@dataclass
class Run:
    run_id: str
    system_id: str
    # The Config version that runs the work; released when the Run finishes so old versions
    # (Snapshot with its two LangGraphs) do not pile up while terminal Runs are kept.
    snapshot: Snapshot | None
    config_revision: str
    parameters: dict[str, Any]
    request_id: str | None
    documents: dict[str, DocRecord]
    finished_at: float | None = None

    def status(self) -> str:
        return aggregate([record.status for record in self.documents.values()])

    def view(self) -> dict[str, Any]:
        records = list(self.documents.values())
        counts = {key: 0 for key in COUNT_KEYS}
        for record in records:
            counts[record.status] += 1
        return {
            "run_id": self.run_id,
            "status": self.status(),
            "config_revision": self.config_revision,
            "counts": {"total": len(records), **counts},
            "documents": [record.view() for record in records],
        }


def aggregate(statuses: list[str]) -> str:
    """Run status from document statuses (runtime_http.schema.json#/$defs/ingestion_run_status)."""
    if all(status == "queued" for status in statuses):
        return "queued"
    if any(status in ACTIVE for status in statuses):
        return "running"
    if "unknown" in statuses:
        return "unknown"
    if all(status == "completed" for status in statuses):
        return "completed"
    if all(status == "cancelled" for status in statuses):
        return "cancelled"
    if "completed" not in statuses:
        return "failed"
    return "partial"


@dataclass(frozen=True)
class _Occupancy:
    token: str
    run_id: str | None  # None for Retire


@dataclass(frozen=True)
class _Job:
    run: Run
    record: DocRecord


class _Cancelled(Exception):
    """Raised inside a worker when its document was cancelled before the write."""


class IngestionControl:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._occupancy: dict[tuple[str, str], _Occupancy] = {}
        self._runs: dict[tuple[str, str], Run] = {}
        self._latest: dict[tuple[str, str], str] = {}
        self._queues: dict[str, deque[tuple[str, str]]] = {}
        self._waiting: dict[str, int] = {}
        self._running: dict[str, int] = {}
        # Retire operations in progress. They take a slot of the Pod total like a running
        # document (06#pod-local-ingestion-control), so unfinished work cannot pile up.
        self._retiring = 0
        self._order: deque[str] = deque()
        self._wakeup = asyncio.Event()
        self._tasks: list[asyncio.Task[None]] = []

    # ------------------------------------------------------------------ lifecycle

    def start(self) -> None:
        for number in range(self._settings.ingestion_max_concurrency_total):
            self._tasks.append(asyncio.create_task(self._worker(), name=f"ingestion-worker-{number}"))
        self._tasks.append(asyncio.create_task(self._cleanup_loop(), name="ingestion-cleanup"))

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._tasks.clear()

    # ------------------------------------------------------------------ queries used by lifecycle

    def _busy_slots(self) -> int:
        """Running documents plus Retire operations; at most ingestion_max_concurrency_total."""
        return sum(self._running.values()) + self._retiring

    def has_active_work(self, system_id: str) -> bool:
        if any(key[0] == system_id for key in self._occupancy):
            return True
        return self._running.get(system_id, 0) > 0

    # ------------------------------------------------------------------ submission

    def submit(
        self,
        snapshot: Snapshot,
        documents: list[Document],
        parameters: dict[str, Any],
    ) -> Run:
        system_id = snapshot.system_id
        conflicts = []
        for document in documents:
            occupancy = self._occupancy.get((system_id, document["document_id"]))
            if occupancy is not None:
                conflicts.append(self._conflict(system_id, document["document_id"], occupancy))
        if conflicts:
            first = conflicts[0]
            position = next(i for i, d in enumerate(documents) if d["document_id"] == first["document_id"])
            raise ApiError(
                "DOCUMENT_BUSY",
                "Some documents are still being processed in this Runtime Pod.",
                path=f"/documents/{position}/document_id",
                run_id=first.get("run_id"),
                extra={"conflicts": conflicts},
            )
        waiting = self._waiting.get(system_id, 0)
        total_waiting = sum(self._waiting.values())
        # 06#pod-local-ingestion-control: any queue capacity shortage is 503 RUNTIME_CAPACITY_EXHAUSTED.
        if waiting + len(documents) > self._settings.ingestion_queue_max_waiting_per_system:
            raise ApiError(
                "RUNTIME_CAPACITY_EXHAUSTED", "The System's Ingestion queue is full.", headers={"Retry-After": "5"}
            )
        if total_waiting + len(documents) > self._settings.ingestion_queue_max_waiting_total:
            raise ApiError(
                "RUNTIME_CAPACITY_EXHAUSTED", "The Runtime Ingestion queue is full.", headers={"Retry-After": "5"}
            )
        run_id = f"ing-{uuid.uuid4().hex}"
        records: dict[str, DocRecord] = {}
        for document in documents:
            token = uuid.uuid4().hex
            records[document["document_id"]] = DocRecord(document["document_id"], token, document)
            self._occupancy[(system_id, document["document_id"])] = _Occupancy(token, run_id)
            self._latest[(system_id, document["document_id"])] = run_id
        run = Run(run_id, system_id, snapshot, snapshot.config_revision, parameters, request_id_var.get(), records)
        self._runs[(system_id, run_id)] = run
        queue = self._queues.setdefault(system_id, deque())
        for document_id in records:
            queue.append((run_id, document_id))
        self._waiting[system_id] = waiting + len(documents)
        if system_id not in self._order:
            self._order.append(system_id)
        self._wakeup.set()
        _log.info("ingestion accepted", extra={"code": "ACCEPTED", "status": len(documents)})
        return run

    def _conflict(self, system_id: str, document_id: str, occupancy: _Occupancy) -> dict[str, Any]:
        if occupancy.run_id is None:
            return {"document_id": document_id, "status": None}
        run = self._runs.get((system_id, occupancy.run_id))
        record = run.documents.get(document_id) if run else None
        return {
            "document_id": document_id,
            "status": record.status if record else "unknown",
            "run_id": occupancy.run_id,
        }

    # ------------------------------------------------------------------ status queries

    def _live_run(self, system_id: str, run_id: str) -> Run | None:
        run = self._runs.get((system_id, run_id))
        if run is None:
            return None
        if run.finished_at is not None and time.monotonic() - run.finished_at > self._settings.status_retention_seconds:
            return None
        return run

    def run_status(self, system_id: str, run_id: str) -> dict[str, Any]:
        run = self._live_run(system_id, run_id)
        if run is None:
            return {"run_id": run_id, "status": "unknown"}
        return run.view()

    def document_status(self, system_id: str, document_id: str) -> dict[str, Any]:
        run_id = self._latest.get((system_id, document_id))
        run = self._live_run(system_id, run_id) if run_id else None
        record = run.documents.get(document_id) if run else None
        if run is None or record is None:
            return {
                "document_id": document_id,
                "run_id": None,
                "status": "unknown",
                "module": None,
                "updated_at": None,
                "error": None,
            }
        return {"run_id": run.run_id, **record.view()}

    # ------------------------------------------------------------------ cancellation

    def cancel(self, system_id: str, run_id: str, document_ids: list[str]) -> dict[str, Any]:
        run = self._live_run(system_id, run_id)
        if run is None:
            raise ApiError("INGESTION_RUN_NOT_FOUND", "The Ingestion Run does not exist or has expired.")
        results = []
        for document_id in document_ids:
            record = run.documents.get(document_id)
            if record is None:
                results.append({"document_id": document_id, "result": "not_found", "status": None})
                continue
            if record.status == "queued":
                self._finish(run, record, "cancelled", None)
                self._waiting[system_id] -= 1
            elif record.status == "running" and not record.write_acquired:
                self._finish(run, record, "cancelled", None)
            elif record.status == "running":
                record.status, record.updated_at = "cancelling", _now()
            results.append(
                {"document_id": document_id, "result": _cancel_result(record.status), "status": record.status}
            )
        return {"run_id": run_id, "documents": results}

    # ------------------------------------------------------------------ Retire

    def reserve_retire(self, system_id: str, document_id: str) -> str:
        """Occupy the document for a Retire. Returns the token for release_retire."""
        occupancy = self._occupancy.get((system_id, document_id))
        if occupancy is not None:
            conflict = self._conflict(system_id, document_id, occupancy)
            raise ApiError(
                "DOCUMENT_BUSY",
                "The document is still being processed in this Runtime Pod.",
                run_id=conflict.get("run_id"),
            )
        if self._busy_slots() >= self._settings.ingestion_max_concurrency_total:
            raise ApiError(
                "RUNTIME_CAPACITY_EXHAUSTED", "The Runtime is at its Ingestion capacity.", headers={"Retry-After": "5"}
            )
        token = uuid.uuid4().hex
        self._occupancy[(system_id, document_id)] = _Occupancy(token, None)
        self._retiring += 1
        return token

    def release_retire(self, system_id: str, document_id: str, token: str) -> None:
        occupancy = self._occupancy.get((system_id, document_id))
        if occupancy is not None and occupancy.token == token:
            del self._occupancy[(system_id, document_id)]
        self._retiring -= 1
        self._wakeup.set()  # a waiting worker may take the freed slot

    # ------------------------------------------------------------------ workers

    def _pick(self) -> _Job | None:
        if self._busy_slots() >= self._settings.ingestion_max_concurrency_total:
            return None  # a Retire holds a slot; release_retire wakes the workers
        for _ in range(len(self._order)):
            system_id = self._order[0]
            self._order.rotate(-1)
            queue = self._queues.get(system_id)
            if not queue or self._running.get(system_id, 0) >= self._settings.ingestion_max_concurrency_per_system:
                continue
            while queue:
                run_id, document_id = queue.popleft()
                run = self._runs.get((system_id, run_id))
                record = run.documents.get(document_id) if run else None
                if run is None or record is None or record.status != "queued":
                    continue  # cancelled while queued; the waiting slot was already returned
                self._waiting[system_id] -= 1
                self._running[system_id] = self._running.get(system_id, 0) + 1
                record.status, record.updated_at = "running", _now()
                return _Job(run, record)
        return None

    async def _worker(self) -> None:
        while True:
            job = self._pick()
            if job is None:
                self._wakeup.clear()
                await self._wakeup.wait()
                continue
            system_id = job.run.system_id
            try:
                await self._execute(job)
            except asyncio.CancelledError:
                raise
            except Exception:  # pragma: no cover - last-resort guard
                _log.exception("ingestion worker crashed")
                if job.record.status in ACTIVE:
                    self._finish(
                        job.run,
                        job.record,
                        "failed",
                        {"code": "INTERNAL_ERROR", "module": job.record.module, "message": "Internal error."},
                    )
            finally:
                self._running[system_id] -= 1
                self._wakeup.set()

    async def _execute(self, job: _Job) -> None:
        run, record = job.run, job.record
        snapshot = run.snapshot
        assert snapshot is not None  # released only after every document finished
        system_token = system_id_var.set(run.system_id)
        run_token = run_id_var.set(run.run_id)
        request_token = request_id_var.set(run.request_id)

        def progress(module: str) -> None:
            if record.status != "running" or record.write_acquired:
                if record.status == "cancelled":
                    raise _Cancelled()
                return
            record.module, record.updated_at = module, _now()

        try:
            async with asyncio.timeout(self._settings.ingestion_document_timeout_seconds):
                result = await snapshot.ingestion_graph.ainvoke(
                    {"documents": [record.payload]},
                    config={
                        "configurable": {
                            "progress": progress,
                            "request_values": run.parameters,
                            "request_id": run.request_id,
                            "deadline": time.monotonic() + self._settings.ingestion_document_timeout_seconds,
                        }
                    },
                )
                prepared = await snapshot.writer.prepare(record.document_id, result["documents"])
                if not self._acquire_write(run, record):
                    return
                record.module, record.updated_at = "indexing", _now()
                await snapshot.writer.commit(prepared)
            self._settle(run, record, success=True)
        except _Cancelled:
            return
        except CleanupUnknown as error:
            self._settle(run, record, success=False, unknown=True, error=_error(error))
        except DocumentFailed as error:
            self._settle(run, record, success=False, error=_error(error))
        except TimeoutError:
            failure = {
                "code": "DEADLINE_EXCEEDED",
                "module": record.module,
                "message": "The document exceeded its processing deadline.",
            }
            self._settle(run, record, success=False, unknown=record.write_acquired, error=failure)
        except EngineError as error:
            self._settle(run, record, success=False, error=_error(error))
        finally:
            request_id_var.reset(request_token)
            run_id_var.reset(run_token)
            system_id_var.reset(system_token)

    def _acquire_write(self, run: Run, record: DocRecord) -> bool:
        """Cancellation and the first index write race on this check (no await inside)."""
        occupancy = self._occupancy.get((run.system_id, record.document_id))
        if record.status != "running" or occupancy is None or occupancy.token != record.token:
            return False
        record.write_acquired = True
        return True

    def _settle(
        self, run: Run, record: DocRecord, *, success: bool, unknown: bool = False, error: dict[str, Any] | None = None
    ) -> None:
        if record.status not in ("running", "cancelling"):
            return
        if success:
            record.module = None
            self._finish(run, record, "completed", None)
        elif record.status == "cancelling":
            self._finish(run, record, "cancelled", None)
        else:
            self._finish(run, record, "unknown" if unknown else "failed", error)

    def _finish(self, run: Run, record: DocRecord, status: str, error: dict[str, Any] | None) -> None:
        record.status = status
        record.error = error
        record.updated_at = _now()
        record.payload = None
        key = (run.system_id, record.document_id)
        occupancy = self._occupancy.get(key)
        if occupancy is not None and occupancy.token == record.token:
            del self._occupancy[key]
        if all(item.status in TERMINAL for item in run.documents.values()):
            run.finished_at = time.monotonic()
            run.snapshot = None
            self._enforce_record_limit()

    # ------------------------------------------------------------------ retention

    def _enforce_record_limit(self) -> None:
        finished = sorted(
            (run for run in self._runs.values() if run.finished_at is not None), key=lambda run: run.finished_at or 0.0
        )
        total = sum(len(run.documents) for run in finished)
        while finished and total > self._settings.status_max_terminal_documents:
            oldest = finished.pop(0)
            total -= len(oldest.documents)
            self._forget(oldest)

    def _forget(self, run: Run) -> None:
        self._runs.pop((run.system_id, run.run_id), None)
        for document_id in run.documents:
            key = (run.system_id, document_id)
            if self._latest.get(key) == run.run_id:
                del self._latest[key]

    def purge_expired(self) -> int:
        cutoff = time.monotonic() - self._settings.status_retention_seconds
        expired = [run for run in self._runs.values() if run.finished_at is not None and run.finished_at < cutoff]
        for run in expired:
            self._forget(run)
        return len(expired)

    async def _cleanup_loop(self) -> None:
        while True:
            await asyncio.sleep(self._settings.status_cleanup_interval_seconds)
            removed = self.purge_expired()
            if removed:
                _log.info("expired ingestion runs removed", extra={"status": removed})


def _cancel_result(status: str) -> str:
    return {
        "cancelled": "cancelled",
        "cancelling": "cancelling",
        "completed": "already_finished",
        "failed": "already_finished",
        "unknown": "not_cancellable",
    }[status]


def _error(error: EngineError) -> dict[str, Any]:
    return {"code": error.code, "module": error.module, "message": error.message}
