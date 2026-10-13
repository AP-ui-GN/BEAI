"""Open Targets Platform target safety and disease associations.

Checked 2026-10-13:
https://platform-docs.opentargets.org/data-access/graphql-api
POST ``https://api.platform.opentargets.org/api/v4/graphql`` with a JSON
``query`` and ``variables``. The docs say the API is for one entity at a time.
``safetyLiabilities`` and ``associatedDiseases`` were present on a VKORC1 query
the same day. No numeric rate limit is stated on that page.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from backend.app.core.errors import ExternalServiceError, InvalidInput
from backend.app.data_access.http import ExternalHttp

ENDPOINT = "https://api.platform.opentargets.org/api/v4/graphql"
_ENSEMBL = re.compile(r"^ENSG\d{1,20}$")
_QUERY = """
query targetSafety($ensemblId: String!) {
  target(ensemblId: $ensemblId) {
    id
    approvedSymbol
    safetyLiabilities {
      event
      eventId
      datasource
      literature
    }
    associatedDiseases(page: {index: 0, size: 5}) {
      count
      rows {
        disease { id name }
        score
      }
    }
  }
}
"""


def fetch_target(http: ExternalHttp, ensembl_id: str) -> dict[str, Any]:
    if not _ENSEMBL.fullmatch(ensembl_id):
        raise InvalidInput("Open Targets lookup needs an Ensembl gene id such as ENSG00000167397.")
    payload = http.post_json(ENDPOINT, {"query": _QUERY, "variables": {"ensemblId": ensembl_id}})
    if payload.get("errors"):
        message = "Open Targets returned an error."
        errors = payload.get("errors")
        if isinstance(errors, list) and errors and isinstance(errors[0], dict):
            detail = errors[0].get("message")
            if isinstance(detail, str) and detail:
                message = f"Open Targets returned an error: {detail[:240]}"
        raise ExternalServiceError(message)
    target = (payload.get("data") or {}).get("target") if isinstance(payload.get("data"), dict) else None
    if not isinstance(target, dict):
        raise ExternalServiceError("Open Targets returned no target for this id.")
    return {
        "source": "Open Targets Platform",
        "url": ENDPOINT,
        "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "ensembl_id": ensembl_id,
        "target": target,
    }
