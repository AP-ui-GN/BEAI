"""Docking routes. Missing Vina or Meeko is HTTP 503."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from backend.app.api.routes.jobs import get_runner, to_job_response
from backend.app.db.session import get_session
from backend.app.schemas.job import JobResponse
from backend.app.services.docking.job import require_docking
from backend.app.services.structure.ingest import get_structure

router = APIRouter(prefix="/api/docking", tags=["docking"])


class DockingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    structure_id: str
    ligand_smiles: str
    ligand_resname: str | None = None
    center: list[float] | None = None
    size: list[float] = Field(default_factory=lambda: [20.0, 20.0, 20.0])
    exhaustiveness: int = 8
    num_modes: int = 3
    seed: int = 1


@router.post("", status_code=202, response_model=JobResponse)
def start_docking(
    body: DockingRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> JobResponse:
    require_docking()
    get_structure(session, body.structure_id)
    if body.ligand_resname is None and (body.center is None or len(body.center) != 3):
        from backend.app.core.errors import InvalidInput

        raise InvalidInput("Provide a ligand residue name or a box center.")
    job = get_runner(request).submit(
        "docking",
        body.model_dump(),
        structure_id=body.structure_id,
    )
    return to_job_response(job)
