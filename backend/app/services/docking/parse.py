"""Parse AutoDock Vina PDBQT output.

The score is the first number on a ``REMARK VINA RESULT:`` line, in kcal/mol.
It is a docking score, not an experimental affinity. This parser was checked
against a file produced by Vina 1.2.5 on 2026-10-13.
"""

from __future__ import annotations

from typing import Any


def parse_vina_pdbqt(text: str) -> list[dict[str, Any]]:
    """Return one record per MODEL. Scores are copied from the REMARK line."""

    modes: list[dict[str, Any]] = []
    score: float | None = None
    rmsd_lb: float | None = None
    rmsd_ub: float | None = None
    atoms: list[str] = []
    model_open = False
    for line in text.splitlines():
        if line.startswith("REMARK VINA RESULT:"):
            parts = line.split()
            if len(parts) < 6:
                continue
            score = float(parts[-3])
            rmsd_lb = float(parts[-2])
            rmsd_ub = float(parts[-1])
        elif line.startswith("MODEL"):
            model_open = True
            atoms = []
        elif model_open and (line.startswith("ATOM") or line.startswith("HETATM")):
            atoms.append(line)
        elif line.startswith("ENDMDL") and model_open:
            if score is None:
                raise ValueError("A MODEL ended without a REMARK VINA RESULT line.")
            modes.append(
                {
                    "affinity_kcal_mol": score,
                    "rmsd_lower_bound": rmsd_lb,
                    "rmsd_upper_bound": rmsd_ub,
                    "pdbqt": "\n".join(atoms) + ("\n" if atoms else ""),
                }
            )
            model_open = False
            score = None
    return modes
