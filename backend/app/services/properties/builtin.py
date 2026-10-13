"""Registry row for the solubility models. Inserting it does not train."""

from __future__ import annotations

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from backend.app.services.properties.constants import DATASET_URL, NOT_EXPERIMENTAL, SPLIT_SEED


def solubility_payload() -> dict:
    return {
        "name": "esol-baselines",
        "version": f"seed-{SPLIT_SEED}",
        "task": "aqueous solubility, log10 mol per litre",
        "source_url": DATASET_URL,
        "licence": (
            "The CSV has no licence line. DeepChem's repository LICENSE retrieved 2026-10-13 is MIT "
            "and covers that software. The table is the Delaney set named by DeepChem's load_delaney."
        ),
        "dependencies": [
            {"kind": "python", "name": "rdkit"},
            {"kind": "python", "name": "sklearn"},
            {"kind": "python", "name": "torch"},
            {"kind": "python", "name": "torch_geometric"},
        ],
        "hardware": {"min_ram_bytes": 512 * 1024 * 1024, "device": "cpu"},
        "input_format": "SMILES",
        "output_format": "predicted log10 solubility in mol per litre",
        "benchmark": None,
        "known_limitations": (
            f"Predictions are {NOT_EXPERIMENTAL}. They are not measured solubilities. "
            "Ridge alpha is 1.0. The GCN is two layers, hidden size 32, 20 epochs, learning rate 0.01. "
            "Those settings were not chosen from the test split. "
            "A molecule is outside the applicability domain when its maximum Morgan Tanimoto "
            "to the training set is below 0.3."
        ),
        "checksum_sha256": None,
        "weights_relative": "esol/gnn.safetensors",
        "loader_key": "solubility",
        "token_limit": None,
    }


def sync_solubility_model(session: Session) -> None:
    bind = session.get_bind()
    if not inspect(bind).has_table("registered_models"):
        return
    from backend.app.db.models import RegisteredModel
    from backend.app.services.models_registry.registry import register_model

    payload = solubility_payload()
    existing = session.scalar(
        select(RegisteredModel).where(
            RegisteredModel.name == payload["name"],
            RegisteredModel.version == payload["version"],
        )
    )
    if existing is not None:
        return
    register_model(session, payload)
