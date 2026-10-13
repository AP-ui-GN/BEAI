"""Job HTTP models."""

from pydantic import BaseModel, ConfigDict


class JobErrorBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str


class JobResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: str
    status: str
    progress: float | None
    cancel_requested: bool
    created_at: str
    started_at: str | None
    completed_at: str | None
    error: JobErrorBody | None
    analysis_id: str | None
    structure_id: str | None


class JobListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    jobs: list[JobResponse]
