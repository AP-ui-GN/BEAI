"""CapabilityUnavailable maps to HTTP 503. Health still answers when tools are missing."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.errors import register_exception_handlers
from backend.app.core.errors import CapabilityUnavailable


def test_capability_unavailable_returns_503_without_traceback() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/api/needs-rdkit")
    def needs_rdkit() -> dict[str, str]:
        raise CapabilityUnavailable("RDKit is not installed")

    with TestClient(app) as client:
        denied = client.get("/api/needs-rdkit")
        missing = client.get("/api/missing")

    assert denied.status_code == 503
    assert denied.json() == {
        "code": "capability_unavailable",
        "message": "RDKit is not installed",
    }
    assert "Traceback" not in denied.text
    assert missing.status_code == 404


def test_health_still_works_when_optional_tools_are_absent(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["capabilities"]["rdkit"]["available"] is False
