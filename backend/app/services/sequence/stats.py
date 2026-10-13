"""Sequence statistics from Biopython ProteinAnalysis.

Molecular weight uses ``Bio.SeqUtils.molecular_weight`` with
``seq_type="protein"`` and ``monoisotopic=False``. That sums IUPAC average
masses of the free amino acids and subtracts ``(n - 1) * 18.0153`` daltons,
which is the average mass of the linear polypeptide (terminal water included).
Isoelectric point is Biopython ``IsoelectricPoint.pi`` (bisection). GRAVY is
the Kyte-Doolittle scale exposed as ``ProteinAnalysis.gravy``.
"""

from __future__ import annotations

import hashlib
import json
import platform
import uuid
from datetime import UTC, datetime
from typing import Any

from Bio import __version__ as biopython_version
from Bio.SeqUtils.ProtParam import ProteinAnalysis

from backend.app.services.sequence.fasta import AMBIGUOUS

_LIMITATIONS = [
    "These are calculated sequence properties. They are not a measurement of mass, charge, solubility, or activity.",
    (
        "Molecular weight is the average mass of the linear chain: free-amino-acid IUPAC average masses "
        "minus (n - 1) water molecules of 18.0153 Da. It is not a monoisotopic mass."
    ),
    "The isoelectric point is Biopython's IsoelectricPoint bisection. It is not an experimental pI.",
    "GRAVY uses the Kyte-Doolittle hydropathy scale as implemented by Biopython. It is not a solubility measurement.",
    "Ambiguity codes B, Z, X, and J block mass, pI, and GRAVY. No substitute value is inserted.",
]


def sequence_statistics(
    sequence: str,
    *,
    analysis_id: str | None = None,
    created_at: str | None = None,
    source_id: str,
    header: str,
    sha256: str,
    validation_messages: list[str],
) -> dict[str, Any]:
    """Return an ``AnalysisResult`` for one unambiguous or ambiguous protein sequence."""

    ambiguous = any(character in AMBIGUOUS for character in sequence)
    warnings = list(validation_messages)
    parameters = {
        "mass": "Bio.SeqUtils.molecular_weight protein average, terminal water included",
        "water_dalton": 18.0153,
        "monoisotopic": False,
        "pi": "Bio.SeqUtils.IsoelectricPoint.pi",
        "gravy": "Kyte-Doolittle via ProteinAnalysis.gravy",
    }
    methods = [
        {
            "name": "sequence_statistics",
            "software": "Biopython",
            "version": biopython_version,
            "parameters": parameters,
        }
    ]
    composition = {letter: sequence.count(letter) for letter in sorted(set(sequence))}
    measurements: list[dict[str, Any]] = [
        _calc("length", len(sequence), "1", "Count of stored amino-acid letters after gap and terminal-stop removal."),
        _calc("amino_acid_composition", composition, "1", "Counts of letters in the stored sequence."),
    ]
    skipped: list[dict[str, str]] = []
    if ambiguous:
        for name in ("molecular_weight", "isoelectric_point", "gravy"):
            measurements.append(
                _calc(
                    name,
                    None,
                    "dalton" if name == "molecular_weight" else ("pH" if name == "isoelectric_point" else "1"),
                    "Not computed because the sequence contains ambiguity codes B, Z, X, or J.",
                )
            )
            skipped.append({"stage": name, "reason": "Ambiguous amino-acid codes are present."})
        warnings.append("Molecular weight, isoelectric point, and GRAVY are null because the sequence is ambiguous.")
    else:
        analysis = ProteinAnalysis(sequence, monoisotopic=False)
        measurements.append(
            _calc(
                "molecular_weight",
                float(analysis.molecular_weight()),
                "dalton",
                "Average mass from Bio.SeqUtils.molecular_weight (protein, monoisotopic=False), "
                "equal to the sum of free amino-acid average masses minus (n - 1) * 18.0153 Da.",
            )
        )
        measurements.append(
            _calc(
                "isoelectric_point",
                float(analysis.isoelectric_point()),
                "pH",
                "Biopython IsoelectricPoint.pi bisection on the stored sequence.",
            )
        )
        measurements.append(
            _calc(
                "gravy",
                float(analysis.gravy()),
                "1",
                "Kyte-Doolittle grand average of hydropathy from ProteinAnalysis.gravy.",
            )
        )
    now = created_at or datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    return {
        "analysis_id": analysis_id or str(uuid.uuid4()),
        "kind": "sequence_statistics",
        "created_at": now,
        "status": "succeeded",
        "inputs": [
            {
                "role": "sequence",
                "filename": None,
                "source_id": source_id,
                "sha256": sha256,
                "validation_status": "valid",
                "validation_messages": validation_messages,
            }
        ],
        "methods": methods,
        "measurements": measurements,
        "evidence": [],
        "limitations": list(_LIMITATIONS),
        "warnings": warnings,
        "skipped_stages": skipped,
        "errors": [],
        "reproducibility": {
            "software_versions": {"python": platform.python_version(), "biopython": biopython_version},
            "random_seed": None,
            "config_hash": hashlib.sha256(
                json.dumps(parameters, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
            "platform": platform.platform(),
        },
        "details": {"header": header},
    }


def _calc(name: str, value: Any, unit: str | None, method: str) -> dict[str, Any]:
    return {
        "name": name,
        "value": value,
        "unit": unit,
        "origin": "calculated",
        "method": method,
        "uncertainty": None,
        "source": None,
    }
