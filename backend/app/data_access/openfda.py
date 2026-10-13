"""openFDA drug label and FAERS count queries.

Label search checked 2026-10-13:
https://api.fda.gov/drug/label.json?search=openfda.generic_name:aspirin&limit=1
FAERS counts:
https://api.fda.gov/drug/event.json?search=patient.drug.medicinalproduct:ASPIRIN&count=...
The response meta includes a disclaimer. Counts are observational.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from backend.app.core.errors import ExternalServiceError
from backend.app.data_access.dailymed import fetch_dailymed_label
from backend.app.data_access.http import ExternalHttp


def fetch_label(http: ExternalHttp, generic_name: str) -> dict[str, Any]:
    """Use openFDA, then DailyMed when openFDA fails. A second failure stores nothing."""

    try:
        return _fetch_openfda_label(http, generic_name)
    except ExternalServiceError as openfda_error:
        try:
            fetched = fetch_dailymed_label(http, generic_name)
        except ExternalServiceError as dailymed_error:
            raise ExternalServiceError(
                "openFDA and DailyMed both failed. "
                f"openFDA: {openfda_error.message} DailyMed: {dailymed_error.message}"
            ) from dailymed_error
        fetched["openfda_error"] = openfda_error.message
        return fetched


def _fetch_openfda_label(http: ExternalHttp, generic_name: str) -> dict[str, Any]:
    url = (
        "https://api.fda.gov/drug/label.json?search=openfda.generic_name:"
        f"{quote(generic_name)}&limit=1"
    )
    payload = http.get_json(url)
    results = payload.get("results")
    if not isinstance(results, list) or not results:
        raise ExternalServiceError("openFDA returned no label for this query.")
    record = results[0]
    if not isinstance(record, dict):
        raise ExternalServiceError("openFDA label result was not an object.")
    return {
        "source": "openFDA drug label",
        "url": url,
        "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "license": (payload.get("meta") or {}).get("license"),
        "record": record,
    }


def fetch_faers_counts(http: ExternalHttp, product: str) -> dict[str, Any]:
    url = (
        "https://api.fda.gov/drug/event.json?search=patient.drug.medicinalproduct:"
        f"{quote(product)}&count=patient.reaction.reactionmeddrapt.exact&limit=5"
    )
    payload = http.get_json(url)
    results = payload.get("results")
    if not isinstance(results, list):
        raise ExternalServiceError("openFDA did not return FAERS counts.")
    return {
        "source": "openFDA FAERS",
        "url": url,
        "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "license": (payload.get("meta") or {}).get("license"),
        "counts": results,
    }
