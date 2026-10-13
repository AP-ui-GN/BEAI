"""Opt-in ESM-2 8M check. Default pytest does not run this module.

The curated files, identity definition, bootstrap seed 20261013, and 1000
resamples were fixed before the coefficient was computed.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.db.migrate import upgrade_to_head
from backend.app.main import create_app
from backend.app.services.embeddings.benchmark import curated_sequences, rank_correlation
from backend.app.services.embeddings.constants import TOKEN_LIMIT
from backend.app.services.embeddings.download import checkpoint_dir, ensure_checkpoint
from backend.app.services.embeddings.esm import load_esm
from backend.app.services.models_registry.registry import get_model_row

pytestmark = pytest.mark.model
FIXTURES = Path(__file__).parent / "fixtures"


def test_esm2_embeddings_and_rank_correlation(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'beai.sqlite'}",
        storage_dir=tmp_path / "structures",
        register_builtins=True,
    )
    upgrade_to_head(settings.resolved_database_url())
    downloaded = ensure_checkpoint()
    assert downloaded["checksum_sha256"]
    config = json.loads((checkpoint_dir() / "config.json").read_text(encoding="utf-8"))
    with TestClient(create_app(settings)) as client:
        esm = next(item for item in client.get("/api/models").json()["models"] if item["loader_key"] == "esm2_8m")
        assert esm["status"] == "ready"
        short = client.post("/api/sequences", json={"text": ">short\nACDE\n"})
        sequence_id = short.json()["sequences"][0]["id"]
        embedded = client.post(f"/api/sequences/{sequence_id}/embeddings", json={"model_id": esm["id"]})
        assert embedded.status_code == 201, embedded.text
        result = embedded.json()["result"]
        vector = result["measurements"][0]["value"]
        assert result["measurements"][0]["origin"] == "ml_prediction"
        assert result["details"]["label"] == "not experimental"
        assert len(vector) == config["hidden_size"]
        too_long = "A" * TOKEN_LIMIT
        refused_id = client.post("/api/sequences", json={"text": f">long\n{too_long}\n"}).json()["sequences"][0]["id"]
        refused = client.post(f"/api/sequences/{refused_id}/embeddings", json={"model_id": esm["id"]})
        assert refused.status_code == 422
        assert "not truncated" in refused.json()["message"]
        unknown = client.post("/api/sequences", json={"text": ">unk\nAJ\n"}).json()["sequences"][0]["id"]
        unknown_response = client.post(f"/api/sequences/{unknown}/embeddings", json={"model_id": esm["id"]})
        assert unknown_response.status_code == 422
        assert "<unk>" in unknown_response.json()["message"]
        session = client.app.state.session_factory()
        try:
            row = get_model_row(session, esm["id"])
            artifact = load_esm(row)
        finally:
            session.close()
        sequences = curated_sequences(FIXTURES, TOKEN_LIMIT)
        assert len(sequences) >= 6
        summary = rank_correlation(sequences, artifact["embed"])
        again = rank_correlation(sequences, artifact["embed"])
        print("ESM2_BENCHMARK", json.dumps({key: summary[key] for key in summary if key != "pairs"}))
        assert summary["spearman"] is not None
        assert -1.0 <= summary["spearman"] <= 1.0
        assert summary["interval_low"] <= summary["spearman"] <= summary["interval_high"]
        assert summary["seed"] == 20261013
        assert summary["resamples"] == 1000
        assert summary["spearman"] == again["spearman"]
        assert summary["interval_low"] == again["interval_low"]
        assert summary["pair_count"] == len(summary["pairs"])
