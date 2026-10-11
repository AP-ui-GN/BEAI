"""Reports are rendered from the stored AnalysisResult. HTML escapes author text."""

import json

from fastapi.testclient import TestClient

from backend.app.services.reports.render import format_value
from backend.tests.fixtures import build_synthetic_peptide
from backend.tests.samples import minimal_pdb


def _analyze(client: TestClient, filename: str, payload: bytes) -> dict:
    uploaded = client.post(
        "/api/structures",
        files={"file": (filename, payload, "chemical/x-pdb")},
    )
    assert uploaded.status_code == 201, uploaded.text
    created = client.post(
        f"/api/structures/{uploaded.json()['id']}/analyses",
        json={"kind": "structure_overview"},
    )
    assert created.status_code == 201, created.text
    return created.json()


def test_json_report_equals_the_api_result_and_text_reports_repeat_it(client: TestClient) -> None:
    detail = _analyze(client, "synthetic_peptide.pdb", build_synthetic_peptide.build().encode())
    result = detail["result"]
    analysis_id = detail["id"]

    json_report = client.get(f"/api/analyses/{analysis_id}/report?format=json")
    assert json_report.status_code == 200
    assert json.loads(json_report.content) == result
    assert "attachment;" in json_report.headers["content-disposition"]

    html = client.get(f"/api/analyses/{analysis_id}/report?format=html")
    markdown = client.get(f"/api/analyses/{analysis_id}/report?format=md")
    assert html.status_code == 200
    assert markdown.status_code == 200
    html_text = html.text
    markdown_text = markdown.text
    assert "Inputs and validation" in html_text
    assert "## Inputs and validation" in markdown_text
    assert "Missing data" in html_text
    assert "Limitations" in html_text
    assert result["reproducibility"]["config_hash"] in html_text
    assert result["reproducibility"]["config_hash"] in markdown_text
    assert result["created_at"] in html_text
    for measurement in result["measurements"]:
        assert measurement["name"] in html_text
        assert measurement["name"] in markdown_text
        value = measurement["value"]
        scalar = value is None or isinstance(value, (str, int, float))
        rendered = format_value(value)
        if scalar and not any(character in rendered for character in '<>&"\''):
            assert rendered in html_text
            assert rendered in markdown_text


def test_html_report_escapes_a_script_tag_in_the_title(client: TestClient) -> None:
    title = '<script>alert("xss")</script>'
    kept = [line for line in minimal_pdb().splitlines() if not line.startswith(b"TITLE")]
    payload = f"TITLE     {title}\n".encode() + b"\n".join(kept) + b"\n"
    detail = _analyze(client, "xss.pdb", payload)
    assert detail["result"]["measurements"][0]["name"] == "title"
    title_measurement = next(item for item in detail["result"]["measurements"] if item["name"] == "title")
    assert title_measurement["value"] == title

    html = client.get(f"/api/analyses/{detail['id']}/report?format=html").text
    markdown = client.get(f"/api/analyses/{detail['id']}/report?format=md").text
    json_report = json.loads(client.get(f"/api/analyses/{detail['id']}/report?format=json").content)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert title in markdown
    assert json_report["measurements"][0]["value"] == title or any(
        item["value"] == title for item in json_report["measurements"] if item["name"] == "title"
    )


def test_rejected_report_requests(client: TestClient) -> None:
    detail = _analyze(client, "synthetic_peptide.pdb", build_synthetic_peptide.build().encode())
    missing_format = client.get(f"/api/analyses/{detail['id']}/report")
    assert missing_format.status_code == 422
    pdf = client.get(f"/api/analyses/{detail['id']}/report?format=pdf")
    assert pdf.status_code == 422
    assert "Traceback" not in pdf.text
    unknown = client.get("/api/analyses/missing/report?format=json")
    assert unknown.status_code == 404
