"""Pocket benchmark recorded on 2026-10-13 from the frozen detector.

Distances are angstroms from the top-3 pocket centroid nearest the ligand
heavy-atom centroid. Recovery is the fraction of polymer residues with a
heavy atom within 4.0 angstrom of the ligand that also line that pocket.
The held-out rows were not used to choose parameters.
"""

import hashlib
import time
from pathlib import Path

from Bio.PDB import PDBParser
from fastapi.testclient import TestClient

from backend.app.services.structure.ccd import component_table
from backend.app.services.structure.pockets import detect_pockets, score_ligand, select_ligand
from backend.app.services.structure.residues import residue_records

POCKETS = Path(__file__).parent / "fixtures" / "pockets"

# split, pdb id, sha256, ligand, distance, success, recovery
RECORDED = [
    ("tuning", "3PTB", "288f7954d4d013fa8eab3808e1037e2958e2dcd12c9eca65a3f1014404a9f9a2", "BEN", 0.565, True, 1.0),
    ("tuning", "1STP", "6fbb3d5c324e717fe7284703426e74ea58191431720daab1b2faa0bbb6430f30", "BTN", 2.245, True, 0.75),
    ("tuning", "1HSG", "d430675c358060808ef614002cfdcfcfa824714d89f1240adf5749d2ba60fed2", "MK1", 0.675, True, 1.0),
    ("tuning", "1FKF", "0f1773ef6f462130abf13cb6b62a4c51c83b265c005c8d9c37c8dc0836fecd27", "FK5", 5.46, False, 0.643),
    ("tuning", "2PK4", "bcefe7418b70527d831ce78bce3eedf772ad923d7deea972ac33f2104844f894", "ACA", 12.835, False, 0.0),
    (
        "held_out",
        "1AQ1",
        "6ef163ddcf3e3298b6c0982dc8c06e89c61b9d6705fb34ced7e142a0313d764d",
        "STU",
        2.111,
        True,
        1.0,
    ),
    (
        "held_out",
        "1TLP",
        "cb14c3e9b3b42589cafe5c3f33c1cf1e8cb6125cb3fefbb19804617cdcf7d258",
        "RDF",
        4.595,
        False,
        0.933,
    ),
    (
        "held_out",
        "2GBP",
        "4b16aa506667a05822696cdbc0b7a4de6872778c0af341aee5d6a65e425087df",
        "BGC",
        2.878,
        True,
        1.0,
    ),
    (
        "held_out",
        "4DFR",
        "57a68d20dc3e7cab4278f4b7006cef0ec0db7e24771bc1c38f4f436668e794e8",
        "MTX",
        5.388,
        False,
        0.938,
    ),
    (
        "held_out",
        "1DWD",
        "c46b204df18e98d6407c086d45821f58465e37b8d70efd421d195ec95268732e",
        "MID",
        2.892,
        True,
        0.722,
    ),
]


def _score(pdb_id: str) -> tuple[str, float, bool, float]:
    path = POCKETS / f"{pdb_id}.pdb"
    structure = PDBParser(QUIET=True).get_structure(pdb_id, str(path))
    residues, _warnings = residue_records(next(structure.get_models()), component_table())
    detected = detect_pockets(residues)
    ligand = select_ligand(residues)
    assert ligand is not None
    scored = score_ligand(detected["pockets"], residues, ligand)
    return ligand.name, float(scored["distance_angstrom"]), bool(scored["success"]), float(scored["recovery"])


def test_recorded_benchmark_still_matches() -> None:
    held_out_hits = 0
    for split, pdb_id, digest, ligand, distance, success, recovery in RECORDED:
        path = POCKETS / f"{pdb_id}.pdb"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
        found_ligand, found_distance, found_success, found_recovery = _score(pdb_id)
        assert found_ligand == ligand
        assert found_distance == pytest_approx(distance)
        assert found_success is success
        assert found_recovery == pytest_approx(recovery)
        if split == "held_out" and found_success:
            held_out_hits += 1
    assert held_out_hits == 3


def test_pocket_job_labels_the_detector_and_skips_fpocket(client: TestClient) -> None:
    payload = (POCKETS / "3PTB.pdb").read_bytes()
    uploaded = client.post("/api/structures", files={"file": ("3PTB.pdb", payload, "chemical/x-pdb")})
    assert uploaded.status_code == 201, uploaded.text
    created = client.post(f"/api/structures/{uploaded.json()['id']}/pockets")
    assert created.status_code == 202, created.text
    deadline = time.monotonic() + 30
    body: dict = {}
    while time.monotonic() < deadline:
        response = client.get(f"/api/jobs/{created.json()['id']}")
        body = response.json()
        if body["status"] in {"succeeded", "failed", "cancelled"}:
            break
        time.sleep(0.05)
    assert body["status"] == "succeeded", body
    assert body["progress"] == 1.0
    analysis = client.get(f"/api/analyses/{body['analysis_id']}")
    result = analysis.json()["result"]
    label = next(item["value"] for item in result["measurements"] if item["name"] == "pocket_method_label")
    assert "3 of 5" in label
    assert "not a general" in label.lower() or "Not a general" in label
    assert any(item["stage"] == "fpocket" for item in result["skipped_stages"])
    ligand = next(item["value"] for item in result["measurements"] if item["name"] == "detected_ligand")
    assert ligand["resname"] == "BEN"


def pytest_approx(value: float):
    import pytest

    return pytest.approx(value, abs=0.001)
