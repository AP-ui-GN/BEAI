"""Load a saved solubility artifact and predict. This does not run at import."""

from __future__ import annotations

import hashlib
import json
import platform
import uuid
from datetime import UTC, datetime
from typing import Any

import numpy
from rdkit import Chem
from safetensors.torch import load_file

from backend.app.core.errors import CapabilityUnavailable, InvalidInput
from backend.app.db.models import RegisteredModel
from backend.app.services.properties.constants import (
    APPLICABILITY_MAX_TANIMOTO,
    DESCRIPTOR_NAMES,
    NOT_EXPERIMENTAL,
)
from backend.app.services.properties.gnn import SolubilityGCN, molecule_graph
from backend.app.services.properties.train import _descriptors, _fingerprint, artifact_dir


def load_solubility(row: RegisteredModel) -> dict[str, Any]:
    """Read the Ridge arrays and the GCN weights. Missing files are a 503, not a guess."""

    directory = artifact_dir()
    ridge_path = directory / "ridge.npz"
    gnn_path = directory / "gnn.safetensors"
    if not ridge_path.is_file() or not gnn_path.is_file():
        raise CapabilityUnavailable("This solubility model has not been trained. No prediction was invented.")
    loaded = numpy.load(ridge_path)
    state = load_file(gnn_path)

    def predict(smiles: str) -> dict[str, Any]:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            raise InvalidInput("RDKit could not parse that SMILES. Nothing was predicted.")
        desc = numpy.asarray(_descriptors(mol), dtype=float)
        fp = _fingerprint(mol).astype(float)
        descriptor_value = float(desc @ loaded["descriptor_coef"] + loaded["descriptor_intercept"][0])
        fingerprint_value = float(fp @ loaded["fingerprint_coef"] + loaded["fingerprint_intercept"][0])
        ensemble = loaded["ensemble_coef"] @ fp + loaded["ensemble_intercept"]
        uncertainty = float(numpy.std(ensemble, ddof=1))
        train_fp = loaded["train_fingerprints"].astype(numpy.uint8)
        query = fp.astype(numpy.uint8)
        intersection = numpy.logical_and(train_fp, query).sum(axis=1)
        union = numpy.logical_or(train_fp, query).sum(axis=1)
        union = numpy.maximum(union, 1)
        tanimoto = intersection / union
        max_tanimoto = float(tanimoto.max()) if tanimoto.size else None
        in_domain = max_tanimoto is not None and max_tanimoto >= APPLICABILITY_MAX_TANIMOTO
        import torch
        from torch_geometric.data import Batch

        graph = Batch.from_data_list([molecule_graph(mol)])
        network = SolubilityGCN()
        network.load_state_dict(state)
        network.eval()
        with torch.no_grad():
            gnn_value = float(network(graph.x, graph.edge_index, graph.batch).item())
        return {
            "descriptor": descriptor_value,
            "fingerprint": fingerprint_value,
            "gnn": gnn_value,
            "fingerprint_ensemble_std": uncertainty,
            "max_tanimoto_to_training": max_tanimoto,
            "in_applicability_domain": in_domain,
            "threshold": APPLICABILITY_MAX_TANIMOTO,
            "canonical_smiles": Chem.MolToSmiles(mol),
        }

    return {
        "weights_loaded": True,
        "predict": predict,
        "note": "Ridge baselines and the GCN were loaded from models/esol. Predictions are not experimental.",
    }


def prediction_result(row: RegisteredModel, smiles: str, predicted: dict[str, Any]) -> dict[str, Any]:
    """Analysis envelope. Every solubility number is an ML prediction."""

    label = NOT_EXPERIMENTAL
    if predicted["in_applicability_domain"]:
        domain = "inside the applicability domain"
    else:
        domain = "outside the applicability domain"
    parameters = {
        "model_name": row.name,
        "model_version": row.version,
        "descriptor_functions": list(DESCRIPTOR_NAMES),
        "applicability_max_tanimoto": APPLICABILITY_MAX_TANIMOTO,
        "label": label,
    }
    warnings = []
    if not predicted["in_applicability_domain"]:
        warnings.append(
            f"Flagged {domain}. Maximum Morgan Tanimoto to the training set is "
            f"{predicted['max_tanimoto_to_training']}."
        )
    now = datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    return {
        "analysis_id": str(uuid.uuid4()),
        "kind": "solubility_prediction",
        "created_at": now,
        "status": "succeeded",
        "inputs": [
            {
                "role": "smiles",
                "filename": None,
                "source_id": predicted["canonical_smiles"],
                "sha256": hashlib.sha256(smiles.encode()).hexdigest(),
                "validation_status": "valid",
                "validation_messages": [],
            }
        ],
        "methods": [
            {
                "name": "solubility_models",
                "software": "scikit-learn Ridge and a two-layer GCN",
                "version": row.version,
                "parameters": parameters,
            }
        ],
        "measurements": [
            _measure(
                "descriptor_ridge_log_solubility",
                predicted["descriptor"],
                "Ridge on named RDKit descriptors. Not an experimental measurement.",
                None,
            ),
            _measure(
                "fingerprint_ridge_log_solubility",
                predicted["fingerprint"],
                "Ridge on Morgan fingerprints. Uncertainty is the std of 5 training-set bootstrap refits.",
                predicted["fingerprint_ensemble_std"],
            ),
            _measure(
                "gcn_log_solubility",
                predicted["gnn"],
                "Two-layer GCN. Not an experimental measurement. No ensemble uncertainty was fit for this model.",
                None,
            ),
        ],
        "evidence": [],
        "limitations": [
            "These are ML predictions of log10 solubility in mol per litre, not measurements.",
            "They are not evidence of safety, dose, or clinical effect.",
            f"The molecule is {domain} at the pre-registered Tanimoto threshold {APPLICABILITY_MAX_TANIMOTO}.",
        ],
        "warnings": warnings,
        "skipped_stages": [],
        "errors": [],
        "reproducibility": {
            "software_versions": {"python": platform.python_version()},
            "random_seed": None,
            "config_hash": hashlib.sha256(json.dumps(parameters, sort_keys=True).encode()).hexdigest(),
            "platform": platform.platform(),
        },
        "details": {
            "label": label,
            "model_id": row.id,
            "max_tanimoto_to_training": predicted["max_tanimoto_to_training"],
            "in_applicability_domain": predicted["in_applicability_domain"],
            "applicability_threshold": predicted["threshold"],
        },
    }


def _measure(name: str, value: float, method: str, uncertainty: float | None) -> dict[str, Any]:
    return {
        "name": name,
        "value": value,
        "unit": "log10_mol_per_litre",
        "origin": "ml_prediction",
        "method": f"{NOT_EXPERIMENTAL}. {method}",
        "uncertainty": uncertainty,
        "source": None,
    }
