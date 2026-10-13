"""Vina parser, a real short docking run, cancellation, and ranking."""

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.services.docking.parse import parse_vina_pdbqt
from backend.app.services.docking.ranking import pareto_flags

FIXTURES = Path(__file__).parent / "fixtures"
VINA = FIXTURES / "vina" / "3ptb_ben_seed1.pdbqt"


def _cactvs_canonical(path: Path) -> str:
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "SMILES_CANONICAL" in line and "CACTVS" in line:
            return line.split('"')[1]
    raise AssertionError("CACTVS canonical SMILES was not in the component file")


def test_parser_scores_match_the_captured_vina_file() -> None:
    text = VINA.read_text(encoding="utf-8")
    parsed = parse_vina_pdbqt(text)
    remarks = []
    for line in text.splitlines():
        if line.startswith("REMARK VINA RESULT:"):
            parts = line.split()
            remarks.append((float(parts[-3]), float(parts[-2]), float(parts[-1])))
    assert len(parsed) == len(remarks) == 3
    for mode, remark in zip(parsed, remarks, strict=True):
        assert mode["affinity_kcal_mol"] == remark[0]
        assert mode["rmsd_lower_bound"] == remark[1]
        assert mode["rmsd_upper_bound"] == remark[2]
    assert "binding affinity" not in str(parsed)


def test_vina_hidden_returns_503(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.app.services.docking.job.shutil.which", lambda _name: None)
    response = client.post(
        "/api/docking",
        json={"structure_id": "missing", "ligand_smiles": "CCO", "center": [0, 0, 0]},
    )
    assert response.status_code == 503
    assert "Vina" in response.json()["message"]
    peptide = (FIXTURES / "synthetic_peptide.pdb").read_bytes()
    uploaded = client.post("/api/structures", files={"file": ("synthetic_peptide.pdb", peptide, "chemical/x-pdb")})
    assert uploaded.status_code == 201


def test_real_benzamidine_redock_and_same_seed_spread(client: TestClient) -> None:
    # Same seed on Vina 1.2.5 was not bit-identical (0.006 kcal/mol apart on 2026-10-13).
    # The tolerance below is the acceptance window for that spread.
    tolerance_kcal_mol = 0.05
    smiles = _cactvs_canonical(FIXTURES / "vina" / "BEN.cif")
    payload = (FIXTURES / "pockets" / "3PTB.pdb").read_bytes()
    uploaded = client.post("/api/structures", files={"file": ("3PTB.pdb", payload, "chemical/x-pdb")})
    assert uploaded.status_code == 201, uploaded.text
    structure_id = uploaded.json()["id"]
    scores = []
    for _ in range(2):
        created = client.post(
            "/api/docking",
            json={
                "structure_id": structure_id,
                "ligand_smiles": smiles,
                "ligand_resname": "BEN",
                "exhaustiveness": 4,
                "num_modes": 1,
                "seed": 1,
            },
        )
        assert created.status_code == 202, created.text
        job = _wait(client, created.json()["id"])
        assert job["status"] == "succeeded", job
        analysis = client.get(f"/api/analyses/{job['analysis_id']}")
        result = analysis.json()["result"]
        score = next(item["value"] for item in result["measurements"] if item["name"] == "docking_score")
        assert result["measurements"][0]["method"].lower().find("not an experimental") != -1 or any(
            "not an experimental affinity" in item["method"] for item in result["measurements"]
        )
        scores.append(score)
    assert abs(scores[0] - scores[1]) <= tolerance_kcal_mol


def test_cancel_kills_a_stand_in_process(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def sleep_argv(*_args, **_kwargs):
        return ["sleep", "30"]

    monkeypatch.setattr("backend.app.services.docking.runner.vina_argv", sleep_argv)
    payload = (FIXTURES / "pockets" / "3PTB.pdb").read_bytes()
    uploaded = client.post("/api/structures", files={"file": ("3PTB.pdb", payload, "chemical/x-pdb")})
    smiles = _cactvs_canonical(FIXTURES / "vina" / "BEN.cif")
    created = client.post(
        "/api/docking",
        json={
            "structure_id": uploaded.json()["id"],
            "ligand_smiles": smiles,
            "ligand_resname": "BEN",
            "exhaustiveness": 4,
            "num_modes": 1,
            "seed": 1,
        },
    )
    assert created.status_code == 202, created.text
    time.sleep(1.5)
    cancelled = client.post(f"/api/jobs/{created.json()['id']}/cancel")
    assert cancelled.status_code == 200
    job = _wait(client, created.json()["id"])
    assert job["status"] == "cancelled", job


def test_pareto_flags_match_a_hand_worked_table() -> None:
    rows = [
        {"score": -8.0, "activity": 10.0},
        {"score": -7.0, "activity": 5.0},
        {"score": -6.0, "activity": 12.0},
    ]
    # Lower docking score and lower activity value are better in this table.
    flags = pareto_flags(rows, ["score", "activity"], {"score": "min", "activity": "min"})
    assert flags == [True, True, False]


def _wait(client: TestClient, job_id: str) -> dict:
    deadline = time.monotonic() + 120
    last: dict = {}
    while time.monotonic() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        last = response.json()
        if last["status"] in {"succeeded", "failed", "cancelled"}:
            return last
        time.sleep(0.1)
    raise AssertionError(last)
