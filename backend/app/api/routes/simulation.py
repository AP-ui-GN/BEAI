"""Simulation routes. Missing OpenMM is HTTP 503. Step counts are capped."""

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from backend.app.api.routes.jobs import get_runner, to_job_response
from backend.app.core.errors import InvalidInput
from backend.app.schemas.job import JobResponse
from backend.app.services.simulation.constants import MAX_MIN_ITERATIONS, MAX_STEPS
from backend.app.services.simulation.engine import require_openmm

router = APIRouter(prefix="/api/simulation", tags=["simulation"])


class SimulationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    structure_id: str
    mode: str = "minimization"
    ph: float = 7.0
    seed: int = 1
    max_iterations: int = Field(default=20, ge=1, le=MAX_MIN_ITERATIONS)
    steps: int = Field(default=20, ge=1, le=MAX_STEPS)
    temperature_kelvin: float = 300.0
    integrator: str = "langevin"


@router.post("", status_code=202, response_model=JobResponse)
def start_simulation(body: SimulationRequest, request: Request) -> JobResponse:
    require_openmm()
    if body.mode not in {"minimization", "dynamics"}:
        raise InvalidInput("Mode must be minimization or dynamics.")
    if body.integrator not in {"langevin", "verlet"}:
        raise InvalidInput("Integrator must be langevin or verlet.")
    job = get_runner(request).submit("simulation", body.model_dump(), structure_id=body.structure_id)
    return to_job_response(job)
