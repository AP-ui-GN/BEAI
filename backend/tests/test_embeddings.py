"""Embedding plumbing uses a composition stub. It is not an ESM-2 result."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.core.errors import InvalidInput
from backend.app.db.migrate import upgrade_to_head
from backend.app.main import create_app
from backend.app.services.embeddings.constants import FILE_SHA256, TOKEN_LIMIT
from backend.app.services.embeddings.download import verify_checkpoint
from backend.app.services.embeddings.stub import AMINO_ACIDS, composition_vector


def _stub(**overrides: object) -> dict:
    payload = {
        "name": "composition-stub",
        "version": "0",
        "task": "embedding plumbing",
        "source_url": "https://example.invalid/composition-stub",
        "licence": "test-only",
        "dependencies": [],
        "hardware": {"min_ram_bytes": 1024, "device": "cpu"},
        "input_format": "amino-acid sequence",
        "output_format": "composition vector",
        "known_limitations": "Amino-acid composition only. Not ESM-2 and not a learned embedding.",
        "loader_key": "embedding_stub",
        "token_limit": 8,
    }
    payload.update(overrides)
    return payload


def _sequence(client: TestClient, header: str, sequence: str) -> str:
    created = client.post("/api/sequences", json={"text": f">{header}\n{sequence}\n"})
    assert created.status_code == 201, created.text
    return created.json()["sequences"][0]["id"]


def test_stub_embedding_is_labelled_and_matches_the_composition_definition(client: TestClient) -> None:
    model = client.post("/api/models", json=_stub())
    assert model.status_code == 201, model.text
    model_id = model.json()["id"]
    sequence_id = _sequence(client, "alanine-rich", "AAAC")
    embedded = client.post(f"/api/sequences/{sequence_id}/embeddings", json={"model_id": model_id})
    assert embedded.status_code == 201, embedded.text
    result = embedded.json()["result"]
    measurement = result["measurements"][0]
    assert measurement["origin"] == "ml_prediction"
    assert measurement["name"] == "mean_pooled_embedding"
    assert "not experimental" in measurement["method"]
    assert result["details"]["label"] == "not experimental"
    expected = [0.0] * len(AMINO_ACIDS)
    expected[AMINO_ACIDS.index("A")] = 3 / 4
    expected[AMINO_ACIDS.index("C")] = 1 / 4
    assert measurement["value"] == pytest.approx(expected)
    assert measurement["value"] == pytest.approx(composition_vector("AAAC"))


def test_over_limit_sequence_stores_no_embedding(client: TestClient) -> None:
    model_id = client.post("/api/models", json=_stub()).json()["id"]
    sequence_id = _sequence(client, "too-long", "ACDEFGHIK")
    refused = client.post(f"/api/sequences/{sequence_id}/embeddings", json={"model_id": model_id})
    assert refused.status_code == 422
    assert "not truncated" in refused.json()["message"]
    neighbours = client.get(f"/api/sequences/{sequence_id}/neighbours", params={"model_id": model_id})
    assert neighbours.status_code == 422
    assert "No embedding is stored" in neighbours.json()["message"]


def test_neighbours_rank_composition_and_do_not_claim_function(client: TestClient) -> None:
    model_id = client.post("/api/models", json=_stub(token_limit=16)).json()["id"]
    query_id = _sequence(client, "query", "AAAAC")
    close_id = _sequence(client, "close", "AAAAA")
    far_id = _sequence(client, "far", "WWWWW")
    for sequence_id in (query_id, close_id, far_id):
        created = client.post(f"/api/sequences/{sequence_id}/embeddings", json={"model_id": model_id})
        assert created.status_code == 201, created.text
    ranked = client.get(f"/api/sequences/{query_id}/neighbours", params={"model_id": model_id})
    assert ranked.status_code == 200, ranked.text
    result = ranked.json()["result"]
    order = [item["sequence_id"] for item in result["details"]["neighbours"]]
    assert order == [close_id, far_id]
    assert result["measurements"][0]["origin"] == "calculated"
    assert any("not sequence identity" in item.lower() for item in result["limitations"])
    query = composition_vector("AAAAC")
    close = _cosine(query, composition_vector("AAAAA"))
    far = _cosine(query, composition_vector("WWWWW"))
    reported = result["measurements"][0]["value"]
    assert reported[0]["cosine_similarity"] == pytest.approx(close)
    assert reported[1]["cosine_similarity"] == pytest.approx(far)
    assert close > far


def test_builtin_esm_row_is_not_loaded_at_startup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'beai.sqlite'}",
        storage_dir=tmp_path / "structures",
        register_builtins=True,
    )
    upgrade_to_head(settings.resolved_database_url())
    calls: list[str] = []

    def refuse(row: object) -> dict:
        calls.append(getattr(row, "id", ""))
        raise AssertionError("startup must not load ESM-2")

    monkeypatch.setattr("backend.app.services.embeddings.esm.load_esm", refuse)
    with TestClient(create_app(settings)) as client:
        models = client.get("/api/models").json()["models"]
    esm = [item for item in models if item["loader_key"] == "esm2_8m"]
    assert len(esm) == 1
    assert esm[0]["loaded"] is False
    assert esm[0]["weights_loaded"] is False
    assert esm[0]["licence"] == "MIT"
    assert esm[0]["token_limit"] == TOKEN_LIMIT
    assert calls == []


def test_checkpoint_checksum_mismatch_is_rejected(tmp_path: Path) -> None:
    for name in FILE_SHA256:
        (tmp_path / name).write_bytes(b"not-the-recorded-file")
    with pytest.raises(InvalidInput, match="checksum"):
        verify_checkpoint(tmp_path)


def test_download_is_refused_for_a_stub(client: TestClient) -> None:
    model_id = client.post("/api/models", json=_stub()).json()["id"]
    response = client.post(f"/api/models/{model_id}/download")
    assert response.status_code == 422
    assert "ESM-2" in response.json()["message"]


def _cosine(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = sum(a * a for a in left) ** 0.5
    right_norm = sum(b * b for b in right) ** 0.5
    return dot / (left_norm * right_norm)
