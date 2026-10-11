"""Upload checks. Client filenames are display text only and never become paths."""

from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import UploadFile

from backend.app.core.errors import InvalidInput, PayloadTooLarge

_FORMAT_BY_SUFFIX = {
    ".pdb": "pdb",
    ".ent": "pdb",
    ".cif": "mmcif",
    ".mmcif": "mmcif",
}


def sanitize_display_filename(filename: str | None) -> str:
    """Keep the last path segment for display. Drop separators and NULs."""

    raw = (filename or "").replace("\\", "/").split("/")[-1]
    raw = raw.replace("\x00", "").replace("\r", "").replace("\n", "").strip()
    if raw in {"", ".", ".."}:
        return "upload"
    return raw[:255]


def format_for_filename(display_filename: str) -> str:
    suffix = Path(display_filename).suffix.lower()
    try:
        return _FORMAT_BY_SUFFIX[suffix]
    except KeyError as exc:
        raise InvalidInput(
            "Extension is not allowed. Upload a .pdb, .ent, .cif, or .mmcif file."
        ) from exc


async def read_limited(upload: UploadFile, max_bytes: int) -> bytes:
    """Read the upload in chunks and stop once it exceeds ``max_bytes``."""

    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise PayloadTooLarge(f"Upload exceeds the {max_bytes} byte limit.")
        chunks.append(chunk)
    return b"".join(chunks)


def sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def assert_text_structure(payload: bytes, structure_format: str) -> None:
    """Reject empty, binary, and format-mismatched bytes before they are stored."""

    if not payload:
        raise InvalidInput("The file is empty.")
    if payload.startswith(b"\x1f\x8b"):
        raise InvalidInput(
            "Gzip-compressed files are not accepted. Upload uncompressed PDB or mmCIF."
        )
    if b"\x00" in payload[:8192]:
        raise InvalidInput("The file looks like binary data, not a PDB or mmCIF text file.")
    text_lines = payload.splitlines()
    if structure_format == "pdb":
        has_coordinates = any(line.startswith((b"ATOM", b"HETATM")) for line in text_lines)
        if not has_coordinates:
            raise InvalidInput("PDB content needs at least one ATOM or HETATM record.")
        return
    has_data_block = any(line.startswith(b"data_") for line in text_lines)
    if not has_data_block:
        raise InvalidInput("mmCIF content needs a data_ block.")


def coordinate_record_count(payload: bytes) -> int:
    """Count ATOM and HETATM lines. mmCIF coordinate rows use the same record names."""

    return sum(1 for line in payload.splitlines() if line.startswith((b"ATOM", b"HETATM")))


def safe_stored_file(storage_dir: Path, stored_path: str) -> Path:
    """Resolve a stored filename and refuse anything that leaves the storage directory."""

    if not stored_path or stored_path != Path(stored_path).name or stored_path.startswith("."):
        raise InvalidInput("The stored structure path is not valid.")
    root = storage_dir.resolve()
    path = (root / stored_path).resolve()
    if path.parent != root:
        raise InvalidInput("The stored structure path is not valid.")
    return path
