"""In-process job pool. Progress is stored only when a handler reports it."""

from __future__ import annotations

import logging
import threading
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import Settings
from backend.app.core.errors import InvalidInput, NotFound
from backend.app.db.models import Analysis, Job

logger = logging.getLogger(__name__)

Handler = Callable[["JobContext", dict[str, Any]], dict[str, Any] | None]


class JobContext:
    """Handle passed to a job handler. Sessions are short so SQLite is not held."""

    def __init__(self, runner: JobRunner, job_id: str) -> None:
        self.runner = runner
        self.job_id = job_id
        self.settings: Settings = runner.settings
        self.analysis_id = str(uuid.uuid4())
        self.reported_progress = False

    def cancelled(self) -> bool:
        session = self.runner.factory()
        try:
            job = session.get(Job, self.job_id)
            return job is None or bool(job.cancel_requested) or job.status == "cancelled"
        finally:
            session.close()

    def set_progress(self, value: float) -> None:
        """Record a fraction in ``[0, 1]``. Callers must not invent a fraction."""

        if not 0.0 <= value <= 1.0:
            raise ValueError("progress must be between 0 and 1")
        with self.runner.lock:
            session = self.runner.factory()
            try:
                job = session.get(Job, self.job_id)
                if job is None or job.cancel_requested or job.status in {"cancelled", "failed", "succeeded"}:
                    return
                job.progress = float(value)
                session.commit()
                self.reported_progress = True
            finally:
                session.close()


