"""Workflow routes. LLM drafting and summaries stay off unless the env var is set."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from backend.app.api.routes.analyses import _detail
from backend.app.core.config import Settings
from backend.app.core.errors import CapabilityUnavailable, NotFound
from backend.app.db.models import Analysis
from backend.app.db.session import get_session
from backend.app.schemas.analysis import AnalysisDetail
from backend.app.services.workflows.execute import check_citations, execute_workflow

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


class WorkflowStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    service: str
    parameters: dict = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)


class WorkflowRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    steps: list[WorkflowStep] = Field(min_length=1)
    resume_from: str | None = None


class SummaryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    retrieved_ids: list[str]


@router.post("", status_code=201, response_model=AnalysisDetail)
def run_workflow(
    body: WorkflowRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> AnalysisDetail:
    settings: Settings = request.app.state.settings
    prior = None
    if body.resume_from:
        previous = session.get(Analysis, body.resume_from)
        if previous is None or not previous.result_json:
            raise NotFound("Workflow run not found.")
        prior = dict((previous.result_json.get("details") or {}).get("steps") or {})
    result = execute_workflow(body.model_dump(), session, settings, prior=prior)
    now = datetime.now(UTC)
    analysis = Analysis(
        id=result["analysis_id"],
        kind="workflow",
        status=str(result["status"]),
        created_at=now,
        started_at=now,
        completed_at=now,
        result_json=result,
        error_json=None,
    )
    session.add(analysis)
    session.commit()
    return _detail(analysis, None)


@router.post("/summarize")
def summarize(body: SummaryRequest, request: Request) -> dict[str, str]:
    settings: Settings = request.app.state.settings
    if not settings.llm_enabled:
        raise CapabilityUnavailable("LLM features are off.")
    check_citations(body.summary, set(body.retrieved_ids))
    return {"label": "ml_generated", "summary": body.summary}
