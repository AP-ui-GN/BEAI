"""Job status endpoints. Handlers live in services, not in this module."""

from fastapi import APIRouter, Request

from backend.app.core.errors import InvalidInput
from backend.app.core.timeutil import utc_iso
from backend.app.db.models import Job
from backend.app.jobs.runner import JobRunner
from backend.app.schemas.job import JobErrorBody, JobListResponse, JobResponse

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def get_runner(request: Request) -> JobRunner:
    runner = getattr(request.app.state, "jobs", None)
    if runner is None:
        raise InvalidInput("The job runner is not running.")
    return runner


def to_job_response(row: Job) -> JobResponse:
    error = JobErrorBody.model_validate(row.error_json) if row.error_json else None
    return JobResponse(
        id=row.id,
        kind=row.kind,
        status=row.status,
        progress=row.progress,
        cancel_requested=bool(row.cancel_requested),
        created_at=utc_iso(row.created_at),
        started_at=utc_iso(row.started_at) if row.started_at else None,
        completed_at=utc_iso(row.completed_at) if row.completed_at else None,
        error=error,
        analysis_id=row.analysis_id,
        structure_id=row.structure_id,
    )


@router.get("", response_model=JobListResponse)
def list_jobs(request: Request) -> JobListResponse:
    runner = get_runner(request)
    return JobListResponse(jobs=[to_job_response(row) for row in runner.list_jobs()])


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str, request: Request) -> JobResponse:
    return to_job_response(get_runner(request).get(job_id))


@router.post("/{job_id}/cancel", response_model=JobResponse)
def cancel_job(job_id: str, request: Request) -> JobResponse:
    return to_job_response(get_runner(request).cancel(job_id))
