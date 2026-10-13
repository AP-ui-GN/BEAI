"""Compound validation, similarity, and retrieved records.

Reference masses are the milestone contract values (aspirin 180.16, caffeine
194.19, ethanol 46.07), checked here against RDKit MolWt rounded to 2 decimals.
"""

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.core.capabilities import probe_import
from backend.app.data_access.http import ExternalHttp
from backend.app.services.compounds.compare import compare_activity_pair, group_activities

FIXTURES = Path(__file__).parent / "fixtures" / "external"


def _use(client: TestClient, tmp_path: Path, handler) -> None:
    client.app.state.http.close()
    client.app.state.http = ExternalHttp(tmp_path / "cache", transport=httpx.MockTransport(handler))


def _measurement(result: dict, name: str) -> dict:
    return next(item for item in result["measurements"] if item["name"] == name)


def test_known_molecules_match_formula_and_mass(client: TestClient) -> None:
    cases = [
        ("CC(=O)Oc1ccccc1C(=O)O", "C9H8O4", 180.16),
        ("CN1C=NC2=C1C(=O)N(C(=O)N2C)C", "C8H10N4O2", 194.19),
        ("CCO", "C2H6O", 46.07),
    ]
    for smiles, formula, mass in cases:
        created = client.post("/api/compounds", json={"smiles": smiles})
        assert created.status_code == 201, created.text
        result = created.json()["analysis"]["result"]
        assert _measurement(result, "molecular_formula")["value"] == formula
        assert round(_measurement(result, "MolWt")["value"], 2) == mass
        assert _measurement(result, "MolWt")["origin"] == "calculated"
        text = " ".join(result["limitations"]).lower()
        assert "drug-likeness" in text and "not" in text


@pytest.mark.parametrize("smiles", ["", "not_a_molecule", "C1CC(", "C(C)(C)(C)(C)C"])
def test_invalid_smiles_are_rejected_and_not_stored(client: TestClient, smiles: str) -> None:
    rejected = client.post("/api/compounds", json={"smiles": smiles})
    assert rejected.status_code == 422, rejected.text
    assert client.get("/api/compounds").json()["compounds"] == []


def test_similarity_is_symmetric_and_orders_aspirin(client: TestClient) -> None:
    created = []
    for smiles in ["CC(=O)Oc1ccccc1C(=O)O", "O=C(O)c1ccccc1O", "CN1C=NC2=C1C(=O)N(C(=O)N2C)C"]:
        response = client.post("/api/compounds", json={"smiles": smiles})
        assert response.status_code == 201, response.text
        created.append(response.json()["id"])
    matrix = client.post("/api/compounds/similarity", json={"compound_ids": created})
    assert matrix.status_code == 200, matrix.text
    values = matrix.json()["matrix"]
    assert values[0][0] == 1.0
    assert values == [list(row) for row in zip(*values, strict=True)] or values[0][1] == values[1][0]
    assert values[0][1] > values[0][2]


def test_salt_stays_multi_fragment_unless_asked(client: TestClient) -> None:
    kept = client.post("/api/compounds", json={"smiles": "CC(=O)[O-].[Na+]"})
    assert kept.status_code == 201, kept.text
    result = kept.json()["analysis"]["result"]
    assert _measurement(result, "fragment_count")["value"] == 2
    assert any("not reduced" in warning for warning in result["warnings"])
    reduced = client.post("/api/compounds", json={"smiles": "CC(=O)[O-].[Na+]", "keep_largest_fragment": True})
    assert reduced.status_code == 201, reduced.text
    reduced_result = reduced.json()["analysis"]["result"]
    assert _measurement(reduced_result, "fragment_count")["value"] == 1


def test_pubchem_mock_stores_reported_fields_and_failure_stores_nothing(client: TestClient, tmp_path: Path) -> None:
    payload = json.loads((FIXTURES / "pubchem_aspirin.json").read_text(encoding="utf-8"))

    def ok(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    _use(client, tmp_path, ok)
    created = client.post("/api/compounds/import/pubchem", json={"query": "aspirin", "query_type": "name"})
    assert created.status_code == 201, created.text
    source = created.json()["source"]
    assert source["identifier"] == "2244"
    assert source["molecular_formula"] == "C9H8O4"
    assert source["molecular_weight"] == "180.16"
    assert source["canonical_smiles"] is None
    assert source["connectivity_smiles"]
    result = created.json()["analysis"]["result"]
    assert _measurement(result, "MolWt")["origin"] == "calculated"

    def fail(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    _use(client, tmp_path / "other", fail)
    before = len(client.get("/api/compounds").json()["compounds"])
    rejected = client.post("/api/compounds/import/pubchem", json={"query": "nope", "query_type": "name"})
    assert rejected.status_code == 502
    assert len(client.get("/api/compounds").json()["compounds"]) == before


def test_activity_types_are_not_merged() -> None:
    ic50 = {
        "target_chembl_id": "CHEMBL3253",
        "standard_type": "IC50",
        "standard_units": "nM",
        "standard_value": 10,
        "standard_relation": "=",
    }
    ki = {**ic50, "standard_type": "Ki", "standard_value": 3}
    compared = compare_activity_pair(ic50, ki)
    assert compared["comparable"] is False
    assert "standard types" in compared["reason"]
    groups = group_activities([ic50, ki])
    assert len(groups) == 2
    assert {group["standard_type"] for group in groups} == {"IC50", "Ki"}


def test_chembl_mock_keeps_activity_fields(client: TestClient, tmp_path: Path) -> None:
    molecule = json.loads((FIXTURES / "chembl_25_molecule.json").read_text(encoding="utf-8"))
    activities = json.loads((FIXTURES / "chembl_25_activities.json").read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        if "activity.json" in str(request.url):
            return httpx.Response(200, json=activities)
        return httpx.Response(200, json=molecule)

    _use(client, tmp_path, handler)
    created = client.post("/api/compounds/import/chembl", json={"chembl_id": "CHEMBL25"})
    assert created.status_code == 201, created.text
    source = created.json()["source"]
    assert source["identifier"] == "CHEMBL25"
    assert source["activities"]
    first = source["activities"][0]
    assert first["assay_chembl_id"]
    assert first["target_chembl_id"]
    assert "standard_type" in first
    depiction = client.get(f"/api/compounds/{created.json()['id']}/depiction")
    assert depiction.status_code == 200
    assert depiction.headers["content-type"].startswith("image/svg+xml")
    assert b"<svg" in depiction.content


def test_rdkit_hidden_returns_503_and_structures_still_upload(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def hidden(module: str, distribution: str) -> dict:
        if module == "rdkit":
            return {"available": False, "version": None, "reason": "RDKit is not installed."}
        return probe_import(module, distribution)

    monkeypatch.setattr("backend.app.services.compounds.chemistry.probe_import", hidden)
    denied = client.post("/api/compounds", json={"smiles": "CCO"})
    assert denied.status_code == 503
    assert "RDKit" in denied.json()["message"]
    peptide = Path("backend/tests/fixtures/synthetic_peptide.pdb").read_bytes()
    uploaded = client.post("/api/structures", files={"file": ("synthetic_peptide.pdb", peptide, "chemical/x-pdb")})
    assert uploaded.status_code == 201, uploaded.text
