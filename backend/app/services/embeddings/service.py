"""Store embeddings and rank stored neighbours. Loaders run only when asked."""

from __future__ import annotations

import hashlib
import json
import platform
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.errors import InvalidInput
from backend.app.core.timeutil import utc_iso
from backend.app.db.models import Analysis, RegisteredModel, SequenceEmbedding, SequenceRecord
from backend.app.services.embeddings.constants import NOT_EXPERIMENTAL
from backend.app.services.embeddings.vectors import cosine
from backend.app.services.models_registry.registry import get_model_row, model_view
from backend.app.services.models_registry.runtime import ModelRuntime


def embed_sequence(
    session: Session,
    runtime: ModelRuntime,
    sequence: SequenceRecord,
    model_id: str,
) -> dict[str, Any]:
    """Embed one stored sequence. A limit failure stores nothing."""

    row = get_model_row(session, model_id)
    _require_loadable(session, runtime, row)
    artifact = runtime.load(row)
    embed = artifact.get("embed")
    if not callable(embed):
        raise InvalidInput("This model does not produce embeddings.")
    vector = embed(sequence.sequence)
    if not isinstance(vector, list) or not vector:
        raise InvalidInput("The embedder returned no vector.")
    label = NOT_EXPERIMENTAL
    now = datetime.now(UTC)
    stored = session.scalar(
        select(SequenceEmbedding).where(
            SequenceEmbedding.sequence_id == sequence.id,
            SequenceEmbedding.model_id == row.id,
        )
    )
    if stored is None:
        stored = SequenceEmbedding(
            id=str(uuid.uuid4()),
            sequence_id=sequence.id,
            model_id=row.id,
            model_version=row.version,
            input_sha256=sequence.sha256,
            vector_json=vector,
            label=label,
            created_at=now,
        )
        session.add(stored)
    else:
        stored.model_version = row.version
        stored.input_sha256 = sequence.sha256
        stored.vector_json = vector
        stored.label = label
        stored.created_at = now
    result = _embedding_result(sequence, row, vector, artifact, label)
    analysis = Analysis(
        id=result["analysis_id"],
        kind="sequence_embedding",
        status="succeeded",
        created_at=now,
        started_at=now,
        completed_at=now,
        sequence_id=sequence.id,
        result_json=result,
        error_json=None,
    )
    session.add(analysis)
    session.commit()
    return result


def neighbours(
    session: Session,
    sequence: SequenceRecord,
    model_id: str,
) -> dict[str, Any]:
    """Rank other stored embeddings for the same model by cosine similarity."""

    row = get_model_row(session, model_id)
    query = session.scalar(
        select(SequenceEmbedding).where(
            SequenceEmbedding.sequence_id == sequence.id,
            SequenceEmbedding.model_id == row.id,
        )
    )
    if query is None:
        raise InvalidInput("No embedding is stored for this sequence and model.")
    others = list(session.scalars(select(SequenceEmbedding).where(SequenceEmbedding.model_id == row.id)))
    ranked: list[dict[str, Any]] = []
    warnings: list[str] = []
    for item in others:
        if item.sequence_id == sequence.id:
            continue
        other = session.get(SequenceRecord, item.sequence_id)
        value = cosine(list(query.vector_json), list(item.vector_json))
        if value is None:
            warnings.append(f"Cosine similarity with {item.sequence_id} is null because a vector has zero length.")
        ranked.append(
            {
                "sequence_id": item.sequence_id,
                "header": other.header if other is not None else None,
                "cosine_similarity": value,
                "origin": "calculated",
                "embedding_label": item.label,
            }
        )
    ranked.sort(key=lambda item: (item["cosine_similarity"] is None, -(item["cosine_similarity"] or 0.0)))
    now = datetime.now(UTC)
    result = _neighbour_result(sequence, row, query, ranked, warnings)
    session.add(
        Analysis(
            id=result["analysis_id"],
            kind="embedding_neighbours",
            status="succeeded",
            created_at=now,
            started_at=now,
            completed_at=now,
            sequence_id=sequence.id,
            result_json=result,
            error_json=None,
        )
    )
    session.commit()
    return result


