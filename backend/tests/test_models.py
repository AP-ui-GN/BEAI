"""Model registry: empty list, missing dependencies, memory refusal, and no load at startup."""

import hashlib
from datetime import UTC, datetime

import psutil
import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import repo_root
from backend.app.db.migrate import upgrade_to_head
from backend.app.db.models import Job, RegisteredModel
from backend.app.db.session import make_engine, session_factory
from backend.app.main import create_app
from backend.app.services.models_registry import runtime as runtime_module


def _body(**overrides: object) -> dict:
    payload = {
        "name": "stand-in",
        "version": "0",
        "task": "registry plumbing",
        "source_url": "https://example.invalid/stand-in",
        "licence": "test-only",
        "dependencies": [{"kind": "python", "name": "rdkit"}],
        "hardware": {"min_ram_bytes": 1024, "device": "cpu"},
        "input_format": "none",
        "output_format": "none",
        "known_limitations": "This entry has no weights and no scientific benchmark.",
        "loader_key": "registry_only",
    }
    payload.update(overrides)
    return payload


def test_no_models_is_an_empty_list(client: TestClient) -> None:
    response = client.get("/api/models")
    assert response.status_code == 200
    body = response.json()
    assert body["models"] == []
    hardware = client.get("/api/models/hardware")
    assert hardware.status_code == 200
    report = hardware.json()
    memory = psutil.virtual_memory()
    assert report["ram_total_bytes"] == memory.total
    assert 0 < report["ram_available_bytes"] <= report["ram_total_bytes"]
    assert report["cuda"]["available"] is False
    assert report["cuda"]["reason"]
    assert report["mps"]["available"] is False
    assert report["mps"]["reason"]


def test_registered_model_is_listed_from_the_row(client: TestClient) -> None:
    created = client.post("/api/models", json=_body())
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] == "ready"
    assert body["loaded"] is False
    assert body["weights_loaded"] is False
    assert body["benchmark"] is None
    assert body["training_jobs"] == []
    assert "No benchmark result is stored." in body["card_markdown"]
    assert "test-only" in body["card_markdown"]
    listed = client.get("/api/models").json()["models"]
    assert [item["id"] for item in listed] == [body["id"]]


def test_missing_dependency_disables_the_model_and_leaves_health_up(client: TestClient) -> None:
    created = client.post(
        "/api/models",
        json=_body(
            name="missing-dep",
            dependencies=[{"kind": "python", "name": "beai_module_that_is_not_installed"}],
        ),
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] == "disabled"
    assert "beai_module_that_is_not_installed" in body["status_reason"]
    loaded = client.post(f"/api/models/{body['id']}/load")
    assert loaded.status_code == 503
    assert "beai_module_that_is_not_installed" in loaded.json()["message"]
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/models").status_code == 200


def test_memory_requirement_above_the_machine_is_refused(client: TestClient) -> None:
    total = client.get("/api/models/hardware").json()["ram_total_bytes"]
    declared = total + 1_000_000_000
    created = client.post(
        "/api/models",
        json=_body(name="too-big", hardware={"min_ram_bytes": declared, "device": "cpu"}),
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] == "incompatible"
    assert str(declared) in body["status_reason"]
    assert "exceeds available RAM" in body["status_reason"]
    refused = client.post(f"/api/models/{body['id']}/load")
    assert refused.status_code == 422
    assert str(declared) in refused.json()["message"]
    assert "exceeds available RAM" in refused.json()["message"]
    assert client.get(f"/api/models/{body['id']}").json()["loaded"] is False


