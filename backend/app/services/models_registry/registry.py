"""Register models and describe them from the database plus the live machine."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.capabilities import probe_executable, probe_import
from backend.app.core.errors import InvalidInput, NotFound
from backend.app.core.timeutil import utc_iso
from backend.app.db.models import Job, RegisteredModel
from backend.app.services.models_registry.hardware import read_hardware
from backend.app.services.models_registry.runtime import ModelRuntime, resolve_weights_path


def register_model(session: Session, payload: dict[str, Any]) -> RegisteredModel:
    """Insert one registry row. This does not download or load weights."""

    name = payload["name"].strip()
    version = payload["version"].strip()
    existing = session.scalar(
        select(RegisteredModel).where(RegisteredModel.name == name, RegisteredModel.version == version)
    )
    if existing is not None:
        raise InvalidInput(f"A model named {name} version {version} is already registered.")
    weights = payload.get("weights_relative")
    if weights:
        resolve_weights_path(weights)
    checksum = payload.get("checksum_sha256")
    if checksum is not None and (len(checksum) != 64 or any(char not in "0123456789abcdef" for char in checksum)):
        raise InvalidInput("checksum_sha256 must be 64 lowercase hex characters.")
    row = RegisteredModel(
        id=str(uuid.uuid4()),
        name=name,
        version=version,
        task=payload["task"].strip(),
        source_url=payload["source_url"].strip(),
        licence=payload["licence"].strip(),
        dependencies_json=[dict(item) for item in payload["dependencies"]],
        hardware_json={
            "min_ram_bytes": int(payload["hardware"]["min_ram_bytes"]),
            "device": payload["hardware"]["device"],
        },
        input_format=payload["input_format"].strip(),
        output_format=payload["output_format"].strip(),
        benchmark_json=payload.get("benchmark"),
        known_limitations=payload["known_limitations"].strip(),
        checksum_sha256=checksum,
        weights_relative=weights,
        loader_key=payload["loader_key"],
        created_at=datetime.now(UTC),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def get_model_row(session: Session, model_id: str) -> RegisteredModel:
    row = session.get(RegisteredModel, model_id)
    if row is None:
        raise NotFound("Model not found.")
    return row


def list_model_views(session: Session, runtime: ModelRuntime) -> dict[str, Any]:
    hardware = read_hardware()
    rows = list(
        session.scalars(select(RegisteredModel).order_by(RegisteredModel.created_at.desc(), RegisteredModel.id.desc()))
    )
    jobs = list(session.scalars(select(Job).where(Job.kind == "model_training")))
    return {
        "hardware": hardware,
        "models": [model_view(row, runtime, hardware, jobs) for row in rows],
    }


def model_view(
    row: RegisteredModel,
    runtime: ModelRuntime,
    hardware: dict[str, Any],
    jobs: list[Job],
) -> dict[str, Any]:
    """Build the API view. Status and compatibility are computed, not stored as facts."""

    dependencies = [_dependency_status(item) for item in row.dependencies_json]
    missing = [item["reason"] for item in dependencies if not item["available"] and item["reason"]]
    compatibility = _compatibility(row.hardware_json, hardware)
    loaded = runtime.is_loaded(row.id)
    info = runtime.info(row.id) or {}
    if missing:
        status = "disabled"
        status_reason = " ".join(missing)
    elif not compatibility["compatible"]:
        status = "incompatible"
        status_reason = " ".join(compatibility["reasons"])
    elif loaded:
        status = "loaded"
        status_reason = None
    else:
        status = "ready"
        status_reason = None
    training = [
        {
            "id": job.id,
            "status": job.status,
            "progress": job.progress,
            "created_at": utc_iso(job.created_at),
        }
        for job in jobs
        if isinstance(job.payload_json, dict) and job.payload_json.get("model_id") == row.id
    ]
    training.sort(key=lambda item: item["created_at"], reverse=True)
    view = {
        "id": row.id,
        "name": row.name,
        "version": row.version,
        "task": row.task,
        "source_url": row.source_url,
        "licence": row.licence,
        "dependencies": dependencies,
        "hardware_requirements": dict(row.hardware_json),
        "hardware_compatibility": compatibility,
        "input_format": row.input_format,
        "output_format": row.output_format,
        "benchmark": row.benchmark_json,
        "known_limitations": row.known_limitations,
        "checksum_sha256": row.checksum_sha256,
        "weights_relative": row.weights_relative,
        "loader_key": row.loader_key,
        "status": status,
        "status_reason": status_reason,
        "loaded": loaded,
        "weights_loaded": bool(info.get("weights_loaded")),
        "load_note": info.get("note"),
        "training_jobs": training,
        "created_at": utc_iso(row.created_at),
    }
    view["card_markdown"] = render_card(view)
    return view


def render_card(view: dict[str, Any]) -> str:
    """Markdown card generated from the stored row. It does not add benchmark numbers."""

    benchmark = view["benchmark"]
    if benchmark is None:
        benchmark_text = "No benchmark result is stored."
    else:
        benchmark_text = str(benchmark)
    lines = [
        f"# {view['name']} {view['version']}",
        "",
        f"Task: {view['task']}",
        f"Source: {view['source_url']}",
        f"Licence: {view['licence']}",
        f"Input format: {view['input_format']}",
        f"Output format: {view['output_format']}",
        f"Loader: {view['loader_key']}",
        f"Hardware requirement: {view['hardware_requirements']}",
        "",
        "## Benchmark",
        "",
        benchmark_text,
        "",
        "## Known limitations",
        "",
        view["known_limitations"],
        "",
        "Predictions from this entry use origin ml_prediction and are labelled not experimental.",
    ]
    return "\n".join(lines)


def _dependency_status(item: dict[str, Any]) -> dict[str, Any]:
    kind = item.get("kind")
    name = str(item.get("name") or "")
    if kind == "python":
        probed = probe_import(name, name)
    elif kind == "executable":
        probed = probe_executable([name], name)
    else:
        probed = {"available": False, "version": None, "reason": f"Unknown dependency kind: {kind}."}
    return {"kind": kind, "name": name, **probed}


def _compatibility(requirements: dict[str, Any], hardware: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    required = int(requirements["min_ram_bytes"])
    available = int(hardware["ram_available_bytes"])
    if required > available:
        reasons.append(f"Declared minimum RAM {required} bytes exceeds available RAM {available} bytes.")
    device = requirements.get("device")
    if device == "cuda" and not hardware["cuda"]["available"]:
        reason = hardware["cuda"]["reason"] or "CUDA is not available."
        reasons.append(f"This model declares device cuda. {reason}")
    elif device == "mps" and not hardware["mps"]["available"]:
        reason = hardware["mps"]["reason"] or "MPS is not available."
        reasons.append(f"This model declares device mps. {reason}")
    elif device not in {"cpu", "cuda", "mps"}:
        reasons.append(f"Unknown device requirement: {device}.")
    return {"compatible": not reasons, "reasons": reasons}
