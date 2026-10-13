"""Solubility plumbing on a synthetic table, plus the checksummed Delaney run."""

import time
from pathlib import Path

import numpy
import pytest
from fastapi.testclient import TestClient
from rdkit import Chem

from backend.app.services.properties.constants import (
    APPLICABILITY_MAX_TANIMOTO,
    DATASET_SHA256,
    REPRODUCTION_TOLERANCE,
    SPLIT_SEED,
)
from backend.app.services.properties.train import (
    read_table,
    regression_metrics,
    save_artifact,
    scaffold_split,
    train_models,
    verify_dataset,
)

# Settings were fixed before any Delaney test metric: seed 20261013, test fraction 0.2,
# Ridge alpha 1, Morgan radius 2 and 2048 bits, applicability Tanimoto 0.3,
# bootstrap 1000, GCN hidden 32, 20 epochs, learning rate 0.01.

SYNTHETIC = [
    ("CCO", 1.2),
    ("CCCO", 0.8),
    ("CCCCO", 0.4),
    ("CC(C)O", 0.9),
    ("CCN", 0.7),
    ("CC(=O)O", 1.1),
    ("c1ccccc1", -2.0),
    ("c1ccccc1O", -1.2),
    ("c1ccccc1N", -1.0),
    ("c1ccncc1", -0.8),
    ("C1CCCCC1", -0.2),
    ("CCCCCC", -0.4),
]


def _rows(pairs: list[tuple[str, float]]):
    rows = []
    for smiles, measured in pairs:
        mol = Chem.MolFromSmiles(smiles)
        assert mol is not None
        rows.append({"smiles": smiles, "measured": measured, "scaffold": smiles, "mol": mol})
    return rows


def test_same_seed_reproduces_ridge_coefficients() -> None:
    rows = _rows(SYNTHETIC)
    train, test = scaffold_split(rows, seed=SPLIT_SEED)
    first = train_models(rows, train, test, seed=SPLIT_SEED)
    second = train_models(rows, train, test, seed=SPLIT_SEED)
    assert numpy.allclose(first["descriptor"]["coef"], second["descriptor"]["coef"], atol=REPRODUCTION_TOLERANCE)
    fingerprint_gap = abs(first["fingerprint"]["metrics"]["rmse"] - second["fingerprint"]["metrics"]["rmse"])
    assert fingerprint_gap <= REPRODUCTION_TOLERANCE
    assert abs(first["gnn"]["metrics"]["rmse"] - second["gnn"]["metrics"]["rmse"]) <= REPRODUCTION_TOLERANCE
    assert first["descriptor"]["metrics"]["r2"] is not None


