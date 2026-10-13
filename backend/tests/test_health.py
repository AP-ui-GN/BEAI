"""Health reports live probes. A missing optional tool is unavailable, not guessed."""

import shutil
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
    assert body["status"] == "ok"
    assert body["database"]["connected"] is True
    assert body["database"]["revision"] == body["database"]["head"] == "0003_sequences"
    assert body["database"]["reason"] is None
    assert body["storage"]["writable"] is True
    assert body["storage"]["reason"] is None
    assert "Traceback" not in response.text
    assert response.headers["x-request-id"]


def test_optional_tools_match_this_machine(client: TestClient) -> None:
    capabilities = client.get("/api/health").json()["capabilities"]
    assert set(capabilities) == set(CAPABILITIES)
    for status in capabilities.values():
        assert set(status) == {"available", "version", "reason"}
        if status["available"]:
            assert status["reason"] is None
            assert status["version"]
        else:
            assert status["version"] is None
            assert isinstance(status["reason"], str) and status["reason"]
    assert capabilities["rdkit"]["available"] is False
    assert "not installed" in capabilities["rdkit"]["reason"]
    assert capabilities["vina"]["available"] is False
    assert "not on PATH" in capabilities["vina"]["reason"]
    assert capabilities["openmm"]["available"] is False
    assert capabilities["pytorch"]["available"] is False
    assert "nvidia-smi" in capabilities["gpu"]["reason"]
    mkdssp_present = shutil.which("mkdssp") is not None or shutil.which("dssp") is not None
    assert capabilities["mkdssp"]["available"] is mkdssp_present
    if mkdssp_present:
        assert "4.2.2" in str(capabilities["mkdssp"]["version"])
    else:
        assert "not on PATH" in capabilities["mkdssp"]["reason"]


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
