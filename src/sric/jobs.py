from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JobStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Job(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: str = Field(default_factory=lambda: f"JOB-{uuid4().hex[:12].upper()}")
    job_type: str
    status: JobStatus = JobStatus.QUEUED
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    cancellable: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[str] = Field(default_factory=list)
    error: str | None = None


class JobEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str = Field(default_factory=lambda: f"JEV-{uuid4().hex[:12].upper()}")
    job_id: str
    timestamp: datetime = Field(default_factory=utcnow)
    event_type: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)


class JobEngine:
    """Persistent local job/event state with explicit cancellation semantics."""

    def __init__(self, workspace: Path) -> None:
        self.path = workspace / "jobs.json"
        if not self.path.exists():
            self._save({"schema_version": "1", "jobs": [], "events": []})

    def _load(self) -> dict[str, Any]:
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("jobs store must contain a JSON object")
        return raw

    def _save(self, data: dict[str, Any]) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        tmp.replace(self.path)

    def create(self, job_type: str, metadata: dict[str, Any] | None = None) -> Job:
        job = Job(job_type=job_type, metadata=metadata or {})
        data = self._load()
        data["jobs"].append(job.model_dump(mode="json"))
        self._save(data)
        self.event(job.job_id, "created", f"Job {job.job_id} queued")
        return job

    def get(self, job_id: str) -> Job:
        data = self._load()
        for raw in data["jobs"]:
            if raw["job_id"] == job_id:
                return Job.model_validate(raw)
        raise KeyError(job_id)

    def transition(
        self,
        job_id: str,
        status: JobStatus,
        *,
        progress: float | None = None,
        error: str | None = None,
    ) -> Job:
        data = self._load()
        allowed: dict[JobStatus, set[JobStatus]] = {
            JobStatus.QUEUED: {JobStatus.RUNNING, JobStatus.CANCELLED, JobStatus.FAILED},
            JobStatus.RUNNING: {
                JobStatus.PAUSED,
                JobStatus.CANCELLING,
                JobStatus.COMPLETED,
                JobStatus.FAILED,
            },
            JobStatus.PAUSED: {JobStatus.RUNNING, JobStatus.CANCELLING, JobStatus.FAILED},
            JobStatus.CANCELLING: {JobStatus.CANCELLED, JobStatus.FAILED},
            JobStatus.CANCELLED: set(),
            JobStatus.COMPLETED: set(),
            JobStatus.FAILED: set(),
        }
        for idx, raw in enumerate(data["jobs"]):
            if raw["job_id"] != job_id:
                continue
            job = Job.model_validate(raw)
            if status != job.status and status not in allowed[job.status]:
                raise ValueError(f"invalid job transition {job.status} -> {status}")
            job.status = status
            if progress is not None:
                job.progress = progress
            if status == JobStatus.COMPLETED:
                job.progress = 1.0
            job.error = error
            job.updated_at = utcnow()
            data["jobs"][idx] = job.model_dump(mode="json")
            self._save(data)
            self.event(job_id, "status", f"Job transitioned to {status}", {"status": status})
            return job
        raise KeyError(job_id)

    def request_cancel(self, job_id: str) -> Job:
        job = self.get(job_id)
        if not job.cancellable:
            raise PermissionError("job is not cancellable")
        if job.status == JobStatus.QUEUED:
            return self.transition(job_id, JobStatus.CANCELLED)
        return self.transition(job_id, JobStatus.CANCELLING)

    def event(
        self,
        job_id: str,
        event_type: str,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> JobEvent:
        self.get(job_id)
        evt = JobEvent(job_id=job_id, event_type=event_type, message=message, data=data or {})
        store = self._load()
        store["events"].append(evt.model_dump(mode="json"))
        self._save(store)
        return evt

    def events(self, job_id: str) -> list[JobEvent]:
        data = self._load()
        return [JobEvent.model_validate(x) for x in data["events"] if x["job_id"] == job_id]

    def all_events(self, after: int = 0) -> list[JobEvent]:
        """Return persisted events after a zero-based cursor for SSE/polling consumers."""
        if after < 0:
            raise ValueError("event cursor must be >= 0")
        data = self._load()
        return [JobEvent.model_validate(x) for x in data["events"][after:]]

    def list(self) -> list[Job]:
        return [Job.model_validate(x) for x in self._load()["jobs"]]


class JobContext:
    """Cooperative context for bounded async workers."""

    def __init__(self, engine: JobEngine, job_id: str) -> None:
        self.engine = engine
        self.job_id = job_id

    def cancelled(self) -> bool:
        return self.engine.get(self.job_id).status in {JobStatus.CANCELLING, JobStatus.CANCELLED}

    def progress(self, value: float, message: str = "progress") -> Job:
        if self.cancelled():
            raise RuntimeError("job cancellation requested")
        job = self.engine.transition(self.job_id, JobStatus.RUNNING, progress=value)
        self.engine.event(self.job_id, "progress", message, {"progress": value})
        return job


class AsyncJobRunner:
    """Bounded-concurrency in-process runner backed by persistent JobEngine state.

    Worker code must cooperate with cancellation via JobContext. The runner never grants network,
    filesystem or executor permissions by itself; products remain responsible for policy gates.
    """

    def __init__(self, engine: JobEngine, max_concurrency: int = 2) -> None:
        import asyncio

        if max_concurrency < 1:
            raise ValueError("max_concurrency must be >= 1")
        self.engine = engine
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._tasks: dict[str, Any] = {}

    def submit(self, job_type: str, worker: Any, metadata: dict[str, Any] | None = None) -> Job:
        import asyncio

        job = self.engine.create(job_type, metadata)

        async def run() -> None:
            async with self._semaphore:
                current = self.engine.get(job.job_id)
                if current.status == JobStatus.CANCELLED:
                    return
                self.engine.transition(job.job_id, JobStatus.RUNNING)
                ctx = JobContext(self.engine, job.job_id)
                try:
                    await worker(ctx)
                    current = self.engine.get(job.job_id)
                    if current.status == JobStatus.CANCELLING:
                        self.engine.transition(job.job_id, JobStatus.CANCELLED)
                    elif current.status not in {JobStatus.CANCELLED, JobStatus.FAILED}:
                        self.engine.transition(job.job_id, JobStatus.COMPLETED)
                except Exception as exc:
                    current = self.engine.get(job.job_id)
                    if current.status == JobStatus.CANCELLING:
                        self.engine.transition(job.job_id, JobStatus.CANCELLED)
                    elif current.status not in {JobStatus.CANCELLED, JobStatus.FAILED}:
                        self.engine.transition(job.job_id, JobStatus.FAILED, error=str(exc))

        self._tasks[job.job_id] = asyncio.create_task(run())
        return job

    async def wait(self, job_id: str) -> Job:
        task = self._tasks.get(job_id)
        if task is None:
            return self.engine.get(job_id)
        await task
        return self.engine.get(job_id)

    def recover_orphans(self) -> list[str]:
        recovered: list[str] = []
        for job in self.engine.list():
            if job.status in {JobStatus.RUNNING, JobStatus.PAUSED, JobStatus.CANCELLING} and job.job_id not in self._tasks:
                self.engine.transition(job.job_id, JobStatus.FAILED, error="worker process ended before job completion")
                recovered.append(job.job_id)
        return recovered
