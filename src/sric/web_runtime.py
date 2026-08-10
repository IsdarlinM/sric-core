from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from typing import Any

from fastapi import HTTPException

from .errors import safe_exception_message

RETIRED_JOB_TTL_SECONDS = 300.0
PROCESS_GRACE_SECONDS = 5.0


def _retired_store(manager: Any) -> dict[str, tuple[Any, float]]:
    store = getattr(manager, "_sentinel_retired_jobs", None)
    if store is None:
        store = {}
        setattr(manager, "_sentinel_retired_jobs", store)
    return store


def _cleanup_retired(manager: Any, *, now: float | None = None) -> None:
    current = time.monotonic() if now is None else now
    store = _retired_store(manager)
    expired = [job_id for job_id, (_, deadline) in store.items() if deadline <= current]
    for job_id in expired:
        store.pop(job_id, None)


def _lookup_job(manager: Any, job_id: str) -> Any | None:
    job = manager._jobs.get(job_id)
    if job is not None:
        return job
    _cleanup_retired(manager)
    retired = _retired_store(manager).get(job_id)
    return None if retired is None else retired[0]


def _snapshot_job(job: Any) -> dict[str, Any]:
    return {
        "job_id": job.job_id,
        "command": job.command,
        "args": list(job.args),
        "classification": job.classification,
        "approval_required": job.approval_required,
        "status": job.status,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "returncode": job.returncode,
        "output": "".join(job.output),
        "output_chunks": len(job.output),
        "truncated": job.truncated,
        "cancel_requested": job.cancel_requested,
    }


