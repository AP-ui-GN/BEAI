"""structure_overview against a hand-built peptide and RCSB entries.

RCSB counts were copied into rcsb_entry_snapshot.json from the Data API on
2026-10-11. They are not taken from the service under test.
"""

import json
import math
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.app.services.structure import overview as overview_module
from backend.app.services.structure.ccd import component_table

FIXTURES = Path(__file__).parent / "fixtures"
SNAPSHOT = json.loads((FIXTURES / "rcsb_entry_snapshot.json").read_text(encoding="utf-8"))


def _measurement(result: dict, name: str) -> dict:
    matches = [item for item in result["measurements"] if item["name"] == name]
    assert len(matches) == 1, name
    return matches[0]


def _analyze(client: TestClient, filename: str, payload: bytes) -> dict:
    uploaded = client.post("/api/structures", files={"file": (filename, payload, "chemical/x-pdb")})
    assert uploaded.status_code == 201, uploaded.text
    created = client.post(
        f"/api/structures/{uploaded.json()['id']}/analyses",
        json={"kind": "structure_overview"},
    )
    assert created.status_code == 201, created.text
    return created.json()


def test_alanine_required_heavy_atoms_match_the_component_file() -> None:
    # Heavy atoms with pdbx_leaving_atom_flag N in ALA.cif, read 2026-10-11:
    # N, CA, C, O, CB. OXT is flagged Y and is not required.
    alanine = component_table().get("ALA")
    assert alanine is not None
    assert alanine.one_letter == "A"
    assert set(alanine.heavy_atoms) == {"N", "CA", "C", "O", "CB"}


def test_synthetic_peptide_matches_hand_values(client: TestClient) -> None:
    payload = (FIXTURES / "synthetic_peptide.pdb").read_bytes()
    body = _analyze(client, "synthetic_peptide.pdb", payload)
    result = body["result"]
    assert result["status"] == "succeeded"
    assert result["evidence"] == []
    assert result["inputs"][0]["sha256"]
    assert {item["origin"] for item in result["measurements"]} <= {
        "experimental_record",
        "database_reported",
        "calculated",
        "ml_prediction",
        "user_supplied",
    }

    chains = _measurement(result, "chains")["value"]
    assert chains[0]["observed_polymer_residue_count"] == 3
    assert chains[0]["seqres_residue_count"] == 4
    assert chains[0]["water_residue_count"] == 1
    assert _measurement(result, "water_residue_count")["value"] == 1
    assert _measurement(result, "ligand_inventory")["value"] == []

    missing = _measurement(result, "missing_residues")["value"]
    assert missing == [
        {
            "chain_id": "A",
            "resname": "GLY",
            "resseq": 3,
            "icode": "",
            "model": None,
            "source": "REMARK 465",
            "reason": "unobserved",
        }
    ]
    incomplete = _measurement(result, "incomplete_residues")["value"]
    assert incomplete == [
        {
            "chain_id": "A",
            "resname": "ALA",
            "resseq": 2,
            "icode": "",
            "missing_atoms": ["CB"],
        }
    ]

    distances = _measurement(result, "ca_distances")["value"]
    assert distances[0]["distance_angstrom"] == pytest.approx(3.0, abs=1e-6)
    assert distances[0]["chain_break"] is False
    assert distances[0]["sequence_separation"] == 1
    assert distances[0]["numbering_gap"] is False
    # Residue numbers 4 and 2 differ by 2 because residue 3 is absent.
    assert distances[1]["distance_angstrom"] == pytest.approx(5.0, abs=1e-6)
    assert distances[1]["chain_break"] is True
    assert distances[1]["sequence_separation"] == 2
    assert distances[1]["numbering_gap"] is True

    rg = _measurement(result, "radius_of_gyration_ca")
    assert rg["unit"] == "angstrom"
    assert rg["origin"] == "calculated"
    assert rg["value"]["overall_angstrom"] == pytest.approx(math.sqrt(98 / 9), abs=1e-6)
    assert rg["value"]["ca_count"] == 3

    box = _measurement(result, "bounding_box")["value"]
    assert box["min_angstrom"] == pytest.approx([0.0, 0.0, 0.0])
    assert box["max_angstrom"] == pytest.approx([20.0, 20.0, 20.0])

    # Selected atoms: 5 + 4 + 5 polymer atoms, plus one water. The lower-occupancy CB is dropped.
    assert _measurement(result, "atom_count_total")["value"] == 15
    assert _measurement(result, "atom_count_hydrogen")["value"] == 0
    assert _measurement(result, "atom_count_water")["value"] == 1
    b_factor = _measurement(result, "b_factor_by_chain")["value"][0]
    assert b_factor["minimum"] == pytest.approx(10.0)
    assert b_factor["maximum"] == pytest.approx(40.0)
    assert b_factor["mean"] == pytest.approx(320 / 15)
    occupancy = _measurement(result, "occupancy_by_chain")["value"][0]
    assert occupancy["minimum"] == pytest.approx(0.7)
    assert occupancy["count_below_one"] == 1
    assert occupancy["mean"] == pytest.approx(0.98)

    comparison = _measurement(result, "sequence_comparison")["value"][0]
    assert comparison["seqres_residue_names"] == ["ALA", "ALA", "GLY", "ALA"]
    assert comparison["observed_residue_names"] == ["ALA", "ALA", "ALA"]
    assert comparison["agreement"] == "explained_by_missing_residues"
    assert _measurement(result, "title")["value"] == "BEAI SYNTHETIC PEPTIDE"
    assert _measurement(result, "title")["origin"] == "experimental_record"
    assert _measurement(result, "resolution")["value"] is None
    assert _measurement(result, "r_free")["value"] is None
    assert _measurement(result, "experimental_method")["value"] is None
    altlocs = _measurement(result, "alternate_locations")["value"]
    assert len(altlocs) == 1
    assert altlocs[0]["selected_altloc"] == "A"
    assert altlocs[0]["selected_occupancy"] == pytest.approx(0.7)


