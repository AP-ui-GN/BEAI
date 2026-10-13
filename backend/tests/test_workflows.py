"""Workflow provenance, resume, skipped docking, and citation checks."""

import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.core.errors import InvalidInput
from backend.app.db.migrate import upgrade_to_head
from backend.app.main import create_app
from backend.app.services.workflows.execute import check_citations


def test_workflow_runs_overview_and_descriptors(client: TestClient) -> None:
    peptide = open("backend/tests/fixtures/synthetic_peptide.pdb", "rb").read()
    uploaded = client.post("/api/structures", files={"file": ("synthetic_peptide.pdb", peptide, "chemical/x-pdb")})
    assert uploaded.status_code == 201, uploaded.text
    created = client.post(
        "/api/workflows",
        json={
            "name": "overview-and-ethanol",
            "steps": [
                {
                    "id": "overview",
                    "service": "structure_overview",
                    "parameters": {"structure_id": uploaded.json()["id"]},
                },
                {
                    "id": "compound",
                    "service": "compound_descriptors",
                    "parameters": {"smiles": "CCO"},
                },
            ],
        },
    )
    assert created.status_code == 201, created.text
    result = created.json()["result"]
    overview = result["details"]["steps"]["overview"]
    compound = result["details"]["steps"]["compound"]
    assert overview["status"] == "succeeded"
    assert any(item["name"] == "residue_count_observed_polymer" for item in overview["output"]["measurements"])
    assert compound["status"] == "succeeded"
    assert compound["output"]["canonical_smiles"] == "CCO"
    assert compound["output"]["origin"] == "calculated"
    assert result["reproducibility"]["config_hash"]


def test_resume_skips_a_succeeded_step(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import backend.app.services.workflows.execute as execute

    calls = {"n": 0}
    original = execute._run_step

    def flaky(service, parameters, session, settings):
        if service == "compound_descriptors":
            calls["n"] += 1
            if calls["n"] == 1:
                raise InvalidInput("first attempt failed")
        return original(service, parameters, session, settings)

    monkeypatch.setattr(execute, "_run_step", flaky)
    peptide = open("backend/tests/fixtures/synthetic_peptide.pdb", "rb").read()
    uploaded = client.post("/api/structures", files={"file": ("synthetic_peptide.pdb", peptide, "chemical/x-pdb")})
    body = {
        "name": "resume",
        "steps": [
            {"id": "overview", "service": "structure_overview", "parameters": {"structure_id": uploaded.json()["id"]}},
            {
                "id": "compound",
                "service": "compound_descriptors",
                "parameters": {"smiles": "CCO"},
                "depends_on": ["overview"],
            },
        ],
    }
    first = client.post("/api/workflows", json=body)
    assert first.status_code == 201, first.text
    assert first.json()["result"]["details"]["steps"]["compound"]["status"] == "failed"
    resumed = client.post("/api/workflows", json={**body, "resume_from": first.json()["id"]})
    assert resumed.status_code == 201, resumed.text
    steps = resumed.json()["result"]["details"]["steps"]
    assert steps["overview"]["status"] == "succeeded"
    assert steps["compound"]["status"] == "succeeded"
    assert calls["n"] == 2


def test_missing_vina_skips_docking_and_dependents(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.app.services.workflows.execute.shutil.which", lambda _name: None)
    created = client.post(
        "/api/workflows",
        json={
            "name": "skip-docking",
            "steps": [
                {"id": "dock", "service": "docking", "parameters": {}},
                {
                    "id": "after",
                    "service": "compound_descriptors",
                    "parameters": {"smiles": "CCO"},
                    "depends_on": ["dock"],
                },
            ],
        },
    )
    assert created.status_code == 201, created.text
    steps = created.json()["result"]["details"]["steps"]
    assert steps["dock"]["status"] == "skipped"
    assert "Vina" in steps["dock"]["reason"]
    assert steps["after"]["status"] == "skipped"
    assert any(item["stage"] == "dock" for item in created.json()["result"]["skipped_stages"])


def test_llm_is_off_by_default_and_citations_must_exist(client: TestClient, tmp_path) -> None:
    refused = client.post("/api/workflows/summarize", json={"summary": "See [PMID:1].", "retrieved_ids": ["PMID:1"]})
    assert refused.status_code == 503
    assert "off" in refused.json()["message"]
    check_citations("See [PMID:1].", {"PMID:1"})
    with pytest.raises(InvalidInput, match="PMID:9"):
        check_citations("See [PMID:9].", {"PMID:1"})
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'beai.sqlite'}",
        storage_dir=tmp_path / "structures",
        register_builtins=False,
        llm_enabled=True,
    )
    upgrade_to_head(settings.resolved_database_url())
    with TestClient(create_app(settings)) as enabled:
        accepted = enabled.post(
            "/api/workflows/summarize",
            json={"summary": "See [PMID:1].", "retrieved_ids": ["PMID:1"]},
        )
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["label"] == "ml_generated"
        rejected = enabled.post(
            "/api/workflows/summarize",
            json={"summary": "See [PMID:9].", "retrieved_ids": ["PMID:1"]},
        )
        assert rejected.status_code == 422
