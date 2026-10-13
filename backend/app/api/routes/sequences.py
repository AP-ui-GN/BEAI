"""Sequence upload, statistics, and pairwise alignment."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.routes.analyses import _detail
from backend.app.core.config import Settings
from backend.app.core.errors import InvalidInput
from backend.app.core.timeutil import utc_iso
from backend.app.data_access.http import ExternalHttp
from backend.app.data_access.uniprot import fetch_sequence
from backend.app.db.models import Analysis, SequenceRecord
from backend.app.db.session import get_session
from backend.app.schemas.analysis import AnalysisDetail, AnalysisResult
from backend.app.schemas.sequence import (
    SequenceAlignRequest,
    SequenceCreate,
    SequenceImportRequest,
    SequenceListResponse,
    SequenceResponse,
)
from backend.app.services.sequence.align import align_sequences
from backend.app.services.sequence.store import get_sequence, ingest_sequence_text, list_sequences

router = APIRouter(prefix="/api/sequences", tags=["sequences"])


def _sequence_response(row: SequenceRecord, analysis: Analysis) -> SequenceResponse:
    messages = list((row.validation_json or {}).get("messages") or [])
    return SequenceResponse(
        id=row.id,
        header=row.header,
        sequence=row.sequence,
        length=len(row.sequence),
        sha256=row.sha256,
        created_at=utc_iso(row.created_at),
        validation_messages=messages,
        source=row.source_json,
        analysis=_detail(analysis, None),
    )


def _latest_analysis(session: Session, sequence_id: str) -> Analysis:
    statement = (
        select(Analysis)
        .where(Analysis.sequence_id == sequence_id, Analysis.kind == "sequence_statistics")
        .order_by(Analysis.created_at.desc())
    )
    row = session.scalars(statement).first()
    if row is None:
        raise InvalidInput("This sequence has no statistics analysis.")
    return row


@router.post("", status_code=201, response_model=SequenceListResponse)
def create_sequences(
    body: SequenceCreate,
    request: Request,
    session: Session = Depends(get_session),
) -> SequenceListResponse:
    settings: Settings = request.app.state.settings
    stored = ingest_sequence_text(body.text, session, settings)
    return SequenceListResponse(sequences=[_sequence_response(row, analysis) for row, analysis in stored])


@router.post("/upload", status_code=201, response_model=SequenceListResponse)
async def upload_sequences(
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> SequenceListResponse:
    settings: Settings = request.app.state.settings
    raw = await file.read()
    if len(raw) > settings.max_upload_bytes:
        raise InvalidInput("The sequence file exceeds the upload limit.")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InvalidInput("The sequence file is not UTF-8 text.") from exc
    stored = ingest_sequence_text(text, session, settings)
    return SequenceListResponse(sequences=[_sequence_response(row, analysis) for row, analysis in stored])


@router.get("", response_model=SequenceListResponse)
def get_sequences(session: Session = Depends(get_session)) -> SequenceListResponse:
    rows = []
    for row in list_sequences(session):
        rows.append(_sequence_response(row, _latest_analysis(session, row.id)))
    return SequenceListResponse(sequences=rows)


@router.get("/{sequence_id}", response_model=SequenceResponse)
def get_sequence_by_id(sequence_id: str, session: Session = Depends(get_session)) -> SequenceResponse:
    row = get_sequence(session, sequence_id)
    return _sequence_response(row, _latest_analysis(session, row.id))


@router.post("/import", status_code=201, response_model=SequenceResponse)
def import_sequence(
    body: SequenceImportRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> SequenceResponse:
    settings: Settings = request.app.state.settings
    http: ExternalHttp = request.app.state.http
    fetched = fetch_sequence(http, body.accession)
    text = f">{fetched['header']}\n{fetched['sequence']}\n"
    stored = ingest_sequence_text(text, session, settings, source=fetched["source"])
    if len(stored) != 1:
        raise InvalidInput("UniProt import expected one sequence.")
    row, analysis = stored[0]
    return _sequence_response(row, analysis)


@router.post("/align", status_code=201, response_model=AnalysisDetail)
def align(
    body: SequenceAlignRequest,
    session: Session = Depends(get_session),
) -> AnalysisDetail:
    left = get_sequence(session, body.left_id)
    right = get_sequence(session, body.right_id)
    payload = align_sequences(
        left.sequence,
        right.sequence,
        left_id=left.id,
        right_id=right.id,
        left_sha256=left.sha256,
        right_sha256=right.sha256,
    )
    result = AnalysisResult.model_validate(payload)
    now = datetime.now(UTC)
    analysis = Analysis(
        id=result.analysis_id,
        kind="sequence_alignment",
        status="succeeded",
        created_at=now,
        started_at=now,
        completed_at=now,
        structure_id=None,
        sequence_id=left.id,
        result_json=result.model_dump(mode="json"),
        error_json=None,
    )
    session.add(analysis)
    session.commit()
    session.refresh(analysis)
    return _detail(analysis, None)