def test_1ubq_pdb_and_mmcif_match_the_rcsb_entry(client: TestClient) -> None:
    expected = SNAPSHOT["1UBQ"]
    pdb = _analyze(client, "1UBQ.pdb", (FIXTURES / "1UBQ.pdb").read_bytes())["result"]
    cif = _analyze(client, "1UBQ.cif", (FIXTURES / "1UBQ.cif").read_bytes())["result"]
    for result in (pdb, cif):
        chains = {row["chain_id"]: row for row in _measurement(result, "chains")["value"]}
        assert set(chains) == {"A"}
        assert chains["A"]["observed_polymer_residue_count"] == expected["chain_sequence_length"]["A"]
        assert chains["A"]["seqres_residue_count"] == expected["chain_sequence_length"]["A"]
        assert chains["A"]["observed_polymer_residue_count"] == expected["deposited_polymer_monomer_count"]
        assert _measurement(result, "water_residue_count")["value"] == expected["deposited_solvent_atom_count"]
        assert _measurement(result, "ligand_inventory")["value"] == []
        assert _measurement(result, "atom_count_total")["value"] == expected["deposited_atom_count"]
        assert _measurement(result, "atom_count_hydrogen")["value"] == expected["deposited_hydrogen_atom_count"]
        assert _measurement(result, "model_count")["value"] == expected["deposited_model_count"]
        assert _measurement(result, "title")["value"] == expected["title"]
        assert _measurement(result, "experimental_method")["value"] == expected["experimental_method"]
        assert _measurement(result, "resolution")["value"] == pytest.approx(expected["resolution_angstrom"])
        assert _measurement(result, "resolution")["unit"] == "angstrom"
        assert _measurement(result, "resolution")["origin"] == "experimental_record"
        assert _measurement(result, "r_free")["value"] is None
        assert _measurement(result, "deposition_date")["value"] == expected["deposition_date"]
        comparison = _measurement(result, "sequence_comparison")["value"][0]
        assert comparison["agreement"] == "identical"
        assert comparison["observed_sequence"] == expected["sequence_one_letter"]["A"]
        assert result["evidence"] == []
    assert _measurement(pdb, "analyzed_model_serial")["value"] is None
    assert _measurement(cif, "analyzed_model_serial")["value"] == 1
    assert (
        _measurement(pdb, "residue_count_observed_polymer")["value"]
        == _measurement(cif, "residue_count_observed_polymer")["value"]
    )
    assert _measurement(pdb, "water_residue_count")["value"] == _measurement(cif, "water_residue_count")["value"]


