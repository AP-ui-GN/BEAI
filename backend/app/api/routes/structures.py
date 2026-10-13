"""Structure upload and fetch. Parsing lives in the structure service."""

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.app.api.routes.jobs import get_runner, to_job_response
from backend.app.core.config import Settings
from backend.app.core.errors import InvalidInput
from backend.app.core.timeutil import utc_iso
from backend.app.db.models import Structure
from backend.app.db.session import get_session
from backend.app.schemas.job import JobResponse
from backend.app.schemas.structure import (
    ResidueListResponse,
    ResidueRow,
    StructureCompareRequest,
    StructureListResponse,
    StructureResponse,
)
from backend.app.services.structure.deep import residue_table
from backend.app.services.structure.ingest import (
    get_structure,
    ingest_structure,
    list_structures,
    structure_file,
)

router = APIRouter(prefix="/api/structures", tags=["structures"])


def _to_response(row: Structure) -> StructureResponse:
    return StructureResponse(
        id=row.id,
        display_filename=row.display_filename,
        format=row.format,
        size_bytes=row.size_bytes,
        sha256=row.sha256,
        created_at=utc_iso(row.created_at),
        metadata=row.metadata_json,
    )


@router.post("", status_code=201, response_model=StructureResponse)
async def create_structure(
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> StructureResponse:
    settings: Settings = request.app.state.settings
    row = await ingest_structure(file, settings, session)
    return _to_response(row)


@router.get("", response_model=StructureListResponse)
def get_structures(session: Session = Depends(get_session)) -> StructureListResponse:
    return StructureListResponse(structures=[_to_response(row) for row in list_structures(session)])


@router.post("/compare", status_code=202, response_model=JobResponse)
def compare_structures(
    body: StructureCompareRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> JobResponse:
    reference = get_structure(session, body.structure_id)
    mobile = get_structure(session, body.other_structure_id)
    _require_chain(reference, body.chain_id)
    _require_chain(mobile, body.other_chain_id)
    job = get_runner(request).submit(
        "structure_comparison",
        {
            "structure_id": body.structure_id,
            "chain_id": body.chain_id,
            "other_structure_id": body.other_structure_id,
            "other_chain_id": body.other_chain_id,
        },
        structure_id=body.structure_id,
    )
    return to_job_response(job)


def _require_chain(row: Structure, chain_id: str) -> None:
    chains = list((row.metadata_json or {}).get("chain_ids") or [])
    if chain_id not in chains:
        raise InvalidInput(f"Chain {chain_id} is not in this structure.")


@router.get("/{structure_id}", response_model=StructureResponse)
def get_structure_by_id(
    structure_id: str,
    session: Session = Depends(get_session),
) -> StructureResponse:
    return _to_response(get_structure(session, structure_id))


@router.post("/{structure_id}/pockets", status_code=202, response_model=JobResponse)
def detect_structure_pockets(
    structure_id: str,
    request: Request,
    session: Session = Depends(get_session),
) -> JobResponse:
    get_structure(session, structure_id)
    job = get_runner(request).submit(
        "pocket_detection",
        {"structure_id": structure_id},
        structure_id=structure_id,
    )
    return to_job_response(job)


@router.get("/{structure_id}/residues", response_model=ResidueListResponse)
def list_residues(
    structure_id: str,
    request: Request,
    chain: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> ResidueListResponse:
    settings: Settings = request.app.state.settings
    row = get_structure(session, structure_id)
    path = structure_file(settings, row)
    rows = residue_table(path, row.format, chain)
    return ResidueListResponse(
        chain_id=chain,
        residues=[ResidueRow.model_validate(item) for item in rows],
    )


@router.get("/{structure_id}/file")
def download_structure_file(
    structure_id: str,
    request: Request,
    session: Session = Depends(get_session),
) -> FileResponse:
    settings: Settings = request.app.state.settings
    row = get_structure(session, structure_id)
    path = structure_file(settings, row)
    media = "chemical/x-pdb" if row.format == "pdb" else "chemical/x-mmcif"
    return FileResponse(
        path,
        media_type=media,
        filename=row.display_filename,
        content_disposition_type="inline",
    )
