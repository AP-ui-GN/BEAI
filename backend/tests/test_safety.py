"""Safety evidence uses saved openFDA and PubMed responses. Failures store nothing."""

import json
import xml.etree.ElementTree as ET
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


def test_dailymed_is_used_when_openfda_fails(client: TestClient, tmp_path: Path) -> None:
    search = json.loads((FIXTURES / "dailymed_warfarin_spls.json").read_text(encoding="utf-8"))
    xml_bytes = (FIXTURES / "dailymed_warfarin_spl.xml").read_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "api.fda.gov" in url:
            return httpx.Response(404, json={"error": {"code": "NOT_FOUND"}})
        if url.endswith(".xml"):
            return httpx.Response(200, content=xml_bytes)
        return httpx.Response(200, json=search)

    _use(client, tmp_path, handler)
    response = client.post("/api/safety/label", json={"name": "warfarin"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "DailyMed"
    assert body["set_id"] == search["data"][0]["setid"]
    assert body["version"] == search["data"][0]["spl_version"]
    assert body["openfda_error"]
    warning = next(item for item in body["sections"] if item["section"] == "boxed_warning")
    assert warning["category"] == "established"
    assert "WARNING: BLEEDING RISK" in warning["text"][0]
    assert "Warfarin sodium can cause major or fatal bleeding" in warning["text"][0]
    independent = _boxed_warning_phrase(xml_bytes)
    assert independent in warning["text"][0]


def test_europepmc_stays_unclassified_and_hides_closed_abstracts(client: TestClient, tmp_path: Path) -> None:
    payload = json.loads((FIXTURES / "europepmc_aspirin.json").read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    _use(client, tmp_path, handler)
    response = client.post("/api/safety/europepmc", json={"query": "aspirin"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "Europe PMC"
    item = body["items"][0]
    assert item["category"] == "unclassified"
    assert item["pmid"] == payload["resultList"]["result"][0]["pmid"]
    assert item["title"] == payload["resultList"]["result"][0]["title"]
    assert item["abstract"] is None
    assert item["abstract_omitted_reason"]
    assert payload["resultList"]["result"][0]["abstractText"] not in response.text


def test_europepmc_keeps_an_open_access_abstract(client: TestClient, tmp_path: Path) -> None:
    payload = json.loads((FIXTURES / "europepmc_oa.json").read_text(encoding="utf-8"))
    row = payload["resultList"]["result"][0]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    _use(client, tmp_path, handler)
    response = client.post("/api/safety/europepmc", json={"query": "aspirin"})
    assert response.status_code == 200, response.text
    item = response.json()["items"][0]
    assert item["category"] == "unclassified"
    assert row["isOpenAccess"] == "Y"
    assert item["license"] == row["license"]
    assert item["abstract"] == row["abstractText"]


def test_open_targets_records_are_unclassified(client: TestClient, tmp_path: Path) -> None:
    payload = json.loads((FIXTURES / "opentargets_vkorc1.json").read_text(encoding="utf-8"))
    target = payload["data"]["target"]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    _use(client, tmp_path, handler)
    response = client.post("/api/safety/open-targets", json={"ensembl_id": "ENSG00000167397"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "Open Targets Platform"
    assert body["approved_symbol"] == target["approvedSymbol"]
    liability = body["safety_liabilities"][0]
    assert liability["category"] == "unclassified"
    assert liability["event"] == target["safetyLiabilities"][0]["event"]
    assert liability["datasource"] == target["safetyLiabilities"][0]["datasource"]
    disease = body["disease_associations"][0]
    assert disease["category"] == "unclassified"
    assert disease["score"] == target["associatedDiseases"]["rows"][0]["score"]
    assert disease["disease_id"] == target["associatedDiseases"]["rows"][0]["disease"]["id"]
    assert "not evidence of efficacy" in disease["limitation"]


def test_failed_europepmc_and_open_targets_store_nothing(client: TestClient, tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    _use(client, tmp_path, handler)
    literature = client.post("/api/safety/europepmc", json={"query": "aspirin"})
    assert literature.status_code == 502
    targets = client.post("/api/safety/open-targets", json={"ensembl_id": "ENSG00000167397"})
    assert targets.status_code == 502
    refused = client.post("/api/safety/open-targets", json={"ensembl_id": "not-an-id"})
    assert refused.status_code == 422
    assert _count(client) == 0


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


def _boxed_warning_phrase(xml_bytes: bytes) -> str:
    root = ET.fromstring(xml_bytes)
    ns = "{urn:hl7-org:v3}"
    for section in root.iter(f"{ns}section"):
        code = section.find(f"{ns}code")
        if code is None or code.get("code") != "34066-1":
            continue
        for node in section.iter():
            if node.text and "major or fatal bleeding" in node.text:
                return node.text.strip()
    raise AssertionError("boxed warning phrase was not in the saved SPL")
