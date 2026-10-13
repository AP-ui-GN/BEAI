"""Generation route. Liability filters stay on."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from backend.app.api.routes.analyses import _detail
from backend.app.db.models import Analysis
from backend.app.db.session import get_session
from backend.app.schemas.analysis import AnalysisDetail
from backend.app.services.generation.brics import generate

router = APIRouter(prefix="/api/generation", tags=["generation"])


class GenerationRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    references: list[str] = Field(min_length=1)
    objectives: list[dict] = Field(min_length=1)
    seed: int = 1
    count: int = Field(default=5, ge=1, le=20)
    filters_off: bool | None = None
    disable_filters: bool | None = None


@router.post("", status_code=201, response_model=AnalysisDetail)
def create_generation(
    body: GenerationRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> AnalysisDetail:
    del request
    payload = body.model_dump()
    result = generate(payload)
    result["analysis_id"] = result.get("analysis_id") or str(uuid.uuid4())
    now = datetime.now(UTC)
    analysis = Analysis(
        id=result["analysis_id"],
        kind="molecular_generation",
        status="succeeded",
        created_at=now,
        started_at=now,
        completed_at=now,
        result_json=result,
        error_json=None,
    )
    session.add(analysis)
    session.commit()
    return _detail(analysis, None)
