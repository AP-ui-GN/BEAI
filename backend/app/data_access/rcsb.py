"""RCSB entry import.

Metadata: https://data.rcsb.org/rest/v1/core/entry/{pdb_id}
Coordinates: https://files.rcsb.org/download/{pdb_id}.pdb
Both URLs returned HTTP 200 for 1UBQ on 2026-10-13. PDB archive data used by
this project are CC0.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from backend.app.core.errors import InvalidInput
from backend.app.data_access.http import ExternalHttp

_PDB_ID = re.compile(r"^[0-9][A-Za-z0-9]{3}$")


def fetch_entry(http: ExternalHttp, pdb_id: str) -> tuple[bytes, dict[str, Any]]:
    """Return PDB bytes and a provenance object. Raises before any local row exists."""

    identifier = pdb_id.strip().upper()
    if not _PDB_ID.fullmatch(identifier):
        raise InvalidInput("A PDB ID is four characters and starts with a digit.")
    metadata_url = f"https://data.rcsb.org/rest/v1/core/entry/{identifier}"
    file_url = f"https://files.rcsb.org/download/{identifier}.pdb"
    metadata = http.get_json(metadata_url)
    payload = http.get_bytes(file_url)
    title = None
    struct = metadata.get("struct")
    if isinstance(struct, dict) and isinstance(struct.get("title"), str):
        title = struct["title"]
    provenance = {
        "source": "RCSB PDB",
        "identifier": identifier,
        "metadata_url": metadata_url,
        "file_url": file_url,
        "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "license": "CC0",
        "title": title,
        "rcsb_id": metadata.get("rcsb_id"),
    }
    return payload, provenance
