"""PubChem PUG REST property lookup.

Endpoint checked 2026-10-13:
https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/aspirin/property/.../JSON
returned HTTP 200. PubChem asks for no more than about 5 requests per second.
The shared client spaces hosts at 0.25 s. A name lookup for aspirin returned
ConnectivitySMILES and did not return CanonicalSMILES; missing fields stay null.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from backend.app.core.errors import ExternalServiceError, InvalidInput
from backend.app.data_access.http import ExternalHttp

_PROPERTY = "MolecularFormula,MolecularWeight,Title,IUPACName,CanonicalSMILES,ConnectivitySMILES"


def lookup(http: ExternalHttp, query: str, query_type: str) -> dict[str, Any]:
    text = query.strip()
    if not text:
        raise InvalidInput("The PubChem query is empty.")
    if query_type not in {"name", "cid", "smiles", "inchikey"}:
        raise InvalidInput("PubChem query type must be name, cid, smiles, or inchikey.")
    kind = {"name": "name", "cid": "cid", "smiles": "smiles", "inchikey": "inchikey"}[query_type]
    url = (
        "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/"
        f"{kind}/{quote(text, safe='')}/property/{_PROPERTY}/JSON"
    )
    payload = http.get_json(url)
    table = payload.get("PropertyTable")
    properties = table.get("Properties") if isinstance(table, dict) else None
    if not isinstance(properties, list) or not properties or not isinstance(properties[0], dict):
        raise ExternalServiceError("PubChem did not return a property record.")
    row = properties[0]
    return {
        "source": "PubChem",
        "identifier": str(row.get("CID") or ""),
        "url": url,
        "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "license": "PubChem data usage policy",
        "title": row.get("Title"),
        "iupac_name": row.get("IUPACName"),
        "molecular_formula": row.get("MolecularFormula"),
        "molecular_weight": row.get("MolecularWeight"),
        "canonical_smiles": row.get("CanonicalSMILES"),
        "connectivity_smiles": row.get("ConnectivitySMILES"),
    }
