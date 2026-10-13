"""Structure-comparison job. The mobile chain is superposed onto the reference chain."""

from __future__ import annotations

import hashlib
import json
import platform
from datetime import UTC, datetime
from typing import Any

from Bio import __version__ as biopython_version
from Bio.PDB import MMCIFParser, PDBParser

from backend.app.core.errors import InvalidInput
from backend.app.jobs.runner import JobContext
from backend.app.services.structure.ccd import component_table
from backend.app.services.structure.ingest import get_structure, structure_file
from backend.app.services.structure.residues import ResidueRecord, residue_records
from backend.app.services.structure.superpose import superpose_chains


def run_comparison_job(context: JobContext, payload: dict[str, Any]) -> dict[str, Any]:
    session = context.runner.factory()
    try:
        reference = get_structure(session, str(payload["structure_id"]))
        mobile = get_structure(session, str(payload["other_structure_id"]))
        reference_path = structure_file(context.settings, reference)
        mobile_path = structure_file(context.settings, mobile)
        reference_format = reference.format
        mobile_format = mobile.format
        reference_name = reference.display_filename
        mobile_name = mobile.display_filename
        reference_sha = reference.sha256
        mobile_sha = mobile.sha256
    finally:
        session.close()
    if context.cancelled():
        return None
    context.set_progress(0.25)
    reference_residues, reference_letters = _chain_polymer(reference_path, reference_format, str(payload["chain_id"]))
    mobile_residues, mobile_letters = _chain_polymer(mobile_path, mobile_format, str(payload["other_chain_id"]))
    context.set_progress(0.6)
    fit = superpose_chains(
        reference_residues,
        mobile_residues,
        left_letters=reference_letters,
        right_letters=mobile_letters,
    )
    now = datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    parameters = {
        "matrix": fit["matrix"],
        "open_gap_score": fit["open_gap_score"],
        "extend_gap_score": fit["extend_gap_score"],
        "minimum_pairs": 3,
        "atom_selection": "C-alpha",
        "algorithm": "Kabsch",
    }
    return {
        "analysis_id": context.analysis_id,
        "kind": "structure_comparison",
        "created_at": now,
        "status": "succeeded",
        "inputs": [
            {
                "role": "reference_structure",
                "filename": reference_name,
                "source_id": payload["structure_id"],
                "sha256": reference_sha,
                "validation_status": "valid",
                "validation_messages": [],
            },
            {
                "role": "mobile_structure",
                "filename": mobile_name,
                "source_id": payload["other_structure_id"],
                "sha256": mobile_sha,
                "validation_status": "valid",
                "validation_messages": [],
            },
        ],
        "methods": [
            {
                "name": "structure_comparison",
                "software": "NumPy SVD Kabsch after Biopython PairwiseAligner",
                "version": biopython_version,
                "parameters": parameters,
            }
        ],
        "measurements": [
            {
                "name": "rmsd_ca",
                "value": fit["rmsd_angstrom"],
                "unit": "angstrom",
                "origin": "calculated",
                "method": "Kabsch RMSD of matched C-alpha atoms after a global BLOSUM62 alignment.",
                "uncertainty": None,
                "source": None,
            },
            {
                "name": "aligned_residue_count",
                "value": fit["aligned_residue_count"],
                "unit": "1",
                "origin": "calculated",
                "method": "Matched residues that both have a C-alpha atom.",
                "uncertainty": None,
                "source": None,
            },
        ],
        "evidence": [],
        "limitations": [
            "This is a rigid C-alpha superposition after a pairwise sequence alignment. It is not a homology model.",
            "RMSD is not a measure of stability, binding, or model quality beyond the matched atoms.",
        ],
        "warnings": [],
        "skipped_stages": [],
        "errors": [],
        "reproducibility": {
            "software_versions": {
                "python": platform.python_version(),
                "biopython": biopython_version,
                "numpy": numpy_version(),
            },
            "random_seed": None,
            "config_hash": hashlib.sha256(
                json.dumps(parameters, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
            "platform": platform.platform(),
        },
        "details": {
            "reference_chain_id": payload["chain_id"],
            "mobile_chain_id": payload["other_chain_id"],
            "rotation": fit["rotation"],
            "translation_angstrom": fit["translation_angstrom"],
            "pairs": fit["pairs"],
            "superposed_pdb": _superposed_pdb(mobile_residues, fit["rotation"], fit["translation_angstrom"]),
        },
    }


def _chain_polymer(path: Any, structure_format: str, chain_id: str) -> tuple[list[ResidueRecord], str]:
    if structure_format == "pdb":
        structure = PDBParser(QUIET=True).get_structure("compare", str(path))
    elif structure_format == "mmcif":
        structure = MMCIFParser(QUIET=True).get_structure("compare", str(path))
    else:
        raise InvalidInput("Unsupported structure format.")
    model = next(iter(structure.get_models()), None)
    if model is None:
        raise InvalidInput("The structure has no model.")
    residues, _warnings = residue_records(model, component_table())
    polymer = [residue for residue in residues if residue.kind == "polymer" and residue.chain_id == chain_id]
    if not polymer:
        raise InvalidInput(f"Chain {chain_id} has no polymer residues.")
    letters: list[str] = []
    table = component_table()
    for residue in polymer:
        component = table.get(residue.name)
        letters.append(component.one_letter if component and component.one_letter else "X")
    return polymer, "".join(letters)


def _superposed_pdb(
    residues: list[ResidueRecord],
    rotation: list[list[float]],
    translation: list[float],
) -> str:
    import numpy

    matrix = numpy.array(rotation, dtype=float)
    shift = numpy.array(translation, dtype=float)
    lines = ["REMARK BEAI superposed mobile chain", "MODEL        1"]
    serial = 1
    for residue in residues:
        for atom in residue.atoms:
            coord = matrix @ numpy.array(atom.coord, dtype=float) + shift
            icode = residue.icode[:1]
            lines.append(
                f"ATOM  {serial:5d} {atom.name:>4} {residue.name:>3} {residue.chain_id:>1}"
                f"{residue.resseq:4d}{icode:1}   "
                f"{coord[0]:8.3f}{coord[1]:8.3f}{coord[2]:8.3f}"
                f"{atom.occupancy:6.2f}{atom.bfactor:6.2f}          {atom.element:>2}"
            )
            serial += 1
    lines.append("END")
    return "\n".join(lines) + "\n"


def numpy_version() -> str:
    import numpy

    return numpy.__version__
