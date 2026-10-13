"""Persist validated sequences and their statistics analyses."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.core.errors import InvalidInput, NotFound
from backend.app.db.models import Analysis, SequenceRecord
from backend.app.schemas.analysis import AnalysisResult
from backend.app.services.sequence.fasta import parse_fasta, sequence_sha256, validate_protein_sequence
from backend.app.services.sequence.stats import sequence_statistics


def ingest_sequence_text(
    text: str,
    session: Session,
    settings: Settings,
    source: dict | None = None,
) -> list[tuple[SequenceRecord, Analysis]]:
    """Validate every record first. A bad record stores nothing."""

    parsed = parse_fasta(text)
    if len(text.encode("utf-8")) > settings.max_upload_bytes:
        raise InvalidInput("The sequence text exceeds the upload limit.")
    cleaned: list[tuple[str, str, list[str]]] = []
    for header, raw in parsed:
        sequence, messages = validate_protein_sequence(raw)
        if len(sequence) > settings.max_sequence_length:
            raise InvalidInput(
                f"A sequence is {len(sequence)} residues, above the limit of {settings.max_sequence_length}."
            )
        cleaned.append((header, sequence, messages))
    now = datetime.now(UTC)
    stored: list[tuple[SequenceRecord, Analysis]] = []
    for header, sequence, messages in cleaned:
        row = SequenceRecord(
            id=str(uuid.uuid4()),
            header=header,
            sequence=sequence,
            sha256=sequence_sha256(sequence),
            created_at=now,
            source_json=source,
            validation_json={"messages": messages},
        )
        session.add(row)
        session.flush()
        payload = sequence_statistics(
            sequence,
            source_id=row.id,
            header=header,
            sha256=row.sha256,
            validation_messages=messages,
        )
        result = AnalysisResult.model_validate(payload)
        analysis = Analysis(
            id=result.analysis_id,
            kind="sequence_statistics",
            status="succeeded",
            created_at=now,
            started_at=now,
            completed_at=now,
            structure_id=None,
            sequence_id=row.id,
            result_json=result.model_dump(mode="json"),
            error_json=None,
        )
        session.add(analysis)
        stored.append((row, analysis))
    session.commit()
    for row, analysis in stored:
        session.refresh(row)
        session.refresh(analysis)
    return stored


def get_sequence(session: Session, sequence_id: str) -> SequenceRecord:
    row = session.get(SequenceRecord, sequence_id)
    if row is None:
        raise NotFound("Sequence not found.")
    return row


def list_sequences(session: Session) -> list[SequenceRecord]:
    statement = select(SequenceRecord).order_by(SequenceRecord.created_at.desc(), SequenceRecord.id.desc())
    return list(session.scalars(statement))
