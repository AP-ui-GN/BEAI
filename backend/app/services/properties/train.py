"""Scaffold-split solubility models. Test rows are not used to choose settings."""

from __future__ import annotations

import csv
import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy
from rdkit import Chem
from rdkit.Chem import Descriptors
from rdkit.Chem.Scaffolds import MurckoScaffold
from sklearn.linear_model import Ridge

from backend.app.core.config import repo_root
from backend.app.core.errors import InvalidInput
from backend.app.services.properties.constants import (
    APPLICABILITY_MAX_TANIMOTO,
    BOOTSTRAP_RESAMPLES,
    BOOTSTRAP_SEED,
    DATASET_SHA256,
    DESCRIPTOR_NAMES,
    ENSEMBLE_SIZE,
    GNN_EPOCHS,
    GNN_HIDDEN,
    GNN_LR,
    MORGAN_BITS,
    MORGAN_RADIUS,
    RIDGE_ALPHA,
    SMILES_COLUMN,
    SPLIT_SEED,
    TARGET_COLUMN,
    TEST_FRACTION,
)

_DESCRIPTOR_FUNCTIONS = {
    "MolWt": Descriptors.MolWt,
    "MolLogP": Descriptors.MolLogP,
    "TPSA": Descriptors.TPSA,
    "NumHDonors": Descriptors.NumHDonors,
    "NumHAcceptors": Descriptors.NumHAcceptors,
    "NumRotatableBonds": Descriptors.NumRotatableBonds,
    "RingCount": Descriptors.RingCount,
}


def dataset_path() -> Path:
    return repo_root() / "data" / "solubility" / "delaney-processed.csv"


def artifact_dir() -> Path:
    return repo_root() / "models" / "esol"


def verify_dataset(path: Path) -> None:
    """Refuse a file whose sha256 is not the recorded Delaney checksum."""

    if not path.is_file():
        raise InvalidInput("The Delaney solubility file is not on disk.")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != DATASET_SHA256:
        raise InvalidInput("The Delaney file checksum does not match the recorded sha256.")


def read_table(path: Path) -> tuple[list[dict[str, Any]], int]:
    """Return valid rows and the count of rows that were dropped."""

    dropped = 0
    rows: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        names = reader.fieldnames or []
        if TARGET_COLUMN not in names or SMILES_COLUMN not in names:
            raise InvalidInput("The table is missing the measured solubility or SMILES column.")
        for raw in reader:
            smiles = (raw.get(SMILES_COLUMN) or "").strip()
            try:
                measured = float(raw[TARGET_COLUMN])
            except (TypeError, ValueError):
                dropped += 1
                continue
            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                dropped += 1
                continue
            scaffold = MurckoScaffold.MurckoScaffoldSmiles(mol=mol, includeChirality=False) or "no_scaffold"
            rows.append(
                {
                    "smiles": smiles,
                    "measured": measured,
                    "scaffold": scaffold,
                    "mol": mol,
                }
            )
    if len(rows) < 8:
        raise InvalidInput("Too few valid rows to train.")
    return rows, dropped


def scaffold_split(rows: list[dict[str, Any]], seed: int = SPLIT_SEED) -> tuple[list[int], list[int]]:
    """Assign whole Murcko scaffolds. The scaffold order is shuffled with ``seed``."""

    groups: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        groups[row["scaffold"]].append(index)
    scaffolds = sorted(groups)
    rng = numpy.random.default_rng(seed)
    order = rng.permutation(len(scaffolds))
    target = max(1, int(round(len(rows) * TEST_FRACTION)))
    test: list[int] = []
    for position in order:
        if len(test) >= target:
            break
        test.extend(groups[scaffolds[int(position)]])
    test_set = set(test)
    train = [index for index in range(len(rows)) if index not in test_set]
    if not train or not test:
        raise InvalidInput("The scaffold split left a side empty.")
    return train, test


