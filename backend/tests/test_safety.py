"""Safety evidence uses saved openFDA and PubMed responses. Failures store nothing."""

import json
from pathlib import Path

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.app.data_access.http import ExternalHttp
from backend.app.services.safety.evidence import NOT_CAUSAL, RESEARCH_BANNER

FIXTURES = Path(__file__).parent / "fixtures" / "safety"


def _use(client: TestClient, tmp_path: Path, handler) -> None:
    client.app.state.http.close()
    client.app.state.http = ExternalHttp(tmp_path / "cache", transport=httpx.MockTransport(handler))


def _count(client: TestClient) -> int:
    with client.app.state.engine.connect() as connection:
        return int(connection.execute(text("SELECT COUNT(*) FROM safety_lookups")).scalar_one())


def test_label_sections_are_verbatim(client: TestClient, tmp_path: Path) -> None:
    payload = json.loads((FIXTURES / "openfda_label_aspirin.json").read_text(encoding="utf-8"))
    record = payload["results"][0]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    _use(client, tmp_path, handler)
    response = client.post("/api/safety/label", json={"name": "aspirin"})
    assert response.status_code == 200, response.text
    body = response.json()
    warnings = next(item for item in body["sections"] if item["section"] == "warnings")
    assert warnings["text"] == record["warnings"]
    assert warnings["set_id"] == record["set_id"]
    assert warnings["version"] == record["version"]
    assert warnings["effective_time"] == record["effective_time"]
    assert warnings["category"] == "established"
    assert body["banner"] == RESEARCH_BANNER
    assert body["drug_interactions"] is None or body["drug_interactions"] == record.get("drug_interactions")


def test_failed_label_request_stores_nothing(client: TestClient, tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    _use(client, tmp_path, handler)
    response = client.post("/api/safety/label", json={"name": "aspirin"})
    assert response.status_code == 502
    assert _count(client) == 0


def test_faers_is_observational_and_not_causal(client: TestClient, tmp_path: Path) -> None:
    payload = json.loads((FIXTURES / "openfda_faers_aspirin.json").read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    _use(client, tmp_path, handler)
    response = client.post("/api/safety/events", json={"name": "ASPIRIN"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["category"] == "observational"
    assert body["statement"] == NOT_CAUSAL
    assert "do not establish causation" in body["statement"]
    assert body["counts"] == payload["results"]


def test_literature_stays_unclassified(client: TestClient, tmp_path: Path) -> None:
    search = json.loads((FIXTURES / "pubmed_esearch.json").read_text(encoding="utf-8"))
    summary = json.loads((FIXTURES / "pubmed_esummary.json").read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        if "esummary" in str(request.url):
            return httpx.Response(200, json=summary)
        return httpx.Response(200, json=search)

    _use(client, tmp_path, handler)
    response = client.post("/api/safety/literature", json={"query": "aspirin"})
    assert response.status_code == 200, response.text
    item = response.json()["items"][0]
    assert item["category"] == "unclassified"
    assert item["pmid"] == "42864513"
    assert item["title"]


def test_similarity_offtargets_are_unverified_and_assays_stay_split(client: TestClient) -> None:
    response = client.post(
        "/api/safety/off-targets",
        json={
            "activities": [
                {
                    "target_chembl_id": "CHEMBL1",
                    "standard_type": "IC50",
                    "standard_units": "nM",
                    "standard_value": 10,
                    "standard_relation": "=",
                    "assay_chembl_id": "CHEMBLA",
                    "document_chembl_id": "CHEMBLD",
                },
                {
                    "target_chembl_id": "CHEMBL1",
                    "standard_type": "Ki",
                    "standard_units": "nM",
                    "standard_value": 4,
                    "standard_relation": "=",
                    "assay_chembl_id": "CHEMBLB",
                    "document_chembl_id": "CHEMBLD",
                },
            ],
            "similarity_hits": [
                {"target_chembl_id": "CHEMBL9", "similarity": 0.82, "supporting_ligands": ["CHEMBL25"]}
            ],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["measured_groups"]) == 2
    hit = body["similarity_offtargets"][0]
    assert hit["category"] == "computational_prediction"
    assert hit["label"] == "unverified"


def test_safety_ui_does_not_offer_dosing_or_medication_changes() -> None:
    text = Path("frontend/src/pages/DrugSafety.tsx").read_text(encoding="utf-8").lower()
    for phrase in ("take ", "mg ", "safer alternative", "stop taking", "change your medication"):
        assert phrase not in text


def test_overdose_query_puts_the_emergency_pointer_first(client: TestClient, tmp_path: Path) -> None:
    payload = json.loads((FIXTURES / "openfda_label_aspirin.json").read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    _use(client, tmp_path, handler)
    response = client.post("/api/safety/label", json={"name": "aspirin overdose"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["emergency"]
    assert "1-800-222-1222" in body["emergency"]
    assert "sections" in body
