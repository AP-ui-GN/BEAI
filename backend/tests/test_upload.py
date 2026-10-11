"""Upload acceptance and rejection. Paths are never built from the client filename."""

import hashlib
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.app.core.config import Settings
from backend.app.main import create_app
from backend.tests.samples import atom_lines, minimal_mmcif, minimal_pdb


def _upload(
    client: TestClient,
    filename: str,
    payload: bytes,
    content_type: str = "chemical/x-pdb",
):
    return client.post(
        "/api/structures",
        files={"file": (filename, payload, content_type)},
    )


def test_pdb_upload_lists_fetches_and_serves_bytes(client: TestClient, settings: Settings) -> None:
    payload = minimal_pdb()
    response = _upload(client, "demo.pdb", payload)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["display_filename"] == "demo.pdb"
    assert body["format"] == "pdb"
    assert body["size_bytes"] == len(payload)
    assert body["sha256"] == hashlib.sha256(payload).hexdigest()
    assert body["created_at"].endswith("Z")
    assert body["metadata"]["title"] == "MINIMAL UPLOAD"
    assert body["metadata"]["model_count"] == 1
    assert body["metadata"]["chain_ids"] == ["A"]
    assert "stored_path" not in body
    assert "Traceback" not in response.text

    listing = client.get("/api/structures")
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()["structures"]] == [body["id"]]

    fetched = client.get(f"/api/structures/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == body

    downloaded = client.get(f"/api/structures/{body['id']}/file")
    assert downloaded.status_code == 200
    assert downloaded.content == payload

    stored = list(settings.resolved_storage_dir().iterdir())
    assert len(stored) == 1
    assert stored[0].name == f"{body['id']}.pdb"
    assert stored[0].read_bytes() == payload


def test_mmcif_upload(client: TestClient) -> None:
    response = _upload(client, "mini.cif", minimal_mmcif(), "chemical/x-mmcif")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["format"] == "mmcif"
    assert body["metadata"]["title"] == "MINIMAL_MMCIF"
    assert body["metadata"]["chain_ids"] == ["A"]


def test_path_traversal_filename_stays_inside_storage(
    client: TestClient, settings: Settings, tmp_path: Path
) -> None:
    outside = tmp_path / "outside.pdb"
    response = _upload(client, "../../outside.pdb", minimal_pdb())
    assert response.status_code == 201, response.text
    assert response.json()["display_filename"] == "outside.pdb"
    assert not outside.exists()
    assert not (tmp_path / "structures" / "outside.pdb").exists()
    stored = list(settings.resolved_storage_dir().iterdir())
    assert len(stored) == 1
    assert stored[0].name.endswith(".pdb")
    assert "outside" not in stored[0].name


def test_rejects_empty_binary_extension_and_malformed(client: TestClient) -> None:
    empty = _upload(client, "empty.pdb", b"")
    assert empty.status_code == 422
    assert empty.json()["code"] == "invalid_input"
    assert "Traceback" not in empty.text

    binary = _upload(client, "bin.pdb", b"\x00\x01\x02\x03")
    assert binary.status_code == 422
    assert "binary" in binary.json()["message"]

    wrong = _upload(client, "notes.txt", minimal_pdb(), "text/plain")
    assert wrong.status_code == 422
    assert "not allowed" in wrong.json()["message"]

    malformed = _upload(client, "bad.pdb", b"this is not a structure\n")
    assert malformed.status_code == 422

    mismatched = _upload(client, "bad.cif", minimal_pdb(), "chemical/x-mmcif")
    assert mismatched.status_code == 422
    assert "data_" in mismatched.json()["message"]


def test_oversized_upload_is_413(client: TestClient) -> None:
    payload = b"ATOM  " + (b"x" * 9000)
    response = _upload(client, "big.pdb", payload)
    assert response.status_code == 413
    assert response.json()["code"] == "payload_too_large"
    assert "Traceback" not in response.text


def test_extreme_atom_count_is_422(client: TestClient, settings: Settings) -> None:
    response = _upload(client, "many.pdb", atom_lines(settings.max_atom_count + 1))
    assert response.status_code == 422, response.text
    assert "limit" in response.json()["message"]
    assert list(settings.resolved_storage_dir().iterdir()) == []


def test_unknown_structure_is_404(client: TestClient) -> None:
    response = client.get("/api/structures/missing")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    assert "Traceback" not in response.text


def test_structure_survives_a_new_process(client: TestClient, settings: Settings) -> None:
    created = _upload(client, "demo.pdb", minimal_pdb())
    assert created.status_code == 201
    with TestClient(create_app(settings)) as restarted:
        fetched = restarted.get(f"/api/structures/{created.json()['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == created.json()


def test_migration_tables_exist(client: TestClient) -> None:
    with client.app.state.engine.connect() as connection:
        names = {
            row[0]
            for row in connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        }
    assert {"structures", "analyses", "alembic_version"} <= names
