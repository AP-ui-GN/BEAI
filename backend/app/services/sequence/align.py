"""Global pairwise alignment. This is not a homology call.

The substitution matrix is BLOSUM62. Gap penalties are an open score of -10
and an extension score of -1, in the units of that matrix. Identity including
gaps is the number of identical letters divided by the number of alignment
columns. Identity over aligned pairs uses only columns where both sequences
have a letter.
"""

from __future__ import annotations

import hashlib
import json
import platform
import uuid
from datetime import UTC, datetime
from typing import Any

from Bio import __version__ as biopython_version
from Bio.Align import PairwiseAligner, substitution_matrices

OPEN_GAP = -10.0
EXTEND_GAP = -1.0
MATRIX_NAME = "BLOSUM62"


def align_sequences(
    left: str,
    right: str,
    *,
    left_id: str,
    right_id: str,
    left_sha256: str,
    right_sha256: str,
) -> dict[str, Any]:
    """Return an ``AnalysisResult`` for one global alignment."""

    aligner = PairwiseAligner()
    aligner.mode = "global"
    aligner.substitution_matrix = substitution_matrices.load(MATRIX_NAME)
    aligner.open_gap_score = OPEN_GAP
    aligner.extend_gap_score = EXTEND_GAP
    alignment = next(iter(aligner.align(left, right)))
    left_aligned = str(alignment[0])
    right_aligned = str(alignment[1])
    if len(left_aligned) != len(right_aligned):
        raise RuntimeError("alignment strings differ in length")
    columns = len(left_aligned)
    identical = sum(
        1 for a, b in zip(left_aligned, right_aligned, strict=True) if a == b and a != "-"
    )
    aligned_pairs = sum(1 for a, b in zip(left_aligned, right_aligned, strict=True) if a != "-" and b != "-")
    identical_pairs = sum(
        1 for a, b in zip(left_aligned, right_aligned, strict=True) if a == b and a != "-" and b != "-"
    )
    identity_including_gaps = identical / columns if columns else None
    identity_over_aligned_pairs = identical_pairs / aligned_pairs if aligned_pairs else None
    parameters = {
        "mode": "global",
        "matrix": MATRIX_NAME,
        "open_gap_score": OPEN_GAP,
        "extend_gap_score": EXTEND_GAP,
        "identity_including_gaps": "identical non-gap letters / alignment columns",
        "identity_over_aligned_pairs": "identical letters / columns where both sequences have a letter",
    }
    now = datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    return {
        "analysis_id": str(uuid.uuid4()),
        "kind": "sequence_alignment",
        "created_at": now,
        "status": "succeeded",
        "inputs": [
            {
                "role": "sequence_left",
                "filename": None,
                "source_id": left_id,
                "sha256": left_sha256,
                "validation_status": "valid",
                "validation_messages": [],
            },
            {
                "role": "sequence_right",
                "filename": None,
                "source_id": right_id,
                "sha256": right_sha256,
                "validation_status": "valid",
                "validation_messages": [],
            },
        ],
        "methods": [
            {
                "name": "pairwise_alignment",
                "software": "Biopython PairwiseAligner",
                "version": biopython_version,
                "parameters": parameters,
            }
        ],
        "measurements": [
            {
                "name": "alignment_score",
                "value": float(alignment.score),
                "unit": "BLOSUM62",
                "origin": "calculated",
                "method": "PairwiseAligner global score with BLOSUM62, open -10, extend -1.",
                "uncertainty": None,
                "source": None,
            },
            {
                "name": "identity_including_gaps",
                "value": identity_including_gaps,
                "unit": "1",
                "origin": "calculated",
                "method": parameters["identity_including_gaps"],
                "uncertainty": None,
                "source": None,
            },
            {
                "name": "identity_over_aligned_pairs",
                "value": identity_over_aligned_pairs,
                "unit": "1",
                "origin": "calculated",
                "method": parameters["identity_over_aligned_pairs"],
                "uncertainty": None,
                "source": None,
            },
            {
                "name": "alignment_column_count",
                "value": columns,
                "unit": "1",
                "origin": "calculated",
                "method": "Length of the global alignment, including gap columns.",
                "uncertainty": None,
                "source": None,
            },
        ],
        "evidence": [],
        "limitations": [
            "This is a pairwise sequence alignment. It is not homology, function, or an evolutionary relationship.",
            "Only one optimal alignment is returned when several share the same score.",
        ],
        "warnings": [],
        "skipped_stages": [],
        "errors": [],
        "reproducibility": {
            "software_versions": {"python": platform.python_version(), "biopython": biopython_version},
            "random_seed": None,
            "config_hash": hashlib.sha256(
                json.dumps(parameters, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
            "platform": platform.platform(),
        },
        "details": {
            "alignment": {
                "left": left_aligned,
                "right": right_aligned,
                "left_id": left_id,
                "right_id": right_id,
            }
        },
    }
