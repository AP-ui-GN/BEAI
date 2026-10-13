"""In-process load state. Nothing in this module runs at import time."""

from __future__ import annotations

import hashlib
from typing import Any

from backend.app.core.config import repo_root
from backend.app.core.errors import CapabilityUnavailable, InvalidInput
from backend.app.db.models import RegisteredModel


class ModelRuntime:
    """Tracks which registry rows have been activated in this process."""

    def __init__(self) -> None:
        self._loaded: dict[str, dict[str, Any]] = {}

    def is_loaded(self, model_id: str) -> bool:
        return model_id in self._loaded

    def info(self, model_id: str) -> dict[str, Any] | None:
        stored = self._loaded.get(model_id)
        if stored is None:
            return None
        return dict(stored)

    def load(self, row: RegisteredModel) -> dict[str, Any]:
        """Activate one registered model. Callers must check hardware and dependencies first."""

        existing = self._loaded.get(row.id)
        if existing is not None:
            return dict(existing)
        artifact = invoke_loader(row)
        self._loaded[row.id] = artifact
        return dict(artifact)

    def unload(self, model_id: str) -> None:
        self._loaded.pop(model_id, None)


def invoke_loader(row: RegisteredModel) -> dict[str, Any]:
    """Run the loader named by the registry row. ``registry_only`` does not execute weights."""

    if row.loader_key != "registry_only":
        raise CapabilityUnavailable(f"No loader is registered for {row.loader_key}.")
    if not row.weights_relative:
        return {
            "weights_loaded": False,
            "note": "This registry entry has no weight file. No weights were loaded.",
        }
    path = resolve_weights_path(row.weights_relative)
    if not path.is_file():
        raise CapabilityUnavailable("The weight file for this model is not on disk.")
    if row.checksum_sha256:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != row.checksum_sha256:
            raise InvalidInput("The weight file checksum does not match the registry entry.")
    return {
        "weights_loaded": False,
        "note": "The weight file checksum matched. This loader does not execute weights.",
    }


def resolve_weights_path(relative: str):
    """Resolve a weight path and refuse anything outside ``models/``."""

    if relative.startswith(("/", "\\")) or ".." in relative.split("/"):
        raise InvalidInput("Weight paths must stay under models/.")
    root = (repo_root() / "models").resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise InvalidInput("Weight paths must stay under models/.")
    return path