class JobRunner:
    """Small thread pool. Interrupted ``running`` rows are failed on startup."""

    def __init__(
        self,
        factory: sessionmaker[Session],
        engine: Any,
        settings: Settings,
    ) -> None:
        self.factory = factory
        self.engine = engine
        self.settings = settings
        self.lock = threading.Lock()
        self._handlers: dict[str, Handler] = {}
        self._executor: ThreadPoolExecutor | None = None

    def register(self, kind: str, handler: Handler) -> None:
        self._handlers[kind] = handler

    def start(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="beai-job")
        self.recover_interrupted()
        self._requeue_pending()

    def shutdown(self) -> None:
        executor = self._executor
        self._executor = None
        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=True)

    def recover_interrupted(self) -> int:
        """Mark jobs left ``running`` as failed. Returns how many rows changed."""

        if not self._jobs_table_exists():
            logger.info("job recovery skipped because the jobs table is absent")
            return 0
        session = self.factory()
        try:
            rows = list(session.scalars(select(Job).where(Job.status == "running")))
            now = datetime.now(UTC)
            for job in rows:
                job.status = "failed"
                job.completed_at = now
                job.error_json = {
                    "code": "interrupted",
                    "message": "The job was interrupted when the server restarted.",
                }
            session.commit()
            return len(rows)
        finally:
            session.close()

    def submit(self, kind: str, payload: dict[str, Any], structure_id: str | None = None) -> Job:
        if kind not in self._handlers:
            raise InvalidInput(f"Unknown job kind: {kind}.")
        if self._executor is None:
            raise InvalidInput("The job runner is not running.")
        session = self.factory()
        try:
            job = Job(
                id=str(uuid.uuid4()),
                kind=kind,
                status="pending",
                progress=None,
                cancel_requested=False,
                created_at=datetime.now(UTC),
                started_at=None,
                completed_at=None,
                error_json=None,
                payload_json=payload,
                analysis_id=None,
                structure_id=structure_id,
            )
            session.add(job)
            session.commit()
            session.refresh(job)
            job_id = job.id
        finally:
            session.close()
        self._executor.submit(self._execute, job_id)
        session = self.factory()
        try:
            stored = session.get(Job, job_id)
            if stored is None:
                raise NotFound("Job not found.")
            return stored
        finally:
            session.close()

    def cancel(self, job_id: str) -> Job:
        session = self.factory()
        try:
            job = session.get(Job, job_id)
            if job is None:
                raise NotFound("Job not found.")
            if job.status in {"succeeded", "failed", "cancelled"}:
                return job
            job.cancel_requested = True
            if job.status == "pending":
                job.status = "cancelled"
                job.completed_at = datetime.now(UTC)
                job.error_json = {
                    "code": "cancelled",
                    "message": "Cancelled before the job started.",
                }
            session.commit()
            session.refresh(job)
            return job
        finally:
            session.close()

    def get(self, job_id: str) -> Job:
        session = self.factory()
        try:
            job = session.get(Job, job_id)
            if job is None:
                raise NotFound("Job not found.")
            session.expunge(job)
            return job
        finally:
            session.close()

    def list_jobs(self) -> list[Job]:
        session = self.factory()
        try:
            rows = list(session.scalars(select(Job).order_by(Job.created_at.desc(), Job.id.desc())))
            for row in rows:
                session.expunge(row)
            return rows
        finally:
            session.close()

    def _execute(self, job_id: str) -> None:
        session = self.factory()
        try:
            job = session.get(Job, job_id)
            if job is None:
                return
            if job.cancel_requested or job.status != "pending":
                if job.status == "pending" and job.cancel_requested:
                    job.status = "cancelled"
                    job.completed_at = datetime.now(UTC)
                    job.error_json = {
                        "code": "cancelled",
                        "message": "Cancelled before the job started.",
                    }
                    session.commit()
                return
            kind = job.kind
            payload = dict(job.payload_json)
            job.status = "running"
            job.started_at = datetime.now(UTC)
            session.commit()
        finally:
            session.close()

        handler = self._handlers.get(kind)
        if handler is None:
            self._finish_error(job_id, "invalid_input", f"Unknown job kind: {kind}.")
            return
        context = JobContext(self, job_id)
        if context.cancelled():
            self._finish_cancelled(job_id)
            return
        try:
            result = handler(context, payload)
        except Exception as exc:
            logger.exception("job %s failed", job_id)
            code = getattr(exc, "code", "internal_error")
            message = getattr(exc, "message", None) or "The job failed."
            if code == "internal_error" and not hasattr(exc, "message"):
                message = "The job failed."
            self._finish_error(job_id, str(code), str(message))
            return
        if context.cancelled():
            self._finish_cancelled(job_id)
            return
        self._finish_success(job_id, result, context)

    def _finish_success(self, job_id: str, result: dict[str, Any] | None, context: JobContext) -> None:
        session = self.factory()
        try:
            job = session.get(Job, job_id)
            if job is None:
                return
            if job.cancel_requested:
                job.status = "cancelled"
                job.completed_at = datetime.now(UTC)
                job.error_json = {"code": "cancelled", "message": "Cancelled."}
                session.commit()
                return
            analysis_id = None
            if result is not None:
                analysis_id = context.analysis_id
                result = dict(result)
                result["analysis_id"] = analysis_id
                session.add(
                    Analysis(
                        id=analysis_id,
                        kind=str(result.get("kind") or job.kind),
                        status=str(result.get("status") or "succeeded"),
                        created_at=job.created_at,
                        started_at=job.started_at,
                        completed_at=datetime.now(UTC),
                        structure_id=job.structure_id,
                        result_json=result,
                        error_json=None,
                    )
                )
            job.status = "succeeded"
            job.analysis_id = analysis_id
            job.completed_at = datetime.now(UTC)
            job.error_json = None
            if context.reported_progress:
                job.progress = 1.0
            session.commit()
        finally:
            session.close()

    def _finish_cancelled(self, job_id: str) -> None:
        session = self.factory()
        try:
            job = session.get(Job, job_id)
            if job is None or job.status in {"succeeded", "failed", "cancelled"}:
                return
            job.status = "cancelled"
            job.completed_at = datetime.now(UTC)
            job.error_json = {"code": "cancelled", "message": "Cancelled."}
            session.commit()
        finally:
            session.close()

    def _finish_error(self, job_id: str, code: str, message: str) -> None:
        session = self.factory()
        try:
            job = session.get(Job, job_id)
            if job is None or job.status in {"succeeded", "cancelled"}:
                return
            job.status = "failed"
            job.completed_at = datetime.now(UTC)
            job.error_json = {"code": code, "message": message}
            session.commit()
        finally:
            session.close()

    def _requeue_pending(self) -> None:
        if self._executor is None or not self._jobs_table_exists():
            return
        session = self.factory()
        try:
            ids = [row.id for row in session.scalars(select(Job).where(Job.status == "pending"))]
        finally:
            session.close()
        for job_id in ids:
            self._executor.submit(self._execute, job_id)

    def _jobs_table_exists(self) -> bool:
        try:
            return inspect(self.engine).has_table("jobs")
        except Exception:
            logger.info("could not inspect the jobs table", exc_info=True)
            return False
