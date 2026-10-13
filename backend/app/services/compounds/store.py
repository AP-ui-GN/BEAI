"""Persist sanitized compounds. Invalid SMILES never reach this insert."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.core.errors import NotFound
from backend.app.db.models import Analysis, CompoundRecord
from backend.app.schemas.analysis import AnalysisResult
from backend.app.services.compounds.chemistry import analysis_payload, parse_molecule


def create_compound(
    smiles: str,
    session: Session,
    settings: Settings,
    *,
    keep_largest_fragment: bool = False,
    source: dict | None = None,
) -> tuple[CompoundRecord, Analysis, bool]:
    """Return the row, its descriptor analysis, and whether it already existed."""

    parsed = parse_molecule(
        smiles,
        keep_largest_fragment=keep_largest_fragment,
        max_heavy_atoms=settings.max_heavy_atoms,
    )
    existing = session.scalar(select(CompoundRecord).where(CompoundRecord.inchikey == parsed["inchikey"]))
    if existing is not None:
        analysis = _latest(session, existing.id)
        if analysis is None:
            analysis = _save_analysis(session, existing, parsed, smiles)
        return existing, analysis, True
    now = datetime.now(UTC)
    row = CompoundRecord(
        id=str(uuid.uuid4()),
        input_smiles=smiles.strip(),
        canonical_smiles=parsed["canonical_smiles"],
        inchikey=parsed["inchikey"],
        source_json=source,
        created_at=now,
    )
    session.add(row)
    session.flush()
    analysis = _save_analysis(session, row, parsed, smiles)
    session.commit()
    session.refresh(row)
    session.refresh(analysis)
    return row, analysis, False


def _save_analysis(session: Session, row: CompoundRecord, parsed: dict, smiles: str) -> Analysis:
    digest = hashlib.sha256(smiles.strip().encode("utf-8")).hexdigest()
    payload = analysis_payload(parsed, compound_id=row.id, input_smiles=smiles.strip(), sha256=digest)
    result = AnalysisResult.model_validate(payload)
    now = datetime.now(UTC)
    analysis = Analysis(
        id=result.analysis_id,
        kind="compound_descriptors",
        status="succeeded",
        created_at=now,
        started_at=now,
        completed_at=now,
        structure_id=None,
        sequence_id=None,
        compound_id=row.id,
        result_json=result.model_dump(mode="json"),
        error_json=None,
    )
    session.add(analysis)
    session.commit()
    session.refresh(analysis)
    return analysis


def _latest(session: Session, compound_id: str) -> Analysis | None:
    statement = (
        select(Analysis)
        .where(Analysis.compound_id == compound_id, Analysis.kind == "compound_descriptors")
        .order_by(Analysis.created_at.desc())
    )
    return session.scalars(statement).first()


def get_compound(session: Session, compound_id: str) -> CompoundRecord:
    row = session.get(CompoundRecord, compound_id)
    if row is None:
        raise NotFound("Compound not found.")
    return row


def list_compounds(session: Session) -> list[CompoundRecord]:
    statement = select(CompoundRecord).order_by(CompoundRecord.created_at.desc())
    return list(session.scalars(statement))
