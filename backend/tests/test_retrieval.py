"""RCSB and UniProt import. Mock bodies are saved API responses, not invented records."""

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.data_access.http import ExternalHttp

FIXTURES = Path(__file__).parent / "fixtures"
EXTERNAL = FIXTURES / "external"


def _use_transport(client: TestClient, tmp_path: Path, handler) -> None:
    client.app.state.http.close()
    client.app.state.http = ExternalHttp(tmp_path / "cache", transport=httpx.MockTransport(handler))


def test_mocked_rcsb_import_stores_provenance_and_upload_still_works_offline(
    client: TestClient, tmp_path: Path
) -> None:
    metadata = (EXTERNAL / "rcsb_1ubq_entry.json").read_bytes()
    pdb_bytes = (FIXTURES / "1UBQ.pdb").read_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        if host == "data.rcsb.org":
            return httpx.Response(200, content=metadata, headers={"Content-Type": "application/json"})
        if host == "files.rcsb.org":
            return httpx.Response(200, content=pdb_bytes, headers={"Content-Type": "text/plain"})
        return httpx.Response(500)

    _use_transport(client, tmp_path, handler)
    created = client.post("/api/structures/import", json={"pdb_id": "1ubq"})
    assert created.status_code == 201, created.text
    body = created.json()
    provenance = body["metadata"]["provenance"]
    assert provenance["identifier"] == "1UBQ"
    assert provenance["license"] == "CC0"
    assert provenance["rcsb_id"] == "1UBQ"
    assert provenance["source"] == "RCSB PDB"
    assert provenance["retrieved_at"]
    analyzed = client.post(f"/api/structures/{body['id']}/analyses", json={"kind": "structure_overview"})
    assert analyzed.status_code == 201, analyzed.text
    # A local upload does not need the mocked network.
    peptide = (FIXTURES / "synthetic_peptide.pdb").read_bytes()
    uploaded = client.post("/api/structures", files={"file": ("synthetic_peptide.pdb", peptide, "chemical/x-pdb")})
    assert uploaded.status_code == 201, uploaded.text


def test_failed_rcsb_request_stores_nothing(client: TestClient, tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "data.rcsb.org":
            return httpx.Response(200, json={"rcsb_id": "1UBQ", "struct": {"title": "X"}})
        return httpx.Response(503)

    _use_transport(client, tmp_path, handler)
    response = client.post("/api/structures/import", json={"pdb_id": "1UBQ"})
    assert response.status_code == 502
    assert response.json()["code"] == "external_service_error"
    listing = client.get("/api/structures")
    assert listing.json()["structures"] == []


def test_inactive_uniprot_entry_is_not_stored(client: TestClient, tmp_path: Path) -> None:
    inactive = json.loads((EXTERNAL / "uniprot_P62988_inactive.json").read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=inactive)

    _use_transport(client, tmp_path, handler)
    response = client.post("/api/sequences/import", json={"accession": "P62988"})
    assert response.status_code == 422, response.text
    assert "P0CG48" in response.json()["message"] or "P62987" in response.json()["message"]
    assert client.get("/api/sequences").json()["sequences"] == []


def test_mocked_uniprot_import_keeps_the_returned_sequence(client: TestClient, tmp_path: Path) -> None:
    record = json.loads((EXTERNAL / "uniprot_P62987.json").read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=record)

    _use_transport(client, tmp_path, handler)
    response = client.post("/api/sequences/import", json={"accession": "P62987"})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["sequence"] == record["sequence"]["value"]
    assert body["length"] == 128
    assert body["source"]["license"] == "CC BY 4.0"
    assert body["source"]["identifier"] == "P62987"
    assert body["source"]["organism"] == "Homo sapiens"


@pytest.mark.network
def test_live_rcsb_and_uniprot_import(client: TestClient) -> None:
    structure = client.post("/api/structures/import", json={"pdb_id": "1UBQ"})
    assert structure.status_code == 201, structure.text
    assert structure.json()["metadata"]["provenance"]["identifier"] == "1UBQ"
    sequence = client.post("/api/sequences/import", json={"accession": "P62987"})
    assert sequence.status_code == 201, sequence.text
    assert sequence.json()["length"] == 128
    assert sequence.json()["source"]["license"] == "CC BY 4.0"
