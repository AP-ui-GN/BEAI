"""Store an uploaded structure and read it back. No client filename is used as a path."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.core.errors import InvalidInput, NotFound
from backend.app.db.models import Structure
from backend.app.services.structure.files import (
    assert_text_structure,
    coordinate_record_count,
    format_for_filename,
    read_limited,
    safe_stored_file,
    sanitize_display_filename,
    sha256_hex,
)
from backend.app.services.structure.parse import parse_structure_file

logger = logging.getLogger(__name__)


async def ingest_structure(upload: UploadFile, settings: Settings, session: Session) -> Structure:
    display = sanitize_display_filename(upload.filename)
    structure_format = format_for_filename(display)
    payload = await read_limited(upload, settings.max_upload_bytes)
    assert_text_structure(payload, structure_format)
    records = coordinate_record_count(payload)
    if records > settings.max_atom_count:
        raise InvalidInput(
            f"The structure has {records} coordinate records, above the limit of {settings.max_atom_count}."
        )
    structure_id = str(uuid.uuid4())
    suffix = "pdb" if structure_format == "pdb" else "cif"
    stored_name = f"{structure_id}.{suffix}"
    destination = safe_stored_file(settings.resolved_storage_dir(), stored_name)
    destination.write_bytes(payload)
    try:
        summary = parse_structure_file(destination, structure_format, records)
        if summary.coordinate_record_count > settings.max_atom_count:
            raise InvalidInput(
                "The structure has "
                f"{summary.coordinate_record_count} coordinate records, above the limit of "
                f"{settings.max_atom_count}."
            )
        row = Structure(
            id=structure_id,
            display_filename=display,
            stored_path=stored_name,
            sha256=sha256_hex(payload),
            format=structure_format,
            size_bytes=len(payload),
            created_at=datetime.now(UTC),
            metadata_json={
                "title": summary.title,
                "model_count": summary.model_count,
                "chain_ids": summary.chain_ids,
                "coordinate_record_count": summary.coordinate_record_count,
            },
        )
        session.add(row)
        session.commit()
        session.refresh(row)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    logger.info("stored structure %s format=%s bytes=%s", row.id, row.format, row.size_bytes)
    return row


def store_structure_bytes(
    payload: bytes,
    display_filename: str,
    settings: Settings,
    session: Session,
    provenance: dict | None = None,
) -> Structure:
    """Store bytes that were already fetched. The caller must not pass a client filename as a path."""

    display = sanitize_display_filename(display_filename)
    structure_format = format_for_filename(display)
    if len(payload) > settings.max_upload_bytes:
        raise InvalidInput("The structure exceeds the upload limit.")
    assert_text_structure(payload, structure_format)
    records = coordinate_record_count(payload)
    if records > settings.max_atom_count:
        raise InvalidInput(
            f"The structure has {records} coordinate records, above the limit of {settings.max_atom_count}."
        )
    structure_id = str(uuid.uuid4())
    suffix = "pdb" if structure_format == "pdb" else "cif"
    stored_name = f"{structure_id}.{suffix}"
    destination = safe_stored_file(settings.resolved_storage_dir(), stored_name)
    destination.write_bytes(payload)
    try:
        summary = parse_structure_file(destination, structure_format, records)
        metadata = {
            "title": summary.title,
            "model_count": summary.model_count,
            "chain_ids": summary.chain_ids,
            "coordinate_record_count": summary.coordinate_record_count,
        }
        if provenance is not None:
            metadata["provenance"] = provenance
        row = Structure(
            id=structure_id,
            display_filename=display,
            stored_path=stored_name,
            sha256=sha256_hex(payload),
            format=structure_format,
            size_bytes=len(payload),
            created_at=datetime.now(UTC),
            metadata_json=metadata,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return row


def list_structures(session: Session) -> list[Structure]:
    statement = select(Structure).order_by(Structure.created_at.desc(), Structure.id.desc())
    return list(session.scalars(statement))


def get_structure(session: Session, structure_id: str) -> Structure:
    row = session.get(Structure, structure_id)
    if row is None:
        raise NotFound("Structure not found.")
    return row


def structure_file(settings: Settings, row: Structure) -> Path:
    path = safe_stored_file(settings.resolved_storage_dir(), row.stored_path)
    if not path.is_file():
        raise NotFound("Structure file is missing.")
    return path