def _descriptors(mol: Chem.Mol) -> list[float]:
    return [float(_DESCRIPTOR_FUNCTIONS[name](mol)) for name in DESCRIPTOR_NAMES]


def _fingerprint(mol: Chem.Mol) -> numpy.ndarray:
    bitvect = _morgan_generator().GetFingerprint(mol)
    array = numpy.zeros((MORGAN_BITS,), dtype=numpy.uint8)
    Chem.DataStructs.ConvertToNumpyArray(bitvect, array)
    return array


def _morgan_generator():
    global _MORGAN
    if _MORGAN is None:
        from rdkit.Chem import rdFingerprintGenerator

        _MORGAN = rdFingerprintGenerator.GetMorganGenerator(radius=MORGAN_RADIUS, fpSize=MORGAN_BITS)
    return _MORGAN


_MORGAN = None


def regression_metrics(y_true: numpy.ndarray, y_pred: numpy.ndarray) -> dict[str, Any]:
    """RMSE, MAE, and R-squared, with a percentile bootstrap fixed before the run."""

    y = numpy.asarray(y_true, dtype=float)
    pred = numpy.asarray(y_pred, dtype=float)
    point = _point_metrics(y, pred)
    rng = numpy.random.default_rng(BOOTSTRAP_SEED)
    buckets: dict[str, list[float]] = {"rmse": [], "mae": [], "r2": []}
    count = len(y)
    for _ in range(BOOTSTRAP_RESAMPLES):
        index = rng.integers(0, count, size=count)
        sample = _point_metrics(y[index], pred[index])
        for name in buckets:
            value = sample[name]
            if value is not None:
                buckets[name].append(value)
    intervals = {}
    for name, values in buckets.items():
        if not values:
            intervals[name] = {"low": None, "high": None}
            continue
        intervals[name] = {
            "low": float(numpy.percentile(values, 2.5)),
            "high": float(numpy.percentile(values, 97.5)),
        }
    return {
        **point,
        "intervals": intervals,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
        "finite_resamples": {name: len(values) for name, values in buckets.items()},
    }


def _point_metrics(y: numpy.ndarray, pred: numpy.ndarray) -> dict[str, float | None]:
    error = pred - y
    rmse = float(numpy.sqrt(numpy.mean(error**2)))
    mae = float(numpy.mean(numpy.abs(error)))
    total = float(numpy.sum((y - float(y.mean())) ** 2))
    r2 = None if total == 0.0 else float(1.0 - numpy.sum(error**2) / total)
    return {"rmse": rmse, "mae": mae, "r2": r2}


