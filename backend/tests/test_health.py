"""Health reports live probes. Missing optional tools are unavailable, not guessed."""

from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.main import create_app

CAPABILITIES = ("rdkit", "mkdssp", "vina", "openmm", "pytorch", "gpu")


def test_health_returns_real_status(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == "0.1.0"
    # No Alembic scripts exist yet, so the database cannot be at a migration head.
    assert body["status"] == "degraded"
    assert body["database"]["connected"] is True
    assert body["database"]["revision"] is None
    assert body["database"]["head"] is None
    assert "alembic_version" in body["database"]["reason"]
    assert body["storage"]["writable"] is True
    assert body["storage"]["reason"] is None
    assert "Traceback" not in response.text
    assert response.headers["x-request-id"]


def test_optional_tools_are_reported_unavailable(client: TestClient) -> None:
    capabilities = client.get("/api/health").json()["capabilities"]
    assert set(capabilities) == set(CAPABILITIES)
    for name in CAPABILITIES:
        status = capabilities[name]
        assert status["available"] is False
        assert status["version"] is None
        assert isinstance(status["reason"], str) and status["reason"]
    assert "not installed" in capabilities["rdkit"]["reason"]
    assert "not on PATH" in capabilities["mkdssp"]["reason"]
    assert "not on PATH" in capabilities["vina"]["reason"]
    assert "not installed" in capabilities["openmm"]["reason"]
    assert "not installed" in capabilities["pytorch"]["reason"]
    assert "nvidia-smi" in capabilities["gpu"]["reason"]


def test_unwritable_storage_is_degraded(tmp_path: Path) -> None:
    storage = tmp_path / "locked-storage"
    storage.mkdir()
    storage.chmod(0o500)
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'beai.sqlite'}",
        storage_dir=storage,
        cors_origins="http://127.0.0.1:8732",
    )
    try:
        with TestClient(create_app(settings)) as client:
            body = client.get("/api/health").json()
    finally:
        storage.chmod(0o700)
    assert body["storage"]["writable"] is False
    assert body["storage"]["reason"]
    assert body["status"] == "degraded"
    assert str(storage) not in str(body)


def test_unknown_route_has_no_traceback(client: TestClient) -> None:
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    assert "Traceback" not in response.text
