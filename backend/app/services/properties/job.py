"""Train solubility models as a job. Progress is the stage fraction, not a timer."""

from __future__ import annotations

import json
from typing import Any

from backend.app.core.errors import InvalidInput
from backend.app.jobs.runner import JobContext
from backend.app.services.properties.train import (
    artifact_dir,
    read_table,
    save_artifact,
    scaffold_split,
    train_models,
    verify_dataset,
)


def run_solubility_job(context: JobContext, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Fit on the checksummed table unless the job is cancelled between stages."""

    path_text = payload.get("dataset_path")
    from pathlib import Path

    path = Path(path_text) if path_text else None
    if path is None:
        from backend.app.services.properties.train import dataset_path

        path = dataset_path()
    if payload.get("require_checksum", True):
        verify_dataset(path)
    if context.cancelled():
        return None
    context.set_progress(0.05)
    rows, dropped = read_table(path)
    if context.cancelled():
        return None
    train_index, test_index = scaffold_split(rows, seed=int(payload.get("seed") or 20261013))
    context.set_progress(0.15)
    result = train_models(
        rows,
        train_index,
        test_index,
        seed=int(payload.get("seed") or 20261013),
        cancelled=context.cancelled,
        progress=context.set_progress,
    )
    if result.get("cancelled") or context.cancelled():
        return None
    directory = artifact_dir()
    save_artifact(result, directory)
    metrics = {
        "dropped_rows": dropped,
        "train_count": len(train_index),
        "test_count": len(test_index),
        "descriptor_ridge": result["descriptor"]["metrics"],
        "fingerprint_ridge": result["fingerprint"]["metrics"],
        "gcn": result["gnn"]["metrics"],
        "seed": int(payload.get("seed") or 20261013),
    }
    (directory / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    _store_benchmark(context, payload.get("model_id"), metrics)
    return {
        "kind": "solubility_training",
        "status": "succeeded",
        "created_at": _now(),
        "inputs": [],
        "methods": [],
        "measurements": [],
        "evidence": [],
        "limitations": ["Training metrics are on the scaffold-held-out rows. They are not experimental measurements."],
        "warnings": [],
        "skipped_stages": [],
        "errors": [],
        "reproducibility": {
            "software_versions": {},
            "random_seed": int(payload.get("seed") or 20261013),
            "config_hash": "solubility",
            "platform": "local",
        },
        "details": metrics,
    }


def _now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _store_benchmark(context: JobContext, model_id: str | None, metrics: dict[str, Any]) -> None:
    if not model_id:
        return
    session = context.runner.factory()
    try:
        from backend.app.db.models import RegisteredModel

        row = session.get(RegisteredModel, model_id)
        if row is None:
            raise InvalidInput("The solubility model row is missing.")
        row.benchmark_json = metrics
        session.commit()
    finally:
        session.close()
