"""Job create, progress, cancel, and restart recovery."""

import time
import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.db.migrate import upgrade_to_head
from backend.app.db.models import Job
from backend.app.db.session import make_engine, session_factory
from backend.app.main import create_app


def _wait_status(client: TestClient, job_id: str, wanted: set[str], timeout: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    last: dict = {}
    while time.monotonic() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200, response.text
        last = response.json()
        if last["status"] in wanted:
            return last
        time.sleep(0.02)
    raise AssertionError(f"job stayed {last.get('status')}: {last}")


def test_job_reports_progress_then_succeeds(client: TestClient) -> None:
    seen: list[float] = []

    def handler(ctx, payload: dict) -> None:
        for step in range(1, 5):
            if ctx.cancelled():
                return None
            ctx.set_progress(step / 5)
            seen.append(step / 5)
        return None

    client.app.state.jobs.register("progress_probe", handler)
    job = client.app.state.jobs.submit("progress_probe", {})
    body = _wait_status(client, job.id, {"succeeded"})
    assert body["progress"] == 1.0
    assert seen == [0.2, 0.4, 0.6, 0.8]
    listing = client.get("/api/jobs")
    assert listing.status_code == 200
    assert any(item["id"] == job.id for item in listing.json()["jobs"])


def test_cancel_stops_a_running_job(client: TestClient) -> None:
    started = {"ok": False}

    def handler(ctx, payload: dict) -> None:
        ctx.set_progress(0.25)
        started["ok"] = True
        for _ in range(40):
            if ctx.cancelled():
                return None
            time.sleep(0.05)
        ctx.set_progress(1.0)
        return None

    client.app.state.jobs.register("cancel_probe", handler)
    job = client.app.state.jobs.submit("cancel_probe", {})
    deadline = time.monotonic() + 2
    while not started["ok"] and time.monotonic() < deadline:
        time.sleep(0.01)
    assert started["ok"]
    cancelled = client.post(f"/api/jobs/{job.id}/cancel")
    assert cancelled.status_code == 200, cancelled.text
    body = _wait_status(client, job.id, {"cancelled"})
    assert body["cancel_requested"] is True
    assert body["error"]["code"] == "cancelled"
    assert body["analysis_id"] is None


def test_unknown_job_is_404(client: TestClient) -> None:
    response = client.get(f"/api/jobs/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_restart_marks_running_jobs_failed(settings: Settings) -> None:
    upgrade_to_head(settings.resolved_database_url())
    engine = make_engine(settings.resolved_database_url())
    factory = session_factory(engine)
    job_id = str(uuid.uuid4())
    session = factory()
    session.add(
        Job(
            id=job_id,
            kind="progress_probe",
            status="running",
            progress=0.4,
            cancel_requested=False,
            created_at=datetime.now(UTC),
            started_at=datetime.now(UTC),
            completed_at=None,
            error_json=None,
            payload_json={},
            analysis_id=None,
            structure_id=None,
        )
    )
    session.commit()
    session.close()
    with TestClient(create_app(settings)) as restarted:
        body = restarted.get(f"/api/jobs/{job_id}")
    assert body.status_code == 200, body.text
    payload = body.json()
    assert payload["status"] == "failed"
    assert payload["error"]["code"] == "interrupted"
    assert "interrupted" in payload["error"]["message"].lower()
    assert payload["progress"] == 0.4
