"""UniProtKB import.

GET https://rest.uniprot.org/uniprotkb/{accession}.json
The licence text was read on 2026-10-13 from
https://ftp.uniprot.org/pub/databases/uniprot/LICENSE (CC BY 4.0).
An inactive entry is not stored. The error names the successor accessions
the API itself returned.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from backend.app.core.errors import ExternalServiceError, InvalidInput
from backend.app.data_access.http import ExternalHttp

_ACCESSION = re.compile(r"^[A-NR-Z][0-9][A-Z0-9]{3}[0-9](?:[A-Z0-9]{3}[0-9])?$|^[OPQ][0-9][A-Z0-9]{3}[0-9]$")
_LICENSE = "CC BY 4.0"
_LICENSE_URL = "https://ftp.uniprot.org/pub/databases/uniprot/LICENSE"


def fetch_sequence(http: ExternalHttp, accession: str) -> dict[str, Any]:
    """Return a sequence payload. Inactive entries raise and are not a sequence."""

    identifier = accession.strip().upper()
    if not _ACCESSION.fullmatch(identifier):
        raise InvalidInput("That is not a UniProt accession.")
    url = f"https://rest.uniprot.org/uniprotkb/{identifier}.json"
    record = http.get_json(url)
    entry_type = str(record.get("entryType") or "")
    if "inactive" in entry_type.lower():
        reason = record.get("inactiveReason") if isinstance(record.get("inactiveReason"), dict) else {}
        successors = reason.get("mergeDemergeTo") if isinstance(reason, dict) else None
        listed = ", ".join(str(item) for item in successors) if isinstance(successors, list) and successors else "none"
        kind = reason.get("inactiveReasonType") if isinstance(reason, dict) else "inactive"
        raise InvalidInput(
            f"UniProt entry {identifier} is inactive ({kind}). Successor accessions reported by UniProt: {listed}."
        )
    sequence = record.get("sequence")
    value = sequence.get("value") if isinstance(sequence, dict) else None
    if not isinstance(value, str) or not value:
        raise ExternalServiceError("UniProt did not return a sequence for this accession.")
    description = record.get("proteinDescription")
    full_name = None
    if isinstance(description, dict):
        recommended = description.get("recommendedName")
        if isinstance(recommended, dict):
            name = recommended.get("fullName")
            if isinstance(name, dict) and isinstance(name.get("value"), str):
                full_name = name["value"]
    organism = record.get("organism") if isinstance(record.get("organism"), dict) else {}
    return {
        "header": full_name or str(record.get("uniProtkbId") or identifier),
        "sequence": value,
        "source": {
            "source": "UniProtKB",
            "identifier": str(record.get("primaryAccession") or identifier),
            "url": url,
            "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "license": _LICENSE,
            "license_url": _LICENSE_URL,
            "entry_type": entry_type,
            "organism": organism.get("scientificName") if isinstance(organism, dict) else None,
        },
    }
