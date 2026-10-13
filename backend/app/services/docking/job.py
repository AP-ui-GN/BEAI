"""Docking job. The score is labelled as a docking score, not an affinity."""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
from datetime import UTC, datetime
from typing import Any

from Bio.PDB import PDBParser

from backend.app.core.errors import CapabilityUnavailable, InvalidInput
from backend.app.jobs.runner import JobContext
from backend.app.services.docking.runner import dock_smiles
from backend.app.services.structure.ingest import get_structure, structure_file


def require_docking() -> None:
    if shutil.which("vina") is None:
        raise CapabilityUnavailable("AutoDock Vina is not on PATH. Docking is unavailable.")
    try:
        import meeko  # noqa: F401
    except Exception as exc:
        raise CapabilityUnavailable(f"Meeko is not installed ({exc.__class__.__name__}).") from exc


def run_docking_job(context: JobContext, payload: dict[str, Any]) -> dict[str, Any]:
    require_docking()
    session = context.runner.factory()
    try:
        docked = dock_payload(session, context.settings, payload, context)
    except InvalidInput:
        if context.cancelled():
            return None
        raise
    finally:
        session.close()
    filename = docked["filename"]
    digest = docked["sha256"]
    seed = docked["seed"]
    parameters = docked["parameters"]
    now = datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    measurements = [
        {
            "name": "docking_score",
            "value": docked["modes"][0]["affinity_kcal_mol"],
            "unit": "kcal/mol",
            "origin": "calculated",
            "method": "AutoDock Vina score of the first mode. This is a docking score, not an experimental affinity.",
            "uncertainty": None,
            "source": None,
        }
    ]
    return {
        "analysis_id": context.analysis_id,
        "kind": "docking",
        "created_at": now,
        "status": "succeeded",
        "inputs": [
            {
                "role": "receptor",
                "filename": filename,
                "source_id": payload["structure_id"],
                "sha256": digest,
                "validation_status": "valid",
                "validation_messages": [],
            }
        ],
        "methods": [
            {
                "name": "autodock_vina",
                "software": "AutoDock Vina",
                "version": _vina_version(),
                "parameters": parameters,
            }
        ],
        "measurements": measurements,
        "evidence": [],
        "limitations": [
            "A docking score is not a binding affinity and does not show biological efficacy.",
            "Protonation states and tautomers were not enumerated.",
        ],
        "warnings": [],
        "skipped_stages": [],
        "errors": [],
        "reproducibility": {
            "software_versions": {"python": platform.python_version(), "vina": _vina_version() or ""},
            "random_seed": seed,
            "config_hash": hashlib.sha256(json.dumps(parameters, sort_keys=True).encode()).hexdigest(),
            "platform": platform.platform(),
        },
        "details": {"modes": docked["modes"], "output_pdbqt": docked["output_pdbqt"]},
    }


def dock_payload(session: Any, settings: Any, payload: dict[str, Any], context: JobContext | None) -> dict[str, Any]:
    """Run Vina on a stored structure. ``context`` may be omitted by a workflow step."""

    require_docking()
    structure = get_structure(session, str(payload["structure_id"]))
    path = structure_file(settings, structure)
    pdb_text = path.read_text(encoding="latin-1")
    resname = str(payload.get("ligand_resname") or "").upper()
    center = _center(pdb_text, resname) if resname else tuple(payload["center"])
    size = tuple(float(value) for value in payload.get("size", [20, 20, 20]))
    seed = int(payload.get("seed", 1))
    exhaustiveness = int(payload.get("exhaustiveness", 8))
    num_modes = int(payload.get("num_modes", 3))
    drop = {resname} if resname else set()
    if context is not None:
        context.set_progress(0.1)
    docked = dock_smiles(
        receptor_pdb=pdb_text,
        ligand_smiles=str(payload["ligand_smiles"]),
        center=(float(center[0]), float(center[1]), float(center[2])),
        size=(float(size[0]), float(size[1]), float(size[2])),
        exhaustiveness=exhaustiveness,
        num_modes=num_modes,
        seed=seed,
        drop_resnames=drop,
        context=context,
        timeout=float(payload.get("timeout_seconds", 180)),
    )
    parameters = {
        "exhaustiveness": exhaustiveness,
        "num_modes": num_modes,
        "seed": seed,
        "size_angstrom": list(size),
        "center_angstrom": [float(center[0]), float(center[1]), float(center[2])],
        "ligand_preparation": "RDKit ETKDGv3 + MMFF, then Meeko. Tautomers are not enumerated.",
        "receptor_preparation": "waters and the named ligand residue removed, then mk_prepare_receptor.py",
    }
    return {
        "modes": docked["modes"],
        "output_pdbqt": docked["output_pdbqt"],
        "parameters": parameters,
        "seed": seed,
        "filename": structure.display_filename,
        "sha256": structure.sha256,
        "vina_version": _vina_version(),
    }


def _center(pdb_text: str, resname: str) -> tuple[float, float, float]:
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".pdb", delete=False) as handle:
        handle.write(pdb_text)
        name = handle.name
    structure = PDBParser(QUIET=True).get_structure("box", name)
    coords = []
    for residue in next(structure.get_models()).get_residues():
        if residue.get_resname().strip() == resname:
            for atom in residue.get_atoms():
                element = (atom.element or "").strip().upper()
                if element != "H":
                    coords.append(atom.coord)
    if not coords:
        raise InvalidInput(f"No heavy atoms named {resname} were found for the box.")
    count = len(coords)
    return (
        sum(point[0] for point in coords) / count,
        sum(point[1] for point in coords) / count,
        sum(point[2] for point in coords) / count,
    )


def _vina_version() -> str | None:
    import shutil
    import subprocess

    path = shutil.which("vina")
    if path is None:
        return None
    completed = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=5, check=False)
    text = (completed.stdout or completed.stderr or "").strip()
    return text.splitlines()[0][:200] if text else None
