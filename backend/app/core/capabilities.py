"""Probe optional tools. Imports are lazy so a missing tool never crashes startup."""

from __future__ import annotations

import importlib
import shutil
import subprocess
from typing import Any


def _unavailable(reason: str) -> dict[str, Any]:
    return {"available": False, "version": None, "reason": reason}


def _available(version: str | None) -> dict[str, Any]:
    return {"available": True, "version": version, "reason": None}


def probe_import(module: str, distribution: str) -> dict[str, Any]:
    """Return availability for a Python distribution without importing it at module import."""

    try:
        imported = importlib.import_module(module)
    except Exception as exc:
        return _unavailable(f"{distribution} is not installed ({exc.__class__.__name__})")
    version = getattr(imported, "__version__", None)
    return _available(str(version) if version is not None else None)


def probe_executable(names: list[str], label: str) -> dict[str, Any]:
    """Return availability for the first executable name found on PATH."""

    for name in names:
        path = shutil.which(name)
        if path is None:
            continue
        version = _executable_version(path)
        return _available(version)
    joined = " or ".join(names)
    return _unavailable(f"{label} ({joined}) is not on PATH")


def _executable_version(path: str) -> str | None:
    try:
        completed = subprocess.run(
            [path, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = (completed.stdout or completed.stderr or "").strip()
    if not text:
        return None
    return text.splitlines()[0][:200]


def probe_gpu() -> dict[str, Any]:
    """Report an NVIDIA GPU only when ``nvidia-smi`` answers. No GPU is invented."""

    path = shutil.which("nvidia-smi")
    if path is None:
        return _unavailable("nvidia-smi is not on PATH")
    try:
        completed = subprocess.run(
            [path, "--query-gpu=driver_version", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return _unavailable(f"nvidia-smi could not be run ({exc.__class__.__name__})")
    if completed.returncode != 0:
        return _unavailable("nvidia-smi exited with a non-zero status")
    line = completed.stdout.strip().splitlines()
    version = line[0].strip() if line and line[0].strip() else None
    if version is None:
        return _unavailable("nvidia-smi returned no driver version")
    return _available(version)


def openmm_platform_names() -> list[str]:
    """Return OpenMM platform names. An import failure is an empty list, not a guessed device."""

    try:
        from openmm import Platform
    except Exception:
        return []
    return [Platform.getPlatform(index).getName() for index in range(Platform.getNumPlatforms())]


def probe_all() -> dict[str, dict[str, Any]]:
    """Capability map required by ``GET /api/health``."""

    return {
        "rdkit": probe_import("rdkit", "RDKit"),
        "biotite": probe_import("biotite", "Biotite"),
        "mkdssp": probe_executable(["mkdssp", "dssp"], "mkdssp"),
        "fpocket": probe_executable(["fpocket"], "fpocket"),
        "vina": probe_executable(["vina"], "Vina"),
        "meeko": probe_import("meeko", "Meeko"),
        "openmm": probe_import("openmm", "OpenMM"),
        "pytorch": probe_import("torch", "PyTorch"),
        "gpu": probe_gpu(),
    }
