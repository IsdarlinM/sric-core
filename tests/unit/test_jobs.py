import pytest
from sric.jobs import JobEngine, JobStatus


def test_jobs_transition_and_cancel(tmp_path):
    e = JobEngine(tmp_path)
    job = e.create("demo")
    assert job.status == JobStatus.QUEUED
    e.transition(job.job_id, JobStatus.RUNNING, progress=0.2)
    cancelling = e.request_cancel(job.job_id)
    assert cancelling.status == JobStatus.CANCELLING
    cancelled = e.transition(job.job_id, JobStatus.CANCELLED)
    assert cancelled.status == JobStatus.CANCELLED
    with pytest.raises(ValueError):
        e.transition(job.job_id, JobStatus.RUNNING)
