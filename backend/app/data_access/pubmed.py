"""PubMed E-utilities esearch plus esummary.

A live aspirin search on 2026-10-13 returned id 42864513. The summary fixture
is that record. Results stay unclassified. NCBI asks for at most 3 requests
per second without an API key; the shared client spaces hosts at 0.25 s.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from backend.app.core.errors import ExternalServiceError
from backend.app.data_access.http import ExternalHttp


def search_summaries(http: ExternalHttp, term: str, retmax: int = 3) -> dict[str, Any]:
    search_url = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        f"?db=pubmed&term={quote(term)}&retmode=json&retmax={int(retmax)}"
    )
    search = http.get_json(search_url)
    id_list = ((search.get("esearchresult") or {}).get("idlist")) or []
    if not isinstance(id_list, list):
        raise ExternalServiceError("PubMed esearch did not return an id list.")
    summaries: list[dict[str, Any]] = []
    if id_list:
        joined = ",".join(str(item) for item in id_list[:retmax])
        summary_url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
            f"?db=pubmed&id={joined}&retmode=json"
        )
        summary = http.get_json(summary_url)
        result = summary.get("result") if isinstance(summary.get("result"), dict) else {}
        for pmid in id_list[:retmax]:
            row = result.get(str(pmid))
            if isinstance(row, dict):
                summaries.append(row)
    return {
        "source": "PubMed",
        "url": search_url,
        "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "ids": [str(item) for item in id_list[:retmax]],
        "summaries": summaries,
    }
