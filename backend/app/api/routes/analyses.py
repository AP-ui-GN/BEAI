"""Analysis routes. Scientific work stays in the structure service."""

from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.core.errors import InvalidInput
from backend.app.core.timeutil import utc_iso
from backend.app.db.models import Analysis
from backend.app.db.session import get_session
from backend.app.schemas.analysis import (
    AnalysisCreate,
    AnalysisDetail,
    AnalysisErrorBody,
    AnalysisListResponse,
    AnalysisResult,
    AnalysisSummary,
)
from backend.app.services.reports.render import render_report
from backend.app.services.structure.analyses import get_analysis, list_analyses, run_structure_overview

router = APIRouter(tags=["analyses"])


def _summary(row: Analysis, filename: str | None) -> AnalysisSummary:
    error = None
    if row.error_json:
        error = AnalysisErrorBody.model_validate(row.error_json)
    return AnalysisSummary(
        id=row.id,
        kind=row.kind,
        status=row.status,
        created_at=utc_iso(row.created_at),
        started_at=utc_iso(row.started_at) if row.started_at else None,
        completed_at=utc_iso(row.completed_at) if row.completed_at else None,
        structure_id=row.structure_id,
        structure_filename=filename,
        sequence_id=row.sequence_id,
        compound_id=row.compound_id,
        error=error,
    )


def _detail(row: Analysis, filename: str | None) -> AnalysisDetail:
    result = AnalysisResult.model_validate(row.result_json) if row.result_json else None
    return AnalysisDetail(**_summary(row, filename).model_dump(), result=result)


@router.post(
    "/api/structures/{structure_id}/analyses",
    status_code=201,
    response_model=AnalysisDetail,
)
def create_analysis(
    structure_id: str,
    body: AnalysisCreate,
    request: Request,
    session: Session = Depends(get_session),
) -> AnalysisDetail:
    settings: Settings = request.app.state.settings
    if body.kind != "structure_overview":
        raise InvalidInput("Only structure_overview is implemented.")
    row, filename = _run(session, settings, structure_id)
    return _detail(row, filename)


def _run(session: Session, settings: Settings, structure_id: str) -> tuple[Analysis, str | None]:
    row = run_structure_overview(session, settings, structure_id)
    return get_analysis(session, row.id)


@router.get("/api/analyses", response_model=AnalysisListResponse)
def get_analyses(session: Session = Depends(get_session)) -> AnalysisListResponse:
    return AnalysisListResponse(analyses=[_summary(row, filename) for row, filename in list_analyses(session)])


@router.get("/api/analyses/{analysis_id}", response_model=AnalysisDetail)
def get_analysis_by_id(
    analysis_id: str,
    session: Session = Depends(get_session),
) -> AnalysisDetail:
    row, filename = get_analysis(session, analysis_id)
    return _detail(row, filename)


@router.get("/api/analyses/{analysis_id}/report")
def download_report(
    analysis_id: str,
    report_format: Literal["html", "md", "json"] = Query(alias="format"),
    session: Session = Depends(get_session),
) -> Response:
    row, _filename = get_analysis(session, analysis_id)
    if row.result_json is None:
        raise InvalidInput("This analysis has no stored result to report.")
    body, media_type, suffix = render_report(row.result_json, report_format)
    download_name = f"beai-{row.id}.{suffix}"
    return Response(
        content=body,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )
