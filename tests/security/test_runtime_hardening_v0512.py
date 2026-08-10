from __future__ import annotations

import asyncio
import subprocess
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sric import web_console, web_runtime
from sric.jobs import AsyncJobRunner, JobEngine, JobStatus
from sric.web_catalog import install_json_safe_catalog
from sric.web_console import ConsoleJob, WebConsoleConfig, WebConsoleManager, mount_web_console


def _config(**overrides: object) -> WebConsoleConfig:
    values: dict[str, object] = {
        "product": "test-product",
        "display_name": "Test Product",
        "cli_module": "sric.cli_all",
        "version": "0.5.12-dev",
        "max_concurrent_jobs": 1,
        "max_output_chars": 100_000,
        "max_runtime_seconds": 0.01,
        "max_jobs": 1,
    }
    values.update(overrides)
    return WebConsoleConfig(**values)  # type: ignore[arg-type]


def test_catalog_failure_returns_redacted_structured_503(monkeypatch: pytest.MonkeyPatch) -> None:
    install_json_safe_catalog()

    def fail_catalog(_module: str) -> list[dict[str, object]]:
        raise RuntimeError("password=catalog-secret token=second-secret")

    monkeypatch.setattr(web_console, "build_command_catalog", fail_catalog)
    app = FastAPI()
    mount_web_console(app, _config())
    response = TestClient(app).get("/api/v1/console/catalog")

    assert response.status_code == 503
    payload = response.json()
    assert isinstance(payload.get("detail"), str)
    assert "command catalog unavailable" in payload["detail"]
    assert "catalog-secret" not in response.text
    assert "second-secret" not in response.text
    assert "REDACTED" in response.text


def test_pruned_terminal_job_remains_available_to_inflight_sse_reader() -> None:
    install_json_safe_catalog()
    manager = WebConsoleManager(_config(max_jobs=1))
    first = ConsoleJob(
        job_id="first",
        command="version",
        args=[],
        classification="READ_ONLY_SAFE",
        approval_required=False,
        created_at=1.0,
        status="succeeded",
        finished_at=2.0,
        returncode=0,
        output=["done\n"],
        output_chars=5,
    )
    second = ConsoleJob(
        job_id="second",
        command="doctor",
        args=[],
        classification="READ_ONLY_SAFE",
        approval_required=False,
        created_at=3.0,
        status="running",
    )
    manager._jobs[first.job_id] = first
    manager._jobs[second.job_id] = second

    manager._prune()

    assert "first" not in manager._jobs
    assert manager.snapshot("first")["status"] == "succeeded"
    chunks, cursor, status = manager.output_since("first", 0)
    assert chunks == ["done\n"]
    assert cursor == 1
    assert status == "succeeded"


class _StubbornProcess:
    def __init__(self) -> None:
        self.stdout: list[str] = []
        self.returncode: int | None = None
        self.wait_calls = 0
        self.terminate_calls = 0
        self.kill_calls = 0

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls += 1
        if self.wait_calls <= 3:
            raise subprocess.TimeoutExpired(cmd="fake", timeout=timeout or 0)
        self.returncode = -9
        return self.returncode

    def terminate(self) -> None:
        self.terminate_calls += 1

    def kill(self) -> None:
        self.kill_calls += 1

    def poll(self) -> int | None:
        return self.returncode


def test_force_kill_final_wait_timeout_is_contained_and_background_reaped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_json_safe_catalog()
    process = _StubbornProcess()
    monkeypatch.setattr(web_runtime.subprocess, "Popen", lambda *args, **kwargs: process)

    manager = WebConsoleManager(_config())
    job = ConsoleJob(
        job_id="stubborn",
        command="version",
        args=[],
        classification="READ_ONLY_SAFE",
        approval_required=False,
        created_at=time.time(),
    )
    manager._jobs[job.job_id] = job

    manager._run(job.job_id, ["version"])

    assert job.status == "timed_out"
    assert process.terminate_calls == 1
    assert process.kill_calls >= 1
    assert "background reaper engaged" in "".join(job.output)
    for _ in range(100):
        if job.process is None:
            break
        time.sleep(0.01)
    assert job.process is None
    assert job.returncode == -9


def test_job_failure_and_operational_metadata_are_redacted_before_persistence(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        engine = JobEngine(tmp_path)
        runner = AsyncJobRunner(engine)

        async def worker(_ctx: object) -> None:
            raise RuntimeError("token=worker-secret password=worker-password")

        job = runner.submit(
            "redaction-test",
            worker,
            metadata={"authorization": "Bearer metadata-secret"},
        )
        result = await runner.wait(job.job_id)
        assert result.status == JobStatus.FAILED
        assert result.error is not None
        assert "worker-secret" not in result.error
        assert "worker-password" not in result.error
        assert "REDACTED" in result.error
        assert "metadata-secret" not in str(result.metadata)

    asyncio.run(scenario())
    raw = (tmp_path / "jobs.json").read_text(encoding="utf-8")
    assert "worker-secret" not in raw
    assert "worker-password" not in raw
    assert "metadata-secret" not in raw
