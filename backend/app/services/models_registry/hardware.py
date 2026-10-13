"""Live RAM and accelerator report.

RAM comes from psutil. CUDA and MPS are queried only when PyTorch imports and
reports them. A missing PyTorch install is a reason, not a guessed device.
"""

from __future__ import annotations

from typing import Any

from backend.app.core.capabilities import probe_import
from backend.app.core.errors import CapabilityUnavailable


def read_hardware() -> dict[str, Any]:
    """Return total and available RAM in bytes, plus CUDA and MPS status."""

    try:
        import psutil
    except Exception as exc:
        raise CapabilityUnavailable(f"psutil is not installed ({exc.__class__.__name__}).") from exc
    memory = psutil.virtual_memory()
    cuda, mps = _accelerators()
    return {
        "ram_total_bytes": int(memory.total),
        "ram_available_bytes": int(memory.available),
        "cuda": cuda,
        "mps": mps,
    }


def _accelerators() -> tuple[dict[str, Any], dict[str, Any]]:
    probe = probe_import("torch", "PyTorch")
    if not probe["available"]:
        return (
            {
                "available": False,
                "version": None,
                "reason": "PyTorch is not installed, so CUDA was not queried.",
            },
            {
                "available": False,
                "version": None,
                "reason": "PyTorch is not installed, so MPS was not queried.",
            },
        )
    import torch

    if torch.cuda.is_available():
        cuda_version = getattr(torch.version, "cuda", None)
        cuda = {
            "available": True,
            "version": str(cuda_version) if cuda_version else str(torch.__version__),
            "reason": None,
        }
    else:
        cuda = {
            "available": False,
            "version": None,
            "reason": "torch.cuda.is_available() is false.",
        }
    mps_backend = getattr(torch.backends, "mps", None)
    if mps_backend is not None and bool(mps_backend.is_available()):
        mps = {"available": True, "version": str(torch.__version__), "reason": None}
    else:
        mps = {
            "available": False,
            "version": None,
            "reason": "torch.backends.mps.is_available() is false.",
        }
    return cuda, mps
