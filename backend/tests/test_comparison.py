"""C-alpha superposition. Analytic RMSD uses coordinates written in the test."""

import time

import numpy
import pytest
from fastapi.testclient import TestClient

from backend.app.core.errors import InvalidInput
from backend.app.services.structure.superpose import rigid_rmsd

FIXTURES_NOTE = "backend/tests/fixtures"


def _wait(client: TestClient, job_id: str) -> dict:
    deadline = time.monotonic() + 20
    last: dict = {}
    while time.monotonic() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200, response.text
        last = response.json()
        if last["status"] in {"succeeded", "failed", "cancelled"}:
            return last
        time.sleep(0.02)
    raise AssertionError(last)


def _upload(client: TestClient, name: str, payload: bytes) -> str:
    response = client.post("/api/structures", files={"file": (name, payload, "chemical/x-pdb")})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_rigid_fit_of_a_copy_and_a_rotated_copy_is_near_zero() -> None:
    mobile = numpy.array([[0.0, 0.0, 0.0], [3.0, 0.0, 0.0], [0.0, 4.0, 0.0], [0.0, 0.0, 5.0]])
    rmsd, _rotation, _translation = rigid_rmsd(mobile, mobile.copy())
    assert rmsd == pytest.approx(0.0, abs=1e-6)
    rotation = numpy.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    target = (rotation @ mobile.T).T + numpy.array([8.0, -3.0, 2.5])
    rotated_rmsd, _rotation, _translation = rigid_rmsd(mobile, target)
    assert rotated_rmsd == pytest.approx(0.0, abs=1e-6)
    with pytest.raises(InvalidInput):
        rigid_rmsd(mobile[:2], target[:2])


def test_self_superposition_and_short_chain_refusal(client: TestClient) -> None:
    payload = open("backend/tests/fixtures/1UBQ.pdb", "rb").read()
    structure_id = _upload(client, "1UBQ.pdb", payload)
    created = client.post(
        "/api/structures/compare",
        json={
            "structure_id": structure_id,
            "chain_id": "A",
            "other_structure_id": structure_id,
            "other_chain_id": "A",
        },
    )
    assert created.status_code == 202, created.text
    job = _wait(client, created.json()["id"])
    assert job["status"] == "succeeded", job
    analysis = client.get(f"/api/analyses/{job['analysis_id']}")
    assert analysis.status_code == 200
    result = analysis.json()["result"]
    rmsd = next(item for item in result["measurements"] if item["name"] == "rmsd_ca")
    assert rmsd["value"] == pytest.approx(0.0, abs=1e-6)
    assert rmsd["unit"] == "angstrom"
    count = next(item for item in result["measurements"] if item["name"] == "aligned_residue_count")["value"]
    assert count == 76
    short = _upload(client, "two.pdb", _two_residue_pdb())
    refused = client.post(
        "/api/structures/compare",
        json={
            "structure_id": short,
            "chain_id": "A",
            "other_structure_id": short,
            "other_chain_id": "A",
        },
    )
    assert refused.status_code == 202, refused.text
    failed = _wait(client, refused.json()["id"])
    assert failed["status"] == "failed"
    assert "3" in failed["error"]["message"]
    peptide_bytes = open("backend/tests/fixtures/synthetic_peptide.pdb", "rb").read()
    peptide = _upload(client, "synthetic_peptide.pdb", peptide_bytes)
    different = client.post(
        "/api/structures/compare",
        json={
            "structure_id": structure_id,
            "chain_id": "A",
            "other_structure_id": peptide,
            "other_chain_id": "A",
        },
    )
    assert different.status_code == 202, different.text
    finished = _wait(client, different.json()["id"])
    assert finished["status"] == "succeeded", finished


def _two_residue_pdb() -> bytes:
    text = """\
ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N
ATOM      2  CA  ALA A   1       1.000   0.000   0.000  1.00  0.00           C
ATOM      3  C   ALA A   1       2.000   0.000   0.000  1.00  0.00           C
ATOM      4  O   ALA A   1       2.000   1.000   0.000  1.00  0.00           O
ATOM      5  N   ALA A   2       3.000   0.000   0.000  1.00  0.00           N
ATOM      6  CA  ALA A   2       4.000   0.000   0.000  1.00  0.00           C
ATOM      7  C   ALA A   2       5.000   0.000   0.000  1.00  0.00           C
ATOM      8  O   ALA A   2       5.000   1.000   0.000  1.00  0.00           O
END
"""
    return text.encode()