def test_startup_does_not_load_a_registered_model(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    upgrade_to_head(settings.resolved_database_url())
    engine = make_engine(settings.resolved_database_url())
    factory = session_factory(engine)
    session = factory()
    session.add(
        RegisteredModel(
            id="11111111-1111-1111-1111-111111111111",
            name="already-there",
            version="1",
            task="registry plumbing",
            source_url="https://example.invalid/already",
            licence="test-only",
            dependencies_json=[{"kind": "python", "name": "rdkit"}],
            hardware_json={"min_ram_bytes": 1024, "device": "cpu"},
            input_format="none",
            output_format="none",
            benchmark_json=None,
            known_limitations="No weights.",
            checksum_sha256=None,
            weights_relative=None,
            loader_key="registry_only",
            created_at=datetime.now(UTC),
        )
    )
    session.commit()
    session.close()
    engine.dispose()
    calls: list[str] = []

    def refuse(row: RegisteredModel) -> dict:
        calls.append(row.id)
        raise AssertionError("startup must not load models")

    monkeypatch.setattr(runtime_module, "invoke_loader", refuse)
    application = create_app(settings)
    with TestClient(application) as client:
        listed = client.get("/api/models").json()["models"]
        assert len(listed) == 1
        assert listed[0]["loaded"] is False
        assert calls == []


def test_load_and_unload_call_the_loader_only_on_load(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    original = runtime_module.invoke_loader

    def wrapped(row: RegisteredModel) -> dict:
        calls.append(row.id)
        return original(row)

    monkeypatch.setattr(runtime_module, "invoke_loader", wrapped)
    created = client.post("/api/models", json=_body(name="loadable"))
    model_id = created.json()["id"]
    loaded = client.post(f"/api/models/{model_id}/load")
    assert loaded.status_code == 200, loaded.text
    assert loaded.json()["status"] == "loaded"
    assert loaded.json()["weights_loaded"] is False
    assert "No weights were loaded." in loaded.json()["load_note"]
    again = client.post(f"/api/models/{model_id}/load")
    assert again.status_code == 200
    assert calls == [model_id]
    unloaded = client.post(f"/api/models/{model_id}/unload")
    assert unloaded.status_code == 200
    assert unloaded.json()["loaded"] is False
    assert unloaded.json()["status"] == "ready"


def test_training_status_comes_from_job_rows(client: TestClient) -> None:
    created = client.post("/api/models", json=_body(name="trainer"))
    model_id = created.json()["id"]
    assert created.json()["training_jobs"] == []
    session = client.app.state.session_factory()
    try:
        session.add(
            Job(
                id="22222222-2222-2222-2222-222222222222",
                kind="model_training",
                status="succeeded",
                progress=1.0,
                cancel_requested=False,
                created_at=datetime.now(UTC),
                started_at=None,
                completed_at=None,
                error_json=None,
                payload_json={"model_id": model_id},
                analysis_id=None,
                structure_id=None,
            )
        )
        session.commit()
    finally:
        session.close()
    listed = client.get(f"/api/models/{model_id}")
    jobs = listed.json()["training_jobs"]
    assert len(jobs) == 1
    assert jobs[0]["id"] == "22222222-2222-2222-2222-222222222222"
    assert jobs[0]["status"] == "succeeded"
    assert jobs[0]["progress"] == 1.0


def test_duplicate_registration_is_rejected(client: TestClient) -> None:
    assert client.post("/api/models", json=_body()).status_code == 201
    again = client.post("/api/models", json=_body())
    assert again.status_code == 422
    assert "already registered" in again.json()["message"]


def test_weight_path_outside_models_is_rejected(client: TestClient) -> None:
    response = client.post("/api/models", json=_body(weights_relative="../pyproject.toml"))
    assert response.status_code == 422
    assert "models/" in response.json()["message"]


def test_checksum_mismatch_refuses_to_activate(client: TestClient) -> None:
    root = repo_root() / "models"
    root.mkdir(parents=True, exist_ok=True)
    path = root / "stand-in-checksum.bin"
    payload = b"not-a-weight-file"
    path.write_bytes(payload)
    try:
        created = client.post(
            "/api/models",
            json=_body(
                name="checksum",
                weights_relative="stand-in-checksum.bin",
                checksum_sha256="0" * 64,
            ),
        )
        assert created.status_code == 201, created.text
        refused = client.post(f"/api/models/{created.json()['id']}/load")
        assert refused.status_code == 422
        assert "checksum" in refused.json()["message"]
        digest = hashlib.sha256(payload).hexdigest()
        matched = client.post(
            "/api/models",
            json=_body(
                name="checksum-ok",
                version="1",
                weights_relative="stand-in-checksum.bin",
                checksum_sha256=digest,
            ),
        )
        assert matched.status_code == 201, matched.text
        loaded = client.post(f"/api/models/{matched.json()['id']}/load")
        assert loaded.status_code == 200, loaded.text
        assert loaded.json()["weights_loaded"] is False
        assert "checksum matched" in loaded.json()["load_note"]
    finally:
        path.unlink(missing_ok=True)
