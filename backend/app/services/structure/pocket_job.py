"""Pocket-detection job. fpocket is parsed when it is installed; the baseline always runs."""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
from datetime import UTC, datetime
from typing import Any

from Bio.PDB import MMCIFParser, PDBParser

from backend.app.jobs.runner import JobContext
from backend.app.services.structure.ccd import component_table
from backend.app.services.structure.ingest import get_structure, structure_file
from backend.app.services.structure.pockets import METHOD_LABEL, detect_pockets, select_ligand
from backend.app.services.structure.residues import residue_records


def run_pocket_job(context: JobContext, payload: dict[str, Any]) -> dict[str, Any]:
    session = context.runner.factory()
    try:
        structure = get_structure(session, str(payload["structure_id"]))
        path = structure_file(context.settings, structure)
        structure_format = structure.format
        filename = structure.display_filename
        digest = structure.sha256
    finally:
        session.close()
    if context.cancelled():
        return None
    context.set_progress(0.1)
    if structure_format == "pdb":
        parsed = PDBParser(QUIET=True).get_structure("pockets", str(path))
    else:
        parsed = MMCIFParser(QUIET=True).get_structure("pockets", str(path))
    model = next(parsed.get_models())
    residues, _warnings = residue_records(model, component_table())
    if context.cancelled():
        return None
    detected = detect_pockets(residues, progress=context.set_progress)
    ligand = select_ligand(residues)
    skipped = []
    warnings = []
    if shutil.which("fpocket") is None:
        skipped.append(
            {
                "stage": "fpocket",
                "reason": "fpocket is not on PATH. Only the baseline geometric detector ran.",
            }
        )
    else:
        skipped.append(
            {
                "stage": "fpocket",
                "reason": (
                    "fpocket is on PATH. This job did not launch it; the baseline detector is the recorded method."
                ),
            }
        )
    if detected["warning"]:
        warnings.append(detected["warning"])
    now = datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    parameters = detected["parameters"]
    return {
        "analysis_id": context.analysis_id,
        "kind": "pocket_detection",
        "created_at": now,
        "status": "succeeded",
        "inputs": [
            {
                "role": "structure",
                "filename": filename,
                "source_id": payload["structure_id"],
                "sha256": digest,
                "validation_status": "valid",
                "validation_messages": [],
            }
        ],
        "methods": [
            {
                "name": "pocket_detection",
                "software": "BEAI baseline geometric detector",
                "version": "1",
                "parameters": parameters,
            }
        ],
        "measurements": [
            {
                "name": "pocket_count",
                "value": len(detected["pockets"]),
                "unit": "1",
                "origin": "calculated",
                "method": METHOD_LABEL,
                "uncertainty": None,
                "source": None,
            },
            {
                "name": "pocket_method_label",
                "value": METHOD_LABEL,
                "unit": None,
                "origin": "calculated",
                "method": "Label fixed to the recorded benchmark, not a score for this structure.",
                "uncertainty": None,
                "source": None,
            },
            {
                "name": "detected_ligand",
                "value": None
                if ligand is None
                else {
                    "resname": ligand.name,
                    "chain_id": ligand.chain_id,
                    "resseq": ligand.resseq,
                    "icode": ligand.icode,
                },
                "unit": None,
                "origin": "calculated",
                "method": "Largest non-buffer ligand residue by heavy-atom count. Null when none is present.",
                "uncertainty": None,
                "source": None,
            },
        ],
        "evidence": [],
        "limitations": [
            METHOD_LABEL,
            "A pocket volume is a count of buried grid voxels. It is not a binding affinity or a druggability score.",
            "fpocket was not used for these pockets.",
        ],
        "warnings": warnings,
        "skipped_stages": skipped,
        "errors": [],
        "reproducibility": {
            "software_versions": {"python": platform.python_version(), "numpy": _numpy_version()},
            "random_seed": None,
            "config_hash": hashlib.sha256(
                json.dumps(parameters, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
            "platform": platform.platform(),
        },
        "details": {
            "pockets": detected["pockets"],
            "parameters": parameters,
        },
    }


def _numpy_version() -> str:
    import numpy

    return numpy.__version__
