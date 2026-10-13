"""Secondary structure from DSSP when mkdssp is on PATH, otherwise Biotite P-SEA.

DSSP codes follow Kabsch and Sander (Biopolymers 22, 1983) as written by
mkdssp. P-SEA follows Labesse et al. as implemented by Biotite
``annotate_sse`` (helix ``a``, strand ``b``, coil ``c``). File HELIX and SHEET
records are not used as the computed assignment.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

from backend.app.services.structure.residues import ResidueRecord

logger = logging.getLogger(__name__)

HELIX_CODES = frozenset({"H", "G", "I"})
STRAND_CODES = frozenset({"E", "B"})


def assign_secondary_structure(
    model: Any,
    path: Path,
    polymer: list[ResidueRecord],
) -> tuple[dict[tuple[str, int, str], str], dict[str, Any], list[str]]:
    """Return a map of (chain, resseq, icode) to a code, the method record, and warnings."""

    executable = shutil.which("mkdssp") or shutil.which("dssp")
    if executable is not None:
        try:
            return _dssp(model, path, executable)
        except Exception:
            logger.info("DSSP failed; falling back to P-SEA", exc_info=True)
            warnings = ["mkdssp was on PATH but the DSSP run failed. Biotite P-SEA was used instead."]
            codes, method = _psea(polymer)
            return codes, method, warnings
    codes, method = _psea(polymer)
    return codes, method, ["mkdssp is not on PATH. Secondary structure used Biotite P-SEA."]


def _dssp(model: Any, path: Path, executable: str) -> tuple[dict[tuple[str, int, str], str], dict[str, Any], list[str]]:
    from Bio.PDB.DSSP import DSSP

    dssp = DSSP(model, str(path), dssp=executable)
    codes: dict[tuple[str, int, str], str] = {}
    for key in dssp.keys():
        chain_id, residue_id = key
        _hetflag, resseq, icode = residue_id
        icode_text = "" if icode in {None, " "} else str(icode).strip()
        value = dssp[key]
        ss = str(value[2]).strip() or "-"
        codes[(str(chain_id).strip(), int(resseq), icode_text)] = ss
    version = _version(executable)
    method = {
        "name": "secondary_structure",
        "software": "mkdssp",
        "version": version,
        "parameters": {
            "algorithm": "DSSP",
            "executable": executable,
            "reference": "Kabsch and Sander, Biopolymers 22 (1983) 2577-2637",
            "helix_codes": sorted(HELIX_CODES),
            "strand_codes": sorted(STRAND_CODES),
        },
    }
    return codes, method, []


def _psea(polymer: list[ResidueRecord]) -> tuple[dict[tuple[str, int, str], str], dict[str, Any]]:
    import biotite
    import biotite.structure as struc
    import numpy

    codes: dict[tuple[str, int, str], str] = {}
    by_chain: dict[str, list[ResidueRecord]] = {}
    for residue in polymer:
        by_chain.setdefault(residue.chain_id, []).append(residue)
    for chain_id, residues in by_chain.items():
        ordered = sorted(residues, key=lambda item: (item.resseq, item.icode))
        ordered = [residue for residue in ordered if any(not atom.hydrogen for atom in residue.atoms)]
        names: list[str] = []
        elements: list[str] = []
        res_names: list[str] = []
        res_ids: list[int] = []
        coords: list[tuple[float, float, float]] = []
        for residue in ordered:
            for atom in residue.atoms:
                if atom.hydrogen:
                    continue
                coords.append(atom.coord)
                names.append(atom.name)
                elements.append(atom.element or "C")
                res_names.append(residue.name)
                res_ids.append(residue.resseq)
        if not coords:
            continue
        array = struc.AtomArray(len(coords))
        array.coord = numpy.array(coords, dtype=numpy.float32)
        array.set_annotation("atom_name", numpy.array(names))
        array.set_annotation("res_name", numpy.array(res_names))
        array.set_annotation("element", numpy.array(elements))
        array.set_annotation("chain_id", numpy.array([chain_id] * len(coords)))
        array.set_annotation("res_id", numpy.array(res_ids, dtype=int))
        sse = struc.annotate_sse(array)
        for residue, code in zip(ordered, sse, strict=True):
            letter = str(code)
            mapped = {"a": "H", "b": "E", "c": "C", "": ""}.get(letter, letter)
            codes[(chain_id, residue.resseq, residue.icode)] = mapped
    method = {
        "name": "secondary_structure",
        "software": "biotite",
        "version": biotite.__version__,
        "parameters": {
            "algorithm": "P-SEA",
            "function": "biotite.structure.annotate_sse",
            "reference": "Labesse et al., via Biotite. Biotite documents deviations from the original program.",
            "mapping": {"a": "H", "b": "E", "c": "C"},
            "short_chain": "Biotite returns coil for a chain with 5 or fewer residues.",
        },
    }
    return codes, method


def _version(executable: str) -> str | None:
    import subprocess

    try:
        completed = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = (completed.stdout or completed.stderr or "").strip()
    return text.splitlines()[0][:200] if text else None
