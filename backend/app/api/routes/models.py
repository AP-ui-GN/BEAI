"""Model registry routes. Handlers do not load weights except through POST .../load."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.routes.analyses import _detail
from backend.app.api.routes.jobs import get_runner, to_job_response
from backend.app.core.errors import CapabilityUnavailable, InvalidInput
from backend.app.db.models import Analysis, Job
from backend.app.db.session import get_session
from backend.app.schemas.analysis import AnalysisDetail
from backend.app.schemas.job import JobResponse
from backend.app.schemas.model_registry import (
    DownloadResponse,
    HardwareReport,
    ModelCreate,
    ModelListResponse,
    ModelResponse,
    PredictRequest,
)
from backend.app.services.embeddings.download import ensure_checkpoint
from backend.app.services.models_registry.hardware import read_hardware
from backend.app.services.models_registry.registry import (
    get_model_row,
    list_model_views,
    model_view,
    register_model,
)
from backend.app.services.models_registry.runtime import ModelRuntime
from backend.app.services.properties.constants import SPLIT_SEED
from backend.app.services.properties.predict import prediction_result

router = APIRouter(prefix="/api/models", tags=["models"])


def _runtime(request: Request) -> ModelRuntime:
    runtime = getattr(request.app.state, "model_runtime", None)
    if runtime is None:
        raise InvalidInput("The model runtime is not available.")
    return runtime


@router.get("/hardware", response_model=HardwareReport)
def get_hardware() -> HardwareReport:
    return HardwareReport.model_validate(read_hardware())


@router.get("", response_model=ModelListResponse)
def list_models(request: Request, session: Session = Depends(get_session)) -> ModelListResponse:
    return ModelListResponse.model_validate(list_model_views(session, _runtime(request)))


@router.post("", status_code=201, response_model=ModelResponse)
def create_model(
    body: ModelCreate,
    request: Request,
    session: Session = Depends(get_session),
) -> ModelResponse:
    row = register_model(session, body.model_dump())
    hardware = read_hardware()
    jobs = list(session.scalars(select(Job).where(Job.kind == "model_training")))
    return ModelResponse.model_validate(model_view(row, _runtime(request), hardware, jobs))


@router.get("/{model_id}", response_model=ModelResponse)
def get_model(model_id: str, request: Request, session: Session = Depends(get_session)) -> ModelResponse:
    row = get_model_row(session, model_id)
    hardware = read_hardware()
    jobs = list(session.scalars(select(Job).where(Job.kind == "model_training")))
    return ModelResponse.model_validate(model_view(row, _runtime(request), hardware, jobs))


@router.post("/{model_id}/train", status_code=202, response_model=JobResponse)
def train_model(model_id: str, request: Request, session: Session = Depends(get_session)) -> JobResponse:
    row = get_model_row(session, model_id)
    if row.loader_key != "solubility":
        raise InvalidInput("Only the solubility model can be trained from this endpoint.")
    job = get_runner(request).submit(
        "solubility_training",
        {"model_id": row.id, "seed": SPLIT_SEED, "require_checksum": True},
    )
    return to_job_response(job)


@router.post("/{model_id}/predict", status_code=201, response_model=AnalysisDetail)
def predict_model(
    model_id: str,
    body: PredictRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> AnalysisDetail:
    from datetime import UTC, datetime

    row = get_model_row(session, model_id)
    if row.loader_key != "solubility":
        raise InvalidInput("This model does not predict solubility.")
    artifact = _runtime(request).load(row)
    predicted = artifact["predict"](body.smiles)
    result = prediction_result(row, body.smiles, predicted)
    now = datetime.now(UTC)
    analysis = Analysis(
        id=result["analysis_id"],
        kind="solubility_prediction",
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


@router.post("/{model_id}/download", response_model=DownloadResponse)
def download_model(model_id: str, session: Session = Depends(get_session)) -> DownloadResponse:
    row = get_model_row(session, model_id)
    if row.loader_key != "esm2_8m":
        raise InvalidInput("Only the registered ESM-2 8M checkpoint can be downloaded.")
    return DownloadResponse.model_validate(ensure_checkpoint())


@router.post("/{model_id}/load", response_model=ModelResponse)
def load_model(model_id: str, request: Request, session: Session = Depends(get_session)) -> ModelResponse:
    runtime = _runtime(request)
    row = get_model_row(session, model_id)
    hardware = read_hardware()
    jobs = list(session.scalars(select(Job).where(Job.kind == "model_training")))
    view = model_view(row, runtime, hardware, jobs)
    if view["status"] == "disabled":
        raise CapabilityUnavailable(view["status_reason"] or "A dependency for this model is missing.")
    if view["status"] == "incompatible":
        raise InvalidInput(view["status_reason"] or "This model is not compatible with this machine.")
    runtime.load(row)
    refreshed = model_view(row, runtime, hardware, jobs)
    return ModelResponse.model_validate(refreshed)


@router.post("/{model_id}/unload", response_model=ModelResponse)
def unload_model(model_id: str, request: Request, session: Session = Depends(get_session)) -> ModelResponse:
    runtime = _runtime(request)
    row = get_model_row(session, model_id)
    runtime.unload(row.id)
    hardware = read_hardware()
    jobs = list(session.scalars(select(Job).where(Job.kind == "model_training")))
    return ModelResponse.model_validate(model_view(row, runtime, hardware, jobs))
