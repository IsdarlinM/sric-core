from fastapi.testclient import TestClient
from sric.api import create_app
from sric.jobs import JobEngine


def test_job_event_sse_once(tmp_path):
    jobs = JobEngine(tmp_path)
    jobs.create("demo")
    client = TestClient(create_app(tmp_path))
    response = client.get("/jobs/events?once=true")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: job" in response.text
    assert "created" in response.text