def _require_loadable(session: Session, runtime: ModelRuntime, row: RegisteredModel) -> None:
    from backend.app.services.models_registry.hardware import read_hardware

    hardware = read_hardware()
    view = model_view(row, runtime, hardware, [])
    if view["status"] == "disabled":
        from backend.app.core.errors import CapabilityUnavailable

        raise CapabilityUnavailable(view["status_reason"] or "This model is disabled.")
    if view["status"] == "incompatible":
        raise InvalidInput(view["status_reason"] or "This model is not compatible with this machine.")


def _embedding_result(
    sequence: SequenceRecord,
    row: RegisteredModel,
    vector: list[float],
    artifact: dict[str, Any],
    label: str,
) -> dict[str, Any]:
    pooling = str(artifact.get("pooling") or "")
    parameters = {
        "model_name": row.name,
        "model_version": row.version,
        "loader_key": row.loader_key,
        "token_limit": row.token_limit,
        "pooling": pooling,
        "label": label,
    }
    now = datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    return {
        "analysis_id": str(uuid.uuid4()),
        "kind": "sequence_embedding",
        "created_at": now,
        "status": "succeeded",
        "inputs": [
            {
                "role": "sequence",
                "filename": None,
                "source_id": sequence.id,
                "sha256": sequence.sha256,
                "validation_status": "valid",
                "validation_messages": [],
            }
        ],
        "methods": [
            {
                "name": "sequence_embedding",
                "software": row.name,
                "version": row.version,
                "parameters": parameters,
            }
        ],
        "measurements": [
            {
                "name": "mean_pooled_embedding",
                "value": vector,
                "unit": None,
                "origin": "ml_prediction",
                "method": f"{label}. {pooling}",
                "uncertainty": None,
                "source": row.source_url,
            }
        ],
        "evidence": [],
        "limitations": [
            "This embedding is an ML prediction, not an experimental measurement.",
            "It is not evidence of function, structure, binding, or clinical effect.",
        ],
        "warnings": [],
        "skipped_stages": [],
        "errors": [],
        "reproducibility": _reproducibility(parameters),
        "details": {
            "label": label,
            "model_id": row.id,
            "model_version": row.version,
            "input_sha256": sequence.sha256,
            "weights_loaded": bool(artifact.get("weights_loaded")),
        },
    }


def _neighbour_result(
    sequence: SequenceRecord,
    row: RegisteredModel,
    query: SequenceEmbedding,
    ranked: list[dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    parameters = {"model_id": row.id, "model_version": row.version, "similarity": "cosine"}
    now = utc_iso(datetime.now(UTC))
    return {
        "analysis_id": str(uuid.uuid4()),
        "kind": "embedding_neighbours",
        "created_at": now,
        "status": "succeeded",
        "inputs": [
            {
                "role": "sequence",
                "filename": None,
                "source_id": sequence.id,
                "sha256": sequence.sha256,
                "validation_status": "valid",
                "validation_messages": [],
            }
        ],
        "methods": [
            {
                "name": "embedding_cosine",
                "software": "numpy",
                "version": numpy_version(),
                "parameters": parameters,
            }
        ],
        "measurements": [
            {
                "name": "neighbour_cosine_similarities",
                "value": [
                    {"sequence_id": item["sequence_id"], "cosine_similarity": item["cosine_similarity"]}
                    for item in ranked
                ],
                "unit": "1",
                "origin": "calculated",
                "method": "Cosine similarity of stored embedding vectors. Not sequence identity or function.",
                "uncertainty": None,
                "source": None,
            }
        ],
        "evidence": [],
        "limitations": [
            "Neighbour rank is cosine similarity of stored vectors.",
            "It is not sequence identity, homology, function, or structure.",
            f"The source embeddings are labelled {query.label}.",
        ],
        "warnings": warnings,
        "skipped_stages": [],
        "errors": [],
        "reproducibility": _reproducibility(parameters),
        "details": {"label": query.label, "neighbours": ranked, "model_id": row.id},
    }


def numpy_version() -> str:
    import numpy

    return str(numpy.__version__)


def _reproducibility(parameters: dict[str, Any]) -> dict[str, Any]:
    return {
        "software_versions": {"python": platform.python_version(), "numpy": numpy_version()},
        "random_seed": None,
        "config_hash": hashlib.sha256(json.dumps(parameters, sort_keys=True, default=str).encode()).hexdigest(),
        "platform": platform.platform(),
    }
