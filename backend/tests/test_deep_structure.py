"""Deeper structure sections on the synthetic peptide and 1UBQ.

SASA tolerance was chosen before comparing the 1UBQ totals. Biopython
Shrake-Rupley (100 points, its default radii) and Biotite ``sasa`` (100
points, ProtOr radii) do not share a radii table, so the window is 20 percent
of the Biopython total.
"""

import shutil
from pathlib import Path

import biotite.structure as struc
import biotite.structure.io.pdb as pdb
import numpy
import pytest
from fastapi.testclient import TestClient

from backend.app.services.structure.secondary import assign_secondary_structure

FIXTURES = Path(__file__).parent / "fixtures"
# Pre-registered before the 1UBQ Shrake-Rupley versus Biotite comparison.
SASA_RELATIVE_TOLERANCE = 0.20


def _measurement(result: dict, name: str) -> dict:
    matches = [item for item in result["measurements"] if item["name"] == name]
    assert len(matches) == 1, name
    return matches[0]


def _analyze(client: TestClient, filename: str) -> dict:
    payload = (FIXTURES / filename).read_bytes()
    media = "chemical/x-mmcif" if filename.endswith("cif") else "chemical/x-pdb"
    uploaded = client.post("/api/structures", files={"file": (filename, payload, media)})
    assert uploaded.status_code == 201, uploaded.text
    created = client.post(
        f"/api/structures/{uploaded.json()['id']}/analyses",
        json={"kind": "structure_overview"},
    )
    assert created.status_code == 201, created.text
    return created.json()


def test_1ubq_secondary_structure_records_the_algorithm_and_file_ranges(client: TestClient) -> None:
    body = _analyze(client, "1UBQ.pdb")
    result = body["result"]
    methods = {item["name"]: item for item in result["methods"]}
    assert methods["secondary_structure"]["parameters"]["algorithm"] == "DSSP"
    # HELIX records read from backend/tests/fixtures/1UBQ.pdb:
    # H1 ILE A 23 to GLU A 34 class 1; H2 LEU A 56 to TYR A 59 class 5.
    helices = result["details"]["secondary_structure"]["file_annotations"]["helices"]
    assert [(item["start_resseq"], item["end_resseq"], item["helix_class"]) for item in helices] == [
        (23, 34, 1),
        (56, 59, 5),
    ]
    disagreement = _measurement(result, "secondary_structure_disagreement")["value"]
    assert disagreement["file_helix_ranges"] == 2
    assert disagreement["file_sheet_ranges"] == 5
    assert "not the same" in _measurement(result, "secondary_structure_disagreement")["method"]
    assert _measurement(result, "sasa_total")["unit"] == "angstrom^2"
    assert _measurement(result, "sasa_total")["value"] > 0
    residues = client.get(f"/api/structures/{body['structure_id']}/residues?chain=A")
    assert residues.status_code == 200, residues.text
    rows = residues.json()["residues"]
    polymer = [row for row in rows if row["kind"] == "polymer"]
    assert len(polymer) == 76
    assert polymer[0]["phi_degrees"] is None
    assert polymer[1]["phi_degrees"] is not None


def test_1ubq_sasa_agrees_with_biotite_within_the_preregistered_window(client: TestClient) -> None:
    result = _analyze(client, "1UBQ.pdb")["result"]
    reported = _measurement(result, "sasa_total")["value"]
    pdb_file = pdb.PDBFile.read(FIXTURES / "1UBQ.pdb")
    array = pdb_file.get_structure(model=1, altloc="first", extra_fields=["b_factor"])
    # Same solvent exclusion as the service: drop water residue names before SASA.
    array = array[array.res_name != "HOH"]
    areas = struc.sasa(array, probe_radius=1.4, point_number=100, vdw_radii="ProtOr")
    assert areas.size and not numpy.isnan(areas).any()
    independent = float(areas.sum())
    assert abs(reported - independent) / reported <= SASA_RELATIVE_TOLERANCE


def test_psea_is_used_when_mkdssp_is_hidden(monkeypatch: pytest.MonkeyPatch) -> None:
    from Bio.PDB import PDBParser

    monkeypatch.setattr(shutil, "which", lambda _name: None)
    structure = PDBParser(QUIET=True).get_structure("x", str(FIXTURES / "1UBQ.pdb"))
    model = next(structure.get_models())
    _codes, method, warnings = assign_secondary_structure(model, FIXTURES / "1UBQ.pdb", [])
    assert method["parameters"]["algorithm"] == "P-SEA"
    assert any("P-SEA" in warning for warning in warnings)
