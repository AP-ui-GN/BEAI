"""ChEMBL molecule and activity lookup.

Checked 2026-10-13:
https://www.ebi.ac.uk/chembl/api/data/molecule/CHEMBL25.json
https://www.ebi.ac.uk/chembl/api/data/activity.json?molecule_chembl_id=CHEMBL25&limit=2
Activities keep assay, target, organism, type, relation, value, units, pChEMBL, and document id.
They are not averaged across standard type or units.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from backend.app.core.errors import ExternalServiceError, InvalidInput
from backend.app.data_access.http import ExternalHttp


def fetch_molecule(http: ExternalHttp, chembl_id: str) -> dict[str, Any]:
    identifier = chembl_id.strip().upper()
    if not identifier.startswith("CHEMBL") or not identifier[6:].isdigit():
        raise InvalidInput("ChEMBL molecule IDs look like CHEMBL25.")
    url = f"https://www.ebi.ac.uk/chembl/api/data/molecule/{quote(identifier)}.json"
    record = http.get_json(url)
    structures = record.get("molecule_structures") if isinstance(record.get("molecule_structures"), dict) else {}
    smiles = structures.get("canonical_smiles") if isinstance(structures, dict) else None
    if not isinstance(smiles, str) or not smiles:
        raise ExternalServiceError("ChEMBL did not return a canonical SMILES for this molecule.")
    activity_url = (
        "https://www.ebi.ac.uk/chembl/api/data/activity.json"
        f"?molecule_chembl_id={quote(identifier)}&limit=100"
    )
    activity_payload = http.get_json(activity_url)
    raw = activity_payload.get("activities")
    activities = [_activity(item) for item in raw] if isinstance(raw, list) else []
    return {
        "source": "ChEMBL",
        "identifier": str(record.get("molecule_chembl_id") or identifier),
        "url": url,
        "activity_url": activity_url,
        "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "license": None,
        "license_note": "The molecule JSON retrieved on 2026-10-13 did not include a licence field.",
        "pref_name": record.get("pref_name"),
        "canonical_smiles": smiles,
        "activities": [item for item in activities if item is not None],
    }


def _activity(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    return {
        "assay_chembl_id": item.get("assay_chembl_id"),
        "target_chembl_id": item.get("target_chembl_id"),
        "target_organism": item.get("target_organism"),
        "assay_type": item.get("assay_type"),
        "standard_type": item.get("standard_type"),
        "standard_relation": item.get("standard_relation"),
        "standard_value": item.get("standard_value"),
        "standard_units": item.get("standard_units"),
        "pchembl_value": item.get("pchembl_value"),
        "document_chembl_id": item.get("document_chembl_id"),
    }