def test_4hhb_matches_the_rcsb_entry(client: TestClient) -> None:
    expected = SNAPSHOT["4HHB"]
    result = _analyze(client, "4HHB.pdb", (FIXTURES / "4HHB.pdb").read_bytes())["result"]
    chains = {row["chain_id"]: row for row in _measurement(result, "chains")["value"]}
    assert set(chains) == {"A", "B", "C", "D"}
    for chain_id, length in expected["chain_sequence_length"].items():
        assert chains[chain_id]["observed_polymer_residue_count"] == length
        assert chains[chain_id]["seqres_residue_count"] == length
        assert chains[chain_id]["water_residue_count"] > 0
    assert (
        _measurement(result, "residue_count_observed_polymer")["value"] == expected["deposited_polymer_monomer_count"]
    )
    assert _measurement(result, "water_residue_count")["value"] == expected["deposited_solvent_atom_count"]
    ligands = {item["resname"]: item for item in _measurement(result, "ligand_inventory")["value"]}
    assert ligands["HEM"]["residue_count"] == len(expected["hem_auth_asym_ids"])
    assert ligands["HEM"]["chains"] == expected["hem_auth_asym_ids"]
    assert ligands["PO4"]["residue_count"] == len(expected["po4_auth_asym_ids"])
    assert ligands["PO4"]["chains"] == expected["po4_auth_asym_ids"]
    assert _measurement(result, "title")["value"] == expected["title"]
    assert _measurement(result, "experimental_method")["value"] == expected["experimental_method"]
    assert _measurement(result, "resolution")["value"] == pytest.approx(expected["resolution_angstrom"])
    assert _measurement(result, "r_free")["value"] is None
    assert _measurement(result, "deposition_date")["value"] == expected["deposition_date"]
    polymer_total = sum(row["observed_polymer_residue_count"] for row in chains.values())
    water_total = _measurement(result, "water_residue_count")["value"]
    assert polymer_total != water_total


def test_running_status_is_visible_before_the_result_is_stored(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    uploaded = client.post(
        "/api/structures",
        files={"file": ("1UBQ.pdb", (FIXTURES / "1UBQ.pdb").read_bytes(), "chemical/x-pdb")},
    )
    assert uploaded.status_code == 201
    seen: dict[str, str] = {}
    real = overview_module.build_structure_overview

    def spy(*args, **kwargs):
        with client.app.state.engine.connect() as connection:
            seen["during"] = connection.execute(text("SELECT status FROM analyses")).scalar_one()
        return real(*args, **kwargs)

    monkeypatch.setattr(overview_module, "build_structure_overview", spy)
    monkeypatch.setattr(
        "backend.app.services.structure.analyses.build_structure_overview",
        spy,
    )
    created = client.post(
        f"/api/structures/{uploaded.json()['id']}/analyses",
        json={"kind": "structure_overview"},
    )
    assert created.status_code == 201, created.text
    assert seen["during"] == "running"
    assert created.json()["status"] == "succeeded"


def test_deleted_file_is_a_failed_analysis_without_a_traceback(client: TestClient, settings) -> None:
    uploaded = client.post(
        "/api/structures",
        files={"file": ("mini.pdb", (FIXTURES / "synthetic_peptide.pdb").read_bytes(), "chemical/x-pdb")},
    )
    assert uploaded.status_code == 201
    stored = list(settings.resolved_storage_dir().iterdir())
    assert len(stored) == 1
    stored[0].unlink()
    response = client.post(
        f"/api/structures/{uploaded.json()['id']}/analyses",
        json={"kind": "structure_overview"},
    )
    assert response.status_code == 422
    assert "Traceback" not in response.text
    listing = client.get("/api/analyses")
    assert listing.status_code == 200
    failed = listing.json()["analyses"]
    assert len(failed) == 1
    assert failed[0]["status"] == "failed"
    detail = client.get(f"/api/analyses/{failed[0]['id']}")
    assert detail.json()["result"] is None
    assert detail.json()["error"]["code"] == "invalid_input"
    assert "synthetic" not in detail.json()["error"]["message"]


def test_unknown_kind_and_missing_analysis(client: TestClient) -> None:
    uploaded = client.post(
        "/api/structures",
        files={"file": ("mini.pdb", (FIXTURES / "synthetic_peptide.pdb").read_bytes(), "chemical/x-pdb")},
    )
    rejected = client.post(
        f"/api/structures/{uploaded.json()['id']}/analyses",
        json={"kind": "docking"},
    )
    assert rejected.status_code == 422
    assert "Traceback" not in rejected.text
    missing = client.get("/api/analyses/does-not-exist")
    assert missing.status_code == 404
    assert missing.json()["code"] == "not_found"


def test_analysis_survives_a_new_app(client: TestClient, settings) -> None:
    from backend.app.main import create_app

    first = _analyze(client, "synthetic_peptide.pdb", (FIXTURES / "synthetic_peptide.pdb").read_bytes())
    with TestClient(create_app(settings)) as restarted:
        second = restarted.get(f"/api/analyses/{first['id']}")
    assert second.status_code == 200
    assert second.json() == first