def test_prediction_is_labelled_and_domain_follows_the_threshold(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = _rows(SYNTHETIC)
    train, test = scaffold_split(rows, seed=SPLIT_SEED)
    trained = train_models(rows, train, test, seed=SPLIT_SEED)
    save_artifact(trained, tmp_path)
    monkeypatch.setattr("backend.app.services.properties.predict.artifact_dir", lambda: tmp_path)
    created = client.post(
        "/api/models",
        json={
            "name": "synthetic-solubility",
            "version": "0",
            "task": "aqueous solubility, log10 mol per litre",
            "source_url": "https://example.invalid/synthetic-solubility",
            "licence": "test-only",
            "dependencies": [],
            "hardware": {"min_ram_bytes": 1024, "device": "cpu"},
            "input_format": "SMILES",
            "output_format": "predicted log10 solubility",
            "known_limitations": "Synthetic rows only. Not experimental solubility.",
            "loader_key": "solubility",
            "weights_relative": "esol/gnn.safetensors",
        },
    )
    assert created.status_code == 201, created.text
    model_id = created.json()["id"]
    predicted = client.post(f"/api/models/{model_id}/predict", json={"smiles": "CCO"})
    assert predicted.status_code == 201, predicted.text
    result = predicted.json()["result"]
    assert result["details"]["label"] == "not experimental"
    assert all(item["origin"] == "ml_prediction" for item in result["measurements"])
    assert all("not experimental" in item["method"] for item in result["measurements"])
    assert "measured" not in result["measurements"][0]["name"]
    max_tanimoto = result["details"]["max_tanimoto_to_training"]
    assert result["details"]["in_applicability_domain"] is (max_tanimoto >= APPLICABILITY_MAX_TANIMOTO)
    fingerprint = next(item for item in result["measurements"] if item["name"] == "fingerprint_ridge_log_solubility")
    assert fingerprint["uncertainty"] is not None


def test_bad_delaney_checksum_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "delaney-processed.csv"
    path.write_text("smiles,measured log solubility in mols per litre\nCCO,1\n", encoding="utf-8")
    with pytest.raises(Exception, match="checksum"):
        verify_dataset(path)


def test_training_job_can_be_cancelled(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import backend.app.services.properties.job as job_module

    def slow(*_args, **_kwargs):
        time.sleep(1.5)
        return {"cancelled": True}

    monkeypatch.setattr(job_module, "verify_dataset", lambda _path: None)
    extra = {"scaffold": "other", "measured": 0.0, "mol": Chem.MolFromSmiles("C"), "smiles": "C"}
    monkeypatch.setattr(job_module, "read_table", lambda _path: (_rows(SYNTHETIC[:8]) + [extra], 0))
    monkeypatch.setattr(job_module, "train_models", slow)
    created = client.post(
        "/api/models",
        json={
            "name": "cancel-solubility",
            "version": "0",
            "task": "aqueous solubility, log10 mol per litre",
            "source_url": "https://example.invalid/cancel-solubility",
            "licence": "test-only",
            "dependencies": [],
            "hardware": {"min_ram_bytes": 1024, "device": "cpu"},
            "input_format": "SMILES",
            "output_format": "predicted log10 solubility",
            "known_limitations": "Cancellation plumbing.",
            "loader_key": "solubility",
        },
    )
    assert created.status_code == 201, created.text
    started = client.post(f"/api/models/{created.json()['id']}/train")
    assert started.status_code == 202, started.text
    time.sleep(0.2)
    cancelled = client.post(f"/api/jobs/{started.json()['id']}/cancel")
    assert cancelled.status_code == 200
    deadline = time.monotonic() + 10
    status = cancelled.json()["status"]
    while status not in {"succeeded", "failed", "cancelled"} and time.monotonic() < deadline:
        time.sleep(0.1)
        status = client.get(f"/api/jobs/{started.json()['id']}").json()["status"]
    assert status == "cancelled"


@pytest.mark.network
def test_esol_held_out_metrics(capsys: pytest.CaptureFixture[str]) -> None:
    from backend.app.services.properties.train import dataset_path

    path = dataset_path()
    verify_dataset(path)
    assert DATASET_SHA256
    rows, dropped = read_table(path)
    train, test = scaffold_split(rows, seed=SPLIT_SEED)
    trained = train_models(rows, train, test, seed=SPLIT_SEED)
    again = train_models(rows, train, test, seed=SPLIT_SEED)
    metrics = {
        "dropped_rows": dropped,
        "train_count": len(train),
        "test_count": len(test),
        "descriptor_ridge": trained["descriptor"]["metrics"],
        "fingerprint_ridge": trained["fingerprint"]["metrics"],
        "gcn": trained["gnn"]["metrics"],
    }
    print("ESOL_METRICS", metrics)
    for name in ("descriptor_ridge", "fingerprint_ridge", "gcn"):
        assert metrics[name]["rmse"] > 0
        assert metrics[name]["mae"] > 0
        assert metrics[name]["r2"] is not None
    descriptor_gap = abs(trained["descriptor"]["metrics"]["rmse"] - again["descriptor"]["metrics"]["rmse"])
    assert descriptor_gap <= REPRODUCTION_TOLERANCE
    assert abs(trained["gnn"]["metrics"]["rmse"] - again["gnn"]["metrics"]["rmse"]) <= REPRODUCTION_TOLERANCE
    assert regression_metrics(numpy.asarray([0.0, 1.0]), numpy.asarray([0.0, 1.0]))["rmse"] == 0.0