def install_web_console_runtime_hardening() -> None:
    """Install fail-closed runtime guards on the shared Web Console manager once."""

    from . import web_console

    manager_type = web_console.WebConsoleManager
    if getattr(manager_type, "_sentinel_runtime_hardened", False):
        return

    original_catalog = manager_type.catalog
    original_cancel = manager_type.cancel

    def catalog(self: Any) -> list[dict[str, Any]]:
        try:
            return original_catalog(self)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail="command catalog unavailable: " + safe_exception_message(exc),
            ) from exc

    def prune(self: Any) -> None:
        with self._lock:
            _cleanup_retired(self)
            if len(self._jobs) <= self.config.max_jobs:
                return
            completed = sorted(
                (
                    job
                    for job in self._jobs.values()
                    if job.status in web_console.TERMINAL_STATES
                ),
                key=lambda job: job.finished_at or job.created_at,
            )
            excess = max(0, len(self._jobs) - self.config.max_jobs)
            now = time.monotonic()
            retired = _retired_store(self)
            for job in completed[:excess]:
                retired[job.job_id] = (job, now + RETIRED_JOB_TTL_SECONDS)
                self._jobs.pop(job.job_id, None)

    def snapshot(self: Any, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = _lookup_job(self, job_id)
            if job is None:
                raise KeyError(job_id)
            return _snapshot_job(job)

    def output_since(self: Any, job_id: str, cursor: int) -> tuple[list[str], int, str]:
        with self._lock:
            job = _lookup_job(self, job_id)
            if job is None:
                raise KeyError(job_id)
            start = max(0, min(cursor, len(job.output)))
            chunks = list(job.output[start:])
            return chunks, len(job.output), job.status

    def _background_reap(self: Any, job_id: str, process: subprocess.Popen[str]) -> None:
        """Reap a forcibly killed child without blocking a Web worker indefinitely."""

        returncode: int | None = None
        last_error: BaseException | None = None
        for _ in range(3):
            if process.poll() is not None:
                returncode = process.returncode
                break
            try:
                process.kill()
            except ProcessLookupError:
                returncode = process.poll()
                break
            except Exception as exc:  # pragma: no cover - OS-specific failure surface
                last_error = exc
            try:
                returncode = process.wait(timeout=PROCESS_GRACE_SECONDS)
                break
            except subprocess.TimeoutExpired:
                continue
            except Exception as exc:  # pragma: no cover - OS-specific failure surface
                last_error = exc
                break

        with self._lock:
            job = _lookup_job(self, job_id)
            if job is None or job.process is not process:
                return
            if returncode is not None:
                job.returncode = returncode
                job.process = None
            elif last_error is not None:
                self._append_output(
                    job,
                    "Background process reaper failed: "
                    + safe_exception_message(last_error)
                    + "\n",
                )

    def run(self: Any, job_id: str, argv: list[str]) -> None:
        with self._semaphore:
            with self._lock:
                job = self._jobs.get(job_id)
                if job is None:
                    return
                if job.cancel_requested:
                    job.status = "cancelled"
                    job.finished_at = time.time()
                    return
                job.status = "running"
                job.started_at = time.time()

            env = os.environ.copy()
            env["NO_COLOR"] = "1"
            env["SENTINEL_BANNER"] = "off"
            env["PYTHONUNBUFFERED"] = "1"
            env["SENTINEL_CLI_MODULE"] = self.config.cli_module
            env["SENTINEL_WEB_CONSOLE"] = "1"
            command = [sys.executable, "-m", "sric.web_console_runner", *argv]

            try:
                process = subprocess.Popen(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    shell=False,
                    env=env,
                )
            except Exception as exc:
                self._append_output(
                    job,
                    "Unable to start CLI command: "
                    + type(exc).__name__
                    + ": "
                    + safe_exception_message(exc)
                    + "\n",
                )
                with self._lock:
                    job.status = "failed"
                    job.finished_at = time.time()
                return

            with self._lock:
                job.process = process

            def reader() -> None:
                if process.stdout is None:
                    return
                for line in process.stdout:
                    self._append_output(job, line)

            reader_thread = threading.Thread(target=reader, daemon=True)
            reader_thread.start()
            timed_out = False
            unreaped = False
            returncode: int | None = None
            try:
                returncode = process.wait(timeout=self.config.max_runtime_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                try:
                    process.terminate()
                except ProcessLookupError:
                    returncode = process.poll()
                except Exception as exc:
                    self._append_output(
                        job,
                        "Unable to terminate timed-out command cleanly: "
                        + safe_exception_message(exc)
                        + "\n",
                    )
                if returncode is None:
                    try:
                        returncode = process.wait(timeout=PROCESS_GRACE_SECONDS)
                    except subprocess.TimeoutExpired:
                        try:
                            process.kill()
                        except ProcessLookupError:
                            returncode = process.poll()
                        except Exception as exc:
                            self._append_output(
                                job,
                                "Unable to force-kill timed-out command: "
                                + safe_exception_message(exc)
                                + "\n",
                            )
                        if returncode is None:
                            try:
                                returncode = process.wait(timeout=PROCESS_GRACE_SECONDS)
                            except subprocess.TimeoutExpired:
                                unreaped = True
                                self._append_output(
                                    job,
                                    "Timed-out command did not exit after forced termination; "
                                    "background reaper engaged.\n",
                                )
                                threading.Thread(
                                    target=_background_reap,
                                    args=(self, job_id, process),
                                    daemon=True,
                                    name=f"sentinel-reaper-{job_id[:8]}",
                                ).start()
                            except Exception as exc:
                                unreaped = True
                                self._append_output(
                                    job,
                                    "Unable to reap force-killed command: "
                                    + safe_exception_message(exc)
                                    + "\n",
                                )
                                threading.Thread(
                                    target=_background_reap,
                                    args=(self, job_id, process),
                                    daemon=True,
                                    name=f"sentinel-reaper-{job_id[:8]}",
                                ).start()
                    except Exception as exc:
                        unreaped = True
                        self._append_output(
                            job,
                            "Unable to reap terminated command: "
                            + safe_exception_message(exc)
                            + "\n",
                        )
                        threading.Thread(
                            target=_background_reap,
                            args=(self, job_id, process),
                            daemon=True,
                            name=f"sentinel-reaper-{job_id[:8]}",
                        ).start()
            except Exception as exc:
                self._append_output(
                    job,
                    "Command wait failed: " + safe_exception_message(exc) + "\n",
                )
                try:
                    process.kill()
                except Exception:
                    pass
                unreaped = process.poll() is None
                if unreaped:
                    threading.Thread(
                        target=_background_reap,
                        args=(self, job_id, process),
                        daemon=True,
                        name=f"sentinel-reaper-{job_id[:8]}",
                    ).start()
                else:
                    returncode = process.returncode

            reader_thread.join(timeout=2)

            with self._lock:
                if returncode is not None:
                    job.returncode = returncode
                elif not unreaped:
                    job.returncode = None
                if not unreaped:
                    job.process = None
                job.finished_at = time.time()
                if timed_out:
                    job.status = "timed_out"
                elif job.cancel_requested:
                    job.status = "cancelled"
                elif returncode == 0:
                    job.status = "succeeded"
                else:
                    job.status = "failed"

    def cancel(self: Any, job_id: str) -> Any:
        with self._lock:
            job = _lookup_job(self, job_id)
            if job is None:
                raise KeyError(job_id)
            process = job.process
            terminal = job.status in web_console.TERMINAL_STATES
        if terminal and process is not None and process.poll() is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            except Exception as exc:
                self._append_output(
                    job,
                    "Unable to terminate retained command process: "
                    + safe_exception_message(exc)
                    + "\n",
                )
            return job
        return original_cancel(self, job_id)

    manager_type.catalog = catalog
    manager_type._prune = prune
    manager_type.snapshot = snapshot
    manager_type.output_since = output_since
    manager_type._run = run
    manager_type.cancel = cancel
    setattr(manager_type, "_sentinel_runtime_hardened", True)
