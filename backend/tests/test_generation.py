"""BRICS hypotheses. Filters stay on and toxicity is not an objective."""

from fastapi.testclient import TestClient
from rdkit import Chem

from backend.app.services.generation.brics import HYPOTHESIS

REFERENCES = [
    "CC(=O)Oc1ccccc1C(=O)O",
    "CCOC(=O)c1ccc(N)cc1",
    "CC(C)Cc1ccc(cc1)C(C)C(=O)O",
]


def test_filters_cannot_be_disabled_and_toxicity_is_rejected(client: TestClient) -> None:
    blocked = client.post(
        "/api/generation",
        json={
            "references": REFERENCES,
            "objectives": [{"kind": "property_range", "property": "MolWt", "maximum": 500}],
            "filters_off": True,
        },
    )
    assert blocked.status_code == 422
    assert "cannot be switched off" in blocked.json()["message"]
    toxic = client.post(
        "/api/generation",
        json={
            "references": REFERENCES,
            "objectives": [{"kind": "property_range", "property": "MolWt", "maximum": 500, "note": "reward toxicity"}],
        },
    )
    assert toxic.status_code == 422
    assert "toxicity" in toxic.json()["message"]


def test_outputs_are_sanitized_hypotheses(client: TestClient) -> None:
    created = client.post(
        "/api/generation",
        json={
            "references": REFERENCES,
            "objectives": [{"kind": "property_range", "property": "MolWt", "minimum": 50, "maximum": 800}],
            "seed": 3,
            "count": 5,
        },
    )
    assert created.status_code == 201, created.text
    result = created.json()["result"]
    assert HYPOTHESIS in result["limitations"]
    assert result["details"]["label"] == HYPOTHESIS
    assert result["methods"][0]["parameters"]["filters"] == ["PAINS", "BRENK", "NIH"]
    metrics = result["details"]["metrics"]
    assert metrics["seed"] == 3
    for name in ("validity", "uniqueness", "novelty", "diversity", "filter_pass_rate"):
        assert name in metrics
    for output in result["details"]["outputs"]:
        mol = Chem.MolFromSmiles(output["smiles"])
        assert mol is not None
        assert output["label"] == HYPOTHESIS
        assert output["filter_hits"] == []
        assert Chem.MolToSmiles(mol) == output["smiles"]
