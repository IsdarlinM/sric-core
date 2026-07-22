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


class ResourceBudget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_attempts: int = Field(default=1, ge=1, le=20)
    timeout_seconds: float = Field(default=300, gt=0, le=86400)
    max_artifacts: int = Field(default=100, ge=0, le=10000)
    max_output_bytes: int = Field(default=50 * 1024 * 1024, ge=0)


class Job(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: str = Field(default_factory=lambda: f"JOB-{uuid4().hex[:12].upper()}")
    job_type: str
    status: JobStatus = JobStatus.QUEUED
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    cancellable: bool = True
    resumable: bool = False
    dependencies: list[str] = Field(default_factory=list)
    attempt: int = 0
    budget: ResourceBudget = Field(default_factory=ResourceBudget)
    metadata: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
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
    """Persistent job DAG/event engine with explicit retry/resource budgets."""

    def __init__(self, workspace: Path) -> None:
        job_dir = workspace / "jobs"
        self.path = (job_dir / "jobs.json") if job_dir.is_dir() else workspace / "jobs.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._save({"schema_version": "2", "jobs": [], "events": []})

    def _load(self) -> dict[str, Any]:
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("jobs store must contain a JSON object")
        raw.setdefault("jobs", [])
        raw.setdefault("events", [])
        return raw

    def _save(self, data: dict[str, Any]) -> None:
        data["schema_version"] = "2"
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        tmp.replace(self.path)

    def create(self, job_type: str, metadata: dict[str, Any] | None = None, *, dependencies: list[str] | None = None, budget: ResourceBudget | None = None, resumable: bool = False, provenance: dict[str, Any] | None = None) -> Job:
        deps = list(dict.fromkeys(dependencies or []))
        existing = {j.job_id for j in self.list()}
        missing = [x for x in deps if x not in existing]
        if missing: raise ValueError(f"unknown job dependencies: {missing}")
        job = Job(job_type=job_type, metadata=metadata or {}, dependencies=deps, budget=budget or ResourceBudget(), resumable=resumable, provenance=provenance or {})
        data = self._load(); data["jobs"].append(job.model_dump(mode="json")); self._save(data)
        self.event(job.job_id, "created", f"Job {job.job_id} queued", {"dependencies": deps})
        return job

    def get(self, job_id: str) -> Job:
        for raw in self._load()["jobs"]:
            if raw["job_id"] == job_id: return Job.model_validate(raw)
        raise KeyError(job_id)

    def dependencies_satisfied(self, job_id: str) -> bool:
        return all(self.get(dep).status == JobStatus.COMPLETED for dep in self.get(job_id).dependencies)

    def ready(self) -> list[Job]:
        return [j for j in self.list() if j.status == JobStatus.QUEUED and self.dependencies_satisfied(j.job_id)]

    def transition(self, job_id: str, status: JobStatus, *, progress: float | None = None, error: str | None = None) -> Job:
        data = self._load()
        allowed = {JobStatus.QUEUED:{JobStatus.RUNNING,JobStatus.CANCELLED,JobStatus.FAILED},JobStatus.RUNNING:{JobStatus.PAUSED,JobStatus.CANCELLING,JobStatus.COMPLETED,JobStatus.FAILED},JobStatus.PAUSED:{JobStatus.RUNNING,JobStatus.CANCELLING,JobStatus.FAILED},JobStatus.CANCELLING:{JobStatus.CANCELLED,JobStatus.FAILED},JobStatus.CANCELLED:set(),JobStatus.COMPLETED:set(),JobStatus.FAILED:{JobStatus.QUEUED}}
        for idx, raw in enumerate(data["jobs"]):
            if raw["job_id"] != job_id: continue
            job = Job.model_validate(raw)
            if status == JobStatus.RUNNING and not self.dependencies_satisfied(job_id): raise ValueError("job dependencies are not completed")
            if status != job.status and status not in allowed[job.status]: raise ValueError(f"invalid job transition {job.status} -> {status}")
            job.status = status
            if progress is not None: job.progress = progress
            if status == JobStatus.COMPLETED: job.progress = 1.0
            if status == JobStatus.RUNNING: job.attempt += 1
            job.error = error; job.updated_at = utcnow(); data["jobs"][idx] = job.model_dump(mode="json"); self._save(data)
            self.event(job_id, "status", f"Job transitioned to {status}", {"status": status, "attempt": job.attempt}); return job
        raise KeyError(job_id)

    def retry(self, job_id: str) -> Job:
        job = self.get(job_id)
        if job.status != JobStatus.FAILED: raise ValueError("only FAILED jobs can be retried")
        if job.attempt >= job.budget.max_attempts: raise PermissionError("job retry budget exhausted")
        return self.transition(job_id, JobStatus.QUEUED, error=None)

    def add_artifact(self, job_id: str, artifact_id: str) -> Job:
        data = self._load()
        for idx, raw in enumerate(data["jobs"]):
            if raw["job_id"] != job_id: continue
            job = Job.model_validate(raw)
            if len(job.artifacts) >= job.budget.max_artifacts: raise PermissionError("job artifact budget exceeded")
            if artifact_id not in job.artifacts: job.artifacts.append(artifact_id)
            job.updated_at=utcnow(); data["jobs"][idx]=job.model_dump(mode="json"); self._save(data); self.event(job_id,"artifact","Artifact recorded",{"artifact_id":artifact_id}); return job
        raise KeyError(job_id)

    def request_cancel(self, job_id: str) -> Job:
        job=self.get(job_id)
        if not job.cancellable: raise PermissionError("job is not cancellable")
        if job.status==JobStatus.QUEUED: return self.transition(job_id,JobStatus.CANCELLED)
        return self.transition(job_id,JobStatus.CANCELLING)

    def event(self, job_id: str, event_type: str, message: str, data: dict[str, Any] | None = None) -> JobEvent:
        self.get(job_id); evt=JobEvent(job_id=job_id,event_type=event_type,message=message,data=data or {}); store=self._load(); store["events"].append(evt.model_dump(mode="json")); self._save(store); return evt

    def events(self, job_id: str) -> list[JobEvent]: return [JobEvent.model_validate(x) for x in self._load()["events"] if x["job_id"]==job_id]
    def all_events(self, after: int = 0) -> list[JobEvent]:
        if after<0: raise ValueError("event cursor must be >= 0")
        return [JobEvent.model_validate(x) for x in self._load()["events"][after:]]
    def list(self) -> list[Job]: return [Job.model_validate(x) for x in self._load()["jobs"]]
    def dag(self) -> dict[str, Any]: return {"nodes":[j.model_dump(mode="json") for j in self.list()],"edges":[{"from":dep,"to":j.job_id} for j in self.list() for dep in j.dependencies]}


class JobContext:
    def __init__(self, engine: JobEngine, job_id: str) -> None: self.engine=engine; self.job_id=job_id
    def cancelled(self) -> bool: return self.engine.get(self.job_id).status in {JobStatus.CANCELLING,JobStatus.CANCELLED}
    def progress(self,value:float,message:str="progress")->Job:
        if self.cancelled(): raise RuntimeError("job cancellation requested")
        job=self.engine.transition(self.job_id,JobStatus.RUNNING,progress=value); self.engine.event(self.job_id,"progress",message,{"progress":value}); return job
    def artifact(self,artifact_id:str)->Job: return self.engine.add_artifact(self.job_id,artifact_id)


class AsyncJobRunner:
    def __init__(self, engine: JobEngine, max_concurrency: int = 2) -> None:
        import asyncio
        if max_concurrency<1: raise ValueError("max_concurrency must be >= 1")
        self.engine=engine; self._semaphore=asyncio.Semaphore(max_concurrency); self._tasks:dict[str,Any]={}
    def submit(self, job_type: str, worker: Any, metadata: dict[str, Any] | None = None, *, dependencies: list[str] | None = None, budget: ResourceBudget | None = None, resumable: bool = False) -> Job:
        import asyncio
        job=self.engine.create(job_type,metadata,dependencies=dependencies,budget=budget,resumable=resumable)
        async def run()->None:
            async with self._semaphore:
                if self.engine.get(job.job_id).status==JobStatus.CANCELLED:return
                if not self.engine.dependencies_satisfied(job.job_id):return
                self.engine.transition(job.job_id,JobStatus.RUNNING);ctx=JobContext(self.engine,job.job_id)
                try:
                    await worker(ctx);current=self.engine.get(job.job_id)
                    if current.status==JobStatus.CANCELLING:self.engine.transition(job.job_id,JobStatus.CANCELLED)
                    elif current.status not in {JobStatus.CANCELLED,JobStatus.FAILED}:self.engine.transition(job.job_id,JobStatus.COMPLETED)
                except Exception as exc:
                    current=self.engine.get(job.job_id)
                    if current.status==JobStatus.CANCELLING:self.engine.transition(job.job_id,JobStatus.CANCELLED)
                    elif current.status not in {JobStatus.CANCELLED,JobStatus.FAILED}:self.engine.transition(job.job_id,JobStatus.FAILED,error=str(exc))
        self._tasks[job.job_id]=asyncio.create_task(run()); return job
    async def wait(self,job_id:str)->Job:
        task=self._tasks.get(job_id)
        if task is not None:await task
        return self.engine.get(job_id)
    def recover_orphans(self)->list[str]:
        recovered=[]
        for job in self.engine.list():
            if job.status in {JobStatus.RUNNING,JobStatus.PAUSED,JobStatus.CANCELLING} and job.job_id not in self._tasks:
                reason="worker ended; resumable job requires explicit retry" if job.resumable else "worker process ended before job completion";self.engine.transition(job.job_id,JobStatus.FAILED,error=reason);recovered.append(job.job_id)
        return recovered
