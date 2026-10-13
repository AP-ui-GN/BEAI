"""Download the ESM-2 8M checkpoint into ``models/`` and check sha256 values."""

from __future__ import annotations

import hashlib
from pathlib import Path

import httpx

from backend.app.core.errors import CapabilityUnavailable, ExternalServiceError, InvalidInput
from backend.app.services.embeddings.constants import FILE_SHA256, SOURCE_URL
from backend.app.services.models_registry.runtime import resolve_weights_path


def checkpoint_dir() -> Path:
    path = resolve_weights_path("esm2_t6_8M_UR50D/model.safetensors")
    return path.parent


def verify_checkpoint(directory: Path) -> None:
    """Raise unless every required file is present and matches ``FILE_SHA256``."""

    missing = [name for name in FILE_SHA256 if not (directory / name).is_file()]
    if missing:
        joined = ", ".join(missing)
        raise CapabilityUnavailable(f"The weight file for this model is not on disk ({joined}).")
    for name, expected in FILE_SHA256.items():
        digest = hashlib.sha256((directory / name).read_bytes()).hexdigest()
        if digest != expected:
            raise InvalidInput(f"The checksum of {name} does not match the recorded sha256.")


def ensure_checkpoint() -> dict[str, object]:
    """Download any missing ESM-2 file from the fixed Hub URL. Refuse a bad checksum."""

    directory = checkpoint_dir()
    directory.mkdir(parents=True, exist_ok=True)
    downloaded: list[str] = []
    with httpx.Client(timeout=120.0, follow_redirects=True, headers={"User-Agent": "BEAI/0.1"}) as client:
        for name, expected in FILE_SHA256.items():
            path = directory / name
            if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == expected:
                continue
            url = f"{SOURCE_URL}/resolve/main/{name}"
            try:
                response = client.get(url)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise ExternalServiceError(f"The model host did not return {name}.") from exc
            digest = hashlib.sha256(response.content).hexdigest()
            if digest != expected:
                raise InvalidInput(f"The downloaded checksum of {name} does not match the recorded sha256.")
            temporary = path.with_suffix(path.suffix + ".partial")
            temporary.write_bytes(response.content)
            temporary.replace(path)
            downloaded.append(name)
    verify_checkpoint(directory)
    weight = directory / "model.safetensors"
    return {
        "downloaded": downloaded,
        "checksum_sha256": FILE_SHA256["model.safetensors"],
        "size_bytes": weight.stat().st_size,
    }
