"""Persist structure_overview runs. Status moves pending, running, then succeeded or failed."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.core.errors import InvalidInput, NotFound
from backend.app.core.timeutil import utc_iso
from backend.app.db.models import Analysis, Structure
from backend.app.schemas.analysis import AnalysisResult
from backend.app.services.structure.ingest import get_structure, structure_file
from backend.app.services.structure.overview import build_structure_overview

logger = logging.getLogger(__name__)


def run_structure_overview(session: Session, settings: Settings, structure_id: str) -> Analysis:
    structure = get_structure(session, structure_id)
    now = datetime.now(UTC)
    analysis = Analysis(
        id=_new_id(),
        kind="structure_overview",
        status="pending",
        created_at=now,
        started_at=None,
        completed_at=None,
        structure_id=structure.id,
        result_json=None,
        error_json=None,
    )
    session.add(analysis)
    session.commit()
    analysis.status = "running"
    analysis.started_at = datetime.now(UTC)
    session.commit()
    try:
        try:
            path = structure_file(settings, structure)
        except NotFound as exc:
            _mark_failed(
                session,
                analysis,
                "invalid_input",
                "The stored structure file could not be read.",
            )
            raise InvalidInput("The stored structure file could not be read.") from exc
        payload = build_structure_overview(
            path,
            structure.format,
            analysis_id=analysis.id,
            created_at=utc_iso(analysis.created_at),
            source_id=structure.id,
            display_filename=structure.display_filename,
            sha256=structure.sha256,
            ca_break_threshold_angstrom=settings.ca_break_threshold_angstrom,
        )
        result = AnalysisResult.model_validate(payload)
        analysis.status = "succeeded"
        analysis.result_json = result.model_dump(mode="json")
        analysis.completed_at = datetime.now(UTC)
        analysis.error_json = None
        session.commit()
        session.refresh(analysis)
        return analysis
    except InvalidInput as exc:
        _mark_failed(session, analysis, exc.code, exc.message)
        raise
    except Exception:
        logger.exception("structure_overview failed")
        _mark_failed(session, analysis, "internal_error", "The analysis failed.")
        raise


def list_analyses(session: Session) -> list[tuple[Analysis, str | None]]:
    statement = select(Analysis).order_by(Analysis.created_at.desc(), Analysis.id.desc())
    rows = list(session.scalars(statement))
    names = _filenames(session, rows)
    return [(row, names.get(row.structure_id or "")) for row in rows]


def get_analysis(session: Session, analysis_id: str) -> tuple[Analysis, str | None]:
    row = session.get(Analysis, analysis_id)
    if row is None:
        raise NotFound("Analysis not found.")
    names = _filenames(session, [row])
    return row, names.get(row.structure_id or "")


def _mark_failed(session: Session, analysis: Analysis, code: str, message: str) -> None:
    analysis.status = "failed"
    analysis.error_json = {"code": code, "message": message}
    analysis.result_json = None
    analysis.completed_at = datetime.now(UTC)
    session.commit()


def _filenames(session: Session, rows: list[Analysis]) -> dict[str, str]:
    ids = {row.structure_id for row in rows if row.structure_id}
    if not ids:
        return {}
    statement = select(Structure).where(Structure.id.in_(ids))
    return {row.id: row.display_filename for row in session.scalars(statement)}


def _new_id() -> str:
    return str(uuid.uuid4())
