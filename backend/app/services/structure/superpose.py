"""Sequence alignment followed by C-alpha Kabsch superposition.

The alignment is a global BLOSUM62 alignment with the same gap penalties as
sequence alignment. It is not a homology inference. RMSD is the root mean
square distance of matched C-alpha atoms after the optimal rigid transform,
in angstroms. Fewer than 3 matched pairs is refused.
"""

from __future__ import annotations

from typing import Any

import numpy
from Bio.Align import PairwiseAligner, substitution_matrices

from backend.app.core.errors import InvalidInput
from backend.app.services.structure.residues import ResidueRecord

OPEN_GAP = -10.0
EXTEND_GAP = -1.0
MIN_PAIRS = 3


def superpose_chains(
    left: list[ResidueRecord],
    right: list[ResidueRecord],
    *,
    left_letters: str,
    right_letters: str,
) -> dict[str, Any]:
    """Superpose ``right`` onto ``left``. Both residue lists follow the letter strings."""

    if len(left_letters) != len(left) or len(right_letters) != len(right):
        raise InvalidInput("The sequence and residue lists do not have the same length.")
    aligner = PairwiseAligner()
    aligner.mode = "global"
    aligner.substitution_matrix = substitution_matrices.load("BLOSUM62")
    aligner.open_gap_score = OPEN_GAP
    aligner.extend_gap_score = EXTEND_GAP
    alignment = next(iter(aligner.align(left_letters, right_letters)))
    left_row = str(alignment[0])
    right_row = str(alignment[1])
    left_index = 0
    right_index = 0
    mobile: list[tuple[float, float, float]] = []
    target: list[tuple[float, float, float]] = []
    pairs: list[dict[str, Any]] = []
    for left_char, right_char in zip(left_row, right_row, strict=True):
        left_residue = left[left_index] if left_char != "-" else None
        right_residue = right[right_index] if right_char != "-" else None
        if left_char != "-":
            left_index += 1
        if right_char != "-":
            right_index += 1
        if left_residue is None or right_residue is None:
            continue
        left_ca = _ca(left_residue)
        right_ca = _ca(right_residue)
        if left_ca is None or right_ca is None:
            continue
        target.append(left_ca)
        mobile.append(right_ca)
        pairs.append({"left_resseq": left_residue.resseq, "right_resseq": right_residue.resseq})
    if len(mobile) < MIN_PAIRS:
        raise InvalidInput(
            f"Only {len(mobile)} matched C-alpha pairs were found. At least {MIN_PAIRS} are required, "
            "so superposition was not run."
        )
    rmsd, rotation, translation = rigid_rmsd(numpy.array(mobile, dtype=float), numpy.array(target, dtype=float))
    return {
        "rmsd_angstrom": rmsd,
        "aligned_residue_count": len(mobile),
        "rotation": rotation.tolist(),
        "translation_angstrom": translation.tolist(),
        "pairs": pairs,
        "matrix": "BLOSUM62",
        "open_gap_score": OPEN_GAP,
        "extend_gap_score": EXTEND_GAP,
    }


def rigid_rmsd(mobile: numpy.ndarray, target: numpy.ndarray) -> tuple[float, numpy.ndarray, numpy.ndarray]:
    """Kabsch RMSD. ``mobile`` is moved onto ``target``. Both arrays are (N, 3)."""

    if mobile.shape != target.shape or mobile.ndim != 2 or mobile.shape[1] != 3 or mobile.shape[0] < MIN_PAIRS:
        raise InvalidInput(f"At least {MIN_PAIRS} matched C-alpha pairs are required for superposition.")
    mobile_center = mobile.mean(axis=0)
    target_center = target.mean(axis=0)
    covariance = (mobile - mobile_center).T @ (target - target_center)
    _u, _singular, vt = numpy.linalg.svd(covariance)
    u = _u
    rotation = vt.T @ u.T
    if numpy.linalg.det(rotation) < 0:
        vt = vt.copy()
        vt[-1, :] *= -1
        rotation = vt.T @ u.T
    aligned = (rotation @ (mobile - mobile_center).T).T + target_center
    delta = aligned - target
    rmsd = float(numpy.sqrt(numpy.mean(numpy.sum(delta * delta, axis=1))))
    translation = target_center - rotation @ mobile_center
    return rmsd, rotation, translation


def _ca(residue: ResidueRecord) -> tuple[float, float, float] | None:
    for atom in residue.atoms:
        if atom.name == "CA" and not atom.hydrogen:
            return atom.coord
    return None
