"""HTML, Markdown, and JSON reports from a stored AnalysisResult."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_TEMPLATES = Path(__file__).resolve().parent / "templates"


def format_value(value: object) -> str:
    """Stable text for a measurement value. Null stays the word null."""

    if value is None:
        return "null"
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return format(value, ".12g")
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def render_report(result: dict[str, Any], report_format: str) -> tuple[bytes, str, str]:
    """Return body bytes, media type, and a file suffix. ``result`` is not recomputed."""

    if report_format == "json":
        body = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        return body, "application/json", "json"
    if report_format == "html":
        text = _environment(autoescape=True).get_template("report.html.j2").render(**result)
        return text.encode("utf-8"), "text/html; charset=utf-8", "html"
    if report_format == "md":
        text = _environment(autoescape=False).get_template("report.md.j2").render(**result)
        return text.encode("utf-8"), "text/markdown; charset=utf-8", "md"
    raise ValueError(f"unsupported report format {report_format}")


def _environment(autoescape: bool) -> Environment:
    environment = Environment(
        loader=FileSystemLoader(_TEMPLATES),
        autoescape=autoescape,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    environment.filters["format_value"] = format_value
    return environment
