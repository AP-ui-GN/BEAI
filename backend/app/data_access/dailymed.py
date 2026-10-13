"""DailyMed SPL lookup, used when openFDA does not return a label.

Checked 2026-10-13:
https://dailymed.nlm.nih.gov/dailymed/webservices-help/v2/spls_api.cfm
https://dailymed.nlm.nih.gov/dailymed/webservices-help/v2/spls_setid_api.cfm
Search is GET ``/services/v2/spls.json`` with ``drug_name`` and ``pagesize``
(maximum 100). The SPL document is GET ``/services/v2/spls/{SETID}.xml``.
Those pages do not publish a numeric rate limit. The shared client spaces
requests to the same host.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from backend.app.core.errors import ExternalServiceError
from backend.app.data_access.http import ExternalHttp

_NS = "{urn:hl7-org:v3}"
_SETID = re.compile(r"^[0-9a-fA-F-]{8,80}$")

# LOINC section codes from the SPL. Display names were read from a warfarin
# SPL retrieved on 2026-10-13 (for example 34066-1 is "Boxed Warning section").
SECTION_CODES = {
    "34066-1": "boxed_warning",
    "34070-3": "contraindications",
    "43685-7": "warnings_and_cautions",
    "34071-1": "warnings",
    "34084-4": "adverse_reactions",
    "34073-7": "drug_interactions",
    "34088-5": "overdosage",
    "43679-0": "mechanism_of_action",
    "43682-4": "pharmacokinetics",
}


def fetch_dailymed_label(http: ExternalHttp, drug_name: str) -> dict[str, Any]:
    search_url = (
        "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json"
        f"?drug_name={quote(drug_name)}&pagesize=1"
    )
    payload = http.get_json(search_url)
    data = payload.get("data")
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        raise ExternalServiceError("DailyMed returned no SPL for this query.")
    first = data[0]
    set_id = str(first.get("setid") or "")
    if not _SETID.fullmatch(set_id):
        raise ExternalServiceError("DailyMed returned an SPL set id that was not usable.")
    document_url = f"https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/{set_id}.xml"
    sections = spl_sections(http.get_bytes(document_url))
    if not sections:
        raise ExternalServiceError("DailyMed SPL did not contain a recognised label section.")
    record: dict[str, Any] = {
        "set_id": set_id,
        "version": first.get("spl_version"),
        "effective_time": first.get("published_date"),
        "title": first.get("title"),
    }
    record.update(sections)
    return {
        "source": "DailyMed",
        "url": document_url,
        "search_url": search_url,
        "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "license": None,
        "record": record,
    }


def spl_sections(xml_bytes: bytes) -> dict[str, list[str]]:
    """Copy recognised SPL section text. Indentation between text nodes is dropped."""

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ExternalServiceError("DailyMed returned an SPL that was not XML.") from exc
    found: dict[str, list[str]] = {}
    _walk(root, inside_mapped=False, found=found)
    return found


def _walk(element: ET.Element, *, inside_mapped: bool, found: dict[str, list[str]]) -> None:
    for child in list(element):
        if child.tag != f"{_NS}section":
            _walk(child, inside_mapped=inside_mapped, found=found)
            continue
        code_element = child.find(f"{_NS}code")
        code = code_element.get("code") if code_element is not None else None
        name = SECTION_CODES.get(code or "")
        mapped = name is not None
        if mapped and not inside_mapped:
            text = _section_text(child)
            if text:
                found.setdefault(name, []).append(text)
        _walk(child, inside_mapped=inside_mapped or mapped, found=found)


def _section_text(section: ET.Element) -> str:
    parts: list[str] = []
    for node in section.iter():
        if node.text and node.text.strip():
            parts.append(node.text.strip())
        if node.tail and node.tail.strip():
            parts.append(node.tail.strip())
    return "\n".join(parts)
