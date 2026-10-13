"""Europe PMC article search.

Checked 2026-10-13: https://europepmc.org/RestfulWebService
GET ``/europepmc/webservices/rest/search`` with ``query``, ``format=json``,
``resultType=core``, and ``pageSize`` (maximum 1000 on that page). The page
does not state a numeric rate limit. The shared client spaces requests.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from backend.app.core.errors import ExternalServiceError
from backend.app.data_access.http import ExternalHttp


def search_articles(http: ExternalHttp, query: str, page_size: int = 3) -> dict[str, Any]:
    size = min(max(int(page_size), 1), 25)
    url = (
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        f"?query={quote(query)}&resultType=core&pageSize={size}&format=json&cursorMark=*"
    )
    payload = http.get_json(url)
    result_list = payload.get("resultList")
    if not isinstance(result_list, dict) or "result" not in result_list:
        raise ExternalServiceError("Europe PMC did not return a result list.")
    rows = result_list.get("result")
    if rows is None:
        rows = []
    elif isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list):
        raise ExternalServiceError("Europe PMC result list was not a list.")
    results = [row for row in rows if isinstance(row, dict)]
    return {
        "source": "Europe PMC",
        "url": url,
        "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "hit_count": payload.get("hitCount"),
        "results": results,
    }