def train_models(
    rows: list[dict[str, Any]],
    train_index: list[int],
    test_index: list[int],
    *,
    seed: int = SPLIT_SEED,
    cancelled=None,
    progress=None,
) -> dict[str, Any]:
    """Fit the two Ridge baselines and the GCN. ``cancelled`` stops before writing."""

    def stop() -> bool:
        return bool(cancelled and cancelled())

    if progress:
        progress(0.2)
    x_desc = numpy.asarray([_descriptors(rows[index]["mol"]) for index in range(len(rows))], dtype=float)
    x_fp = numpy.vstack([_fingerprint(rows[index]["mol"]) for index in range(len(rows))])
    y = numpy.asarray([rows[index]["measured"] for index in range(len(rows))], dtype=float)
    if stop():
        return {"cancelled": True}
    train = numpy.asarray(train_index)
    test = numpy.asarray(test_index)
    descriptor = Ridge(alpha=RIDGE_ALPHA)
    descriptor.fit(x_desc[train], y[train])
    fingerprint = Ridge(alpha=RIDGE_ALPHA)
    fingerprint.fit(x_fp[train], y[train])
    rng = numpy.random.default_rng(seed)
    ensemble_coef = []
    ensemble_intercept = []
    for _ in range(ENSEMBLE_SIZE):
        if stop():
            return {"cancelled": True}
        draw = rng.integers(0, len(train), size=len(train))
        member = Ridge(alpha=RIDGE_ALPHA)
        member.fit(x_fp[train][draw], y[train][draw])
        ensemble_coef.append(member.coef_.astype(float))
        ensemble_intercept.append(float(member.intercept_))
    if progress:
        progress(0.55)
    gnn_test = _train_gnn(rows, train_index, test_index, seed=seed, cancelled=stop, progress=progress)
    if gnn_test is None:
        return {"cancelled": True}
    descriptor_pred = descriptor.predict(x_desc[test])
    fingerprint_pred = fingerprint.predict(x_fp[test])
    return {
        "cancelled": False,
        "descriptor": {
            "coef": descriptor.coef_.astype(float),
            "intercept": float(descriptor.intercept_),
            "metrics": regression_metrics(y[test], descriptor_pred),
        },
        "fingerprint": {
            "coef": fingerprint.coef_.astype(float),
            "intercept": float(fingerprint.intercept_),
            "metrics": regression_metrics(y[test], fingerprint_pred),
            "ensemble_coef": numpy.asarray(ensemble_coef, dtype=float),
            "ensemble_intercept": numpy.asarray(ensemble_intercept, dtype=float),
        },
        "gnn": gnn_test,
        "train_fingerprints": x_fp[train].astype(numpy.uint8),
        "train_index": train_index,
        "test_index": test_index,
        "dropped_note": None,
    }


def _train_gnn(rows, train_index, test_index, *, seed: int, cancelled, progress) -> dict[str, Any] | None:
    import torch
    from torch_geometric.data import Batch

    from backend.app.services.properties.gnn import SolubilityGCN, molecule_graph

    graphs = [molecule_graph(row["mol"], row["measured"]) for row in rows]
    torch.manual_seed(seed)
    model = SolubilityGCN()
    optimizer = torch.optim.Adam(model.parameters(), lr=GNN_LR)
    loss_fn = torch.nn.MSELoss()
    train_batch = Batch.from_data_list([graphs[index] for index in train_index])
    test_batch = Batch.from_data_list([graphs[index] for index in test_index])
    model.train()
    for epoch in range(GNN_EPOCHS):
        if cancelled():
            return None
        optimizer.zero_grad()
        pred = model(train_batch.x, train_batch.edge_index, train_batch.batch)
        loss = loss_fn(pred, train_batch.y)
        loss.backward()
        optimizer.step()
        if progress:
            progress(0.55 + 0.35 * ((epoch + 1) / GNN_EPOCHS))
    model.eval()
    with torch.no_grad():
        predicted = model(test_batch.x, test_batch.edge_index, test_batch.batch).detach().numpy()
    return {
        "state": {key: value.detach().cpu() for key, value in model.state_dict().items()},
        "metrics": regression_metrics(test_batch.y.numpy(), predicted),
        "hidden": GNN_HIDDEN,
        "epochs": GNN_EPOCHS,
        "lr": GNN_LR,
    }


def save_artifact(result: dict[str, Any], directory: Path) -> None:
    from safetensors.torch import save_file

    directory.mkdir(parents=True, exist_ok=True)
    numpy.savez(
        directory / "ridge.npz",
        descriptor_coef=result["descriptor"]["coef"],
        descriptor_intercept=numpy.asarray([result["descriptor"]["intercept"]]),
        fingerprint_coef=result["fingerprint"]["coef"],
        fingerprint_intercept=numpy.asarray([result["fingerprint"]["intercept"]]),
        ensemble_coef=result["fingerprint"]["ensemble_coef"],
        ensemble_intercept=result["fingerprint"]["ensemble_intercept"],
        train_fingerprints=result["train_fingerprints"],
    )
    save_file(result["gnn"]["state"], directory / "gnn.safetensors")


def applicability_threshold() -> float:
    return APPLICABILITY_MAX_TANIMOTO
