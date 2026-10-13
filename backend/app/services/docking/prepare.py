"""Ligand and receptor preparation for Vina.

Ligands: RDKit adds hydrogens, embeds with ETKDGv3 using the given seed, and
optimizes with MMFF when the force field has parameters. Meeko writes the
PDBQT. Protonation states and tautomers are not enumerated.

Receptors: waters and an optional residue name are removed, then
``mk_prepare_receptor.py`` writes a rigid PDBQT. The method record names both
steps.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from shutil import which

from backend.app.core.errors import CapabilityUnavailable, InvalidInput


def ligand_pdbqt(smiles: str, seed: int) -> str:
    from meeko import MoleculePreparation, PDBQTWriterLegacy
    from rdkit import Chem
    from rdkit.Chem import AllChem

    molecule = Chem.MolFromSmiles(smiles)
    if molecule is None:
        raise InvalidInput("The ligand SMILES could not be parsed.")
    molecule = Chem.AddHs(molecule)
    params = AllChem.ETKDGv3()
    params.randomSeed = int(seed)
    if AllChem.EmbedMolecule(molecule, params) != 0:
        raise InvalidInput("ETKDGv3 could not embed the ligand.")
    try:
        AllChem.MMFFOptimizeMolecule(molecule)
    except Exception as exc:
        raise InvalidInput("MMFF optimization failed for this ligand.") from exc
    prepared = MoleculePreparation()
    setups = prepared.prepare(molecule)
    if not setups:
        raise InvalidInput("Meeko did not return a ligand setup.")
    pdbqt, ok, error = PDBQTWriterLegacy.write_string(setups[0])
    if not ok:
        raise InvalidInput(f"Meeko could not write ligand PDBQT: {error}")
    return pdbqt


def receptor_pdbqt(pdb_text: str, drop_resnames: set[str]) -> str:
    kept = []
    for line in pdb_text.splitlines():
        if line.startswith(("ATOM", "HETATM", "TER", "END")):
            resname = line[17:20].strip() if len(line) >= 20 else ""
            if resname in drop_resnames or resname in {"HOH", "WAT"}:
                continue
        kept.append(line)
    if not any(line.startswith("ATOM") for line in kept):
        raise InvalidInput("The receptor has no ATOM records after preparation.")
    script = _meeko_script("mk_prepare_receptor.py")
    with tempfile.TemporaryDirectory(prefix="beai-receptor-") as directory:
        folder = Path(directory)
        pdb_path = folder / "receptor.pdb"
        pdb_path.write_text("\n".join(kept) + "\n", encoding="utf-8")
        out_base = folder / "receptor"
        completed = subprocess.run(
            [script, "--read_pdb", str(pdb_path), "-o", str(out_base), "-p", str(out_base) + ".pdbqt"],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        pdbqt_path = Path(str(out_base) + ".pdbqt")
        if completed.returncode != 0 or not pdbqt_path.is_file():
            detail = (completed.stderr or completed.stdout or "no output").strip().splitlines()
            message = detail[-1][:300] if detail else "receptor preparation failed"
            raise InvalidInput(f"Meeko receptor preparation failed: {message}")
        return pdbqt_path.read_text(encoding="utf-8")


def _meeko_script(name: str) -> str:
    beside = Path(sys.executable).with_name(name)
    if beside.is_file():
        return str(beside)
    path = which(name)
    if path is None:
        raise CapabilityUnavailable(f"{name} is not on PATH. Install Meeko in the project virtualenv.")
    return path
