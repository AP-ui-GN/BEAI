"""Structure upload and fetch. Parsing lives in the structure service."""

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.db.models import Structure
from backend.app.db.session import get_session
from backend.app.schemas.structure import StructureListResponse, StructureResponse
from backend.app.services.structure.ingest import (
    get_structure,
    ingest_structure,
    list_structures,
    structure_file,
)

router = APIRouter(prefix="/api/structures", tags=["structures"])


def _to_response(row: Structure) -> StructureResponse:
    created = row.created_at
    if created.tzinfo is None:
        from datetime import UTC

        created = created.replace(tzinfo=UTC)
    else:
        from datetime import UTC

        created = created.astimezone(UTC)
    created_text = created.isoformat(timespec="microseconds").replace("+00:00", "Z")
    return StructureResponse(
        id=row.id,
        display_filename=row.display_filename,
        format=row.format,
        size_bytes=row.size_bytes,
        sha256=row.sha256,
        created_at=created_text,
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


@router.get("/{structure_id}", response_model=StructureResponse)
def get_structure_by_id(
    structure_id: str,
    session: Session = Depends(get_session),
) -> StructureResponse:
    return _to_response(get_structure(session, structure_id))


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
