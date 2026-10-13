"""Redock a co-crystallized ligand and measure heavy-atom RMSD to that pose.

The split below is the Milestone 2 pocket split. It was frozen before any
docking RMSD was computed and is not changed after the held-out results.

RMSD uses RDKit ``CalcRMS`` in the crystal frame, with symmetry accounted for
and hydrogens removed. A docking score is not an affinity. A missing pose is
a failure, not a filled-in distance.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from backend.app.core.errors import InvalidInput
from backend.app.services.docking.parse import parse_vina_pdbqt
from backend.app.services.docking.prepare import receptor_pdbqt
from backend.app.services.docking.runner import run_argv, vina_argv

SUCCESS_RMSD_ANGSTROM = 2.0
BOX_ANGSTROM = 20.0
EXHAUSTIVENESS = 8
NUM_MODES = 1
SEED = 1

# split, PDB id, ligand residue name
COMPLEXES: list[tuple[str, str, str]] = [
    ("tuning", "3PTB", "BEN"),
    ("tuning", "1STP", "BTN"),
    ("tuning", "1HSG", "MK1"),
    ("tuning", "1FKF", "FK5"),
    ("tuning", "2PK4", "ACA"),
    ("held-out", "1AQ1", "STU"),
    ("held-out", "1TLP", "RDF"),
    ("held-out", "2GBP", "BGC"),
    ("held-out", "4DFR", "MTX"),
    ("held-out", "1DWD", "MID"),
]


def vina_version() -> str | None:
    path = shutil.which("vina")
    if path is None:
        return None
    completed = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=5, check=False)
    text = (completed.stdout or completed.stderr or "").strip()
    return text.splitlines()[0][:200] if text else None


def cactvs_canonical_smiles(ccd_text: str) -> str:
    """Read the CACTVS canonical SMILES quote from an RCSB chemical-component file."""

    for line in ccd_text.splitlines():
        if "SMILES_CANONICAL" in line and "CACTVS" in line:
            parts = line.split('"')
            if len(parts) >= 2 and parts[1]:
                return parts[1]
    raise InvalidInput("CACTVS canonical SMILES was not in the component file.")


def extract_ligand_block(pdb_text: str, resname: str) -> str:
    """PDB block for the largest residue with this name. Ties keep file order."""

    wanted = resname.strip().upper()
    groups: dict[tuple[str, str, str], list[str]] = {}
    order: list[tuple[str, str, str]] = []
    for line in pdb_text.splitlines():
        if line.startswith("ENDMDL"):
            break
        if not line.startswith("HETATM") or len(line) < 26:
            continue
        if line[17:20].strip().upper() != wanted:
            continue
        if line[16] not in {" ", "A"}:
            continue
        key = (line[21], line[22:26], line[26] if len(line) > 26 else " ")
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(line)
    if not order:
        raise InvalidInput(f"No {wanted} heavy atoms were found in the first model.")
    chosen = max(order, key=lambda key: _heavy_count(groups[key]))
    return "\n".join(groups[chosen]) + "\nEND\n"


def crystal_molecule(pdb_block: str, smiles: str) -> Any:
    """Assign component bond orders onto the crystal coordinates."""

    from rdkit import Chem
    from rdkit.Chem import AllChem

    raw = Chem.MolFromPDBBlock(pdb_block, removeHs=True, sanitize=False)
    if raw is None:
        raise InvalidInput("RDKit could not read the crystal ligand.")
    template = Chem.MolFromSmiles(smiles)
    if template is None:
        raise InvalidInput("The component SMILES could not be parsed.")
    try:
        molecule = AllChem.AssignBondOrdersFromTemplate(template, raw)
        Chem.SanitizeMol(molecule)
    except Exception as exc:
        raise InvalidInput(f"The crystal ligand could not be sanitized: {exc.__class__.__name__}.") from exc
    return molecule


def ligand_pdbqt_from_molecule(molecule: Any) -> str:
    """Write a Meeko PDBQT without replacing the heavy-atom coordinates."""

    from meeko import MoleculePreparation, PDBQTWriterLegacy
    from rdkit import Chem

    explicit = Chem.AddHs(molecule, addCoords=True)
    setups = MoleculePreparation().prepare(explicit)
    if not setups:
        raise InvalidInput("Meeko did not return a ligand setup.")
    pdbqt, ok, error = PDBQTWriterLegacy.write_string(setups[0])
    if not ok:
        raise InvalidInput(f"Meeko could not write ligand PDBQT: {error}")
    return pdbqt


def molecule_from_vina_pdbqt(text: str) -> Any:
    from meeko import PDBQTMolecule, RDKitMolCreate

    parsed = PDBQTMolecule(text, skip_typing=True)
    molecules = RDKitMolCreate.from_pdbqt_mol(parsed)
    if not molecules:
        raise InvalidInput("Meeko could not rebuild a molecule from the Vina pose.")
    return molecules[0]


def heavy_atom_rmsd(probe: Any, reference: Any) -> float:
    """In-place heavy-atom RMSD in angstroms. Symmetry is handled by RDKit."""

    from rdkit import Chem
    from rdkit.Chem import rdMolAlign

    probe_heavy = Chem.RemoveHs(probe)
    reference_heavy = Chem.RemoveHs(reference)
    try:
        return float(rdMolAlign.CalcRMS(probe_heavy, reference_heavy))
    except Exception as exc:
        raise InvalidInput(f"Heavy-atom RMSD could not be calculated: {exc.__class__.__name__}.") from exc


def ligand_centroid(molecule: Any) -> tuple[float, float, float]:
    conformer = molecule.GetConformer()
    count = molecule.GetNumAtoms()
    if count < 1:
        raise InvalidInput("The crystal ligand has no atoms.")
    xs = []
    ys = []
    zs = []
    for index in range(count):
        point = conformer.GetAtomPosition(index)
        xs.append(point.x)
        ys.append(point.y)
        zs.append(point.z)
    return (sum(xs) / count, sum(ys) / count, sum(zs) / count)


def redock_complex(
    pdb_text: str,
    resname: str,
    ccd_text: str,
    *,
    timeout: float = 300.0,
) -> dict[str, Any]:
    """Dock the extracted ligand. On failure the dict has ``error`` and no RMSD."""

    if shutil.which("vina") is None:
        raise InvalidInput("AutoDock Vina is not on PATH.")
    smiles = cactvs_canonical_smiles(ccd_text)
    block = extract_ligand_block(pdb_text, resname)
    crystal = crystal_molecule(block, smiles)
    ligand = ligand_pdbqt_from_molecule(crystal)
    receptor = receptor_pdbqt(pdb_text, {resname.strip().upper()})
    center = ligand_centroid(crystal)
    size = (BOX_ANGSTROM, BOX_ANGSTROM, BOX_ANGSTROM)
    with tempfile.TemporaryDirectory(prefix="beai-redock-") as directory:
        folder = Path(directory)
        receptor_path = folder / "receptor.pdbqt"
        ligand_path = folder / "ligand.pdbqt"
        output_path = folder / "out.pdbqt"
        receptor_path.write_text(receptor, encoding="utf-8")
        ligand_path.write_text(ligand, encoding="utf-8")
        argv = vina_argv(
            receptor_path,
            ligand_path,
            output_path,
            center,
            size,
            exhaustiveness=EXHAUSTIVENESS,
            num_modes=NUM_MODES,
            seed=SEED,
        )
        completed = run_argv(argv, None, timeout)
        if completed.returncode != 0 or not output_path.is_file():
            stderr = (completed.stderr or completed.stdout or "").strip().splitlines()
            summary = stderr[-1][:300] if stderr else "Vina exited without an output file."
            raise InvalidInput(f"Vina failed: {summary}")
        output = output_path.read_text(encoding="utf-8")
    modes = parse_vina_pdbqt(output)
    if not modes:
        raise InvalidInput("Vina finished but the output had no scored modes.")
    pose = molecule_from_vina_pdbqt(output)
    rmsd = heavy_atom_rmsd(pose, crystal)
    return {
        "smiles": smiles,
        "rmsd_angstrom": rmsd,
        "success": rmsd <= SUCCESS_RMSD_ANGSTROM,
        "affinity_kcal_mol": modes[0]["affinity_kcal_mol"],
        "output_pdbqt": output,
        "center_angstrom": [center[0], center[1], center[2]],
    }


def rmsd_of_saved_pose(pdb_text: str, resname: str, ccd_text: str, vina_pdbqt: str) -> float:
    """Recompute RMSD from a stored Vina file. Does not launch Vina."""

    smiles = cactvs_canonical_smiles(ccd_text)
    crystal = crystal_molecule(extract_ligand_block(pdb_text, resname), smiles)
    pose = molecule_from_vina_pdbqt(vina_pdbqt)
    return heavy_atom_rmsd(pose, crystal)


def write_benchmark(fixture_root: Path, destination: Path) -> dict[str, Any]:
    """Dock each complex and write pose files plus ``results.json``. Failures stay in the table."""

    import json

    rows: list[dict[str, Any]] = []
    version = vina_version()
    for split, pdb_id, resname in COMPLEXES:
        pdb_text = (fixture_root / "pockets" / f"{pdb_id}.pdb").read_text(encoding="utf-8", errors="replace")
        ccd_text = (destination / "ccd" / f"{resname}.cif").read_text(encoding="utf-8", errors="replace")
        row: dict[str, Any] = {"split": split, "pdb": pdb_id, "ligand": resname}
        try:
            result = redock_complex(pdb_text, resname, ccd_text)
        except InvalidInput as exc:
            row["error"] = exc.message
        else:
            (destination / f"{pdb_id}_{resname}.pdbqt").write_text(result["output_pdbqt"], encoding="utf-8")
            row["rmsd_angstrom"] = result["rmsd_angstrom"]
            row["success"] = result["success"]
            row["affinity_kcal_mol"] = result["affinity_kcal_mol"]
            row["smiles"] = result["smiles"]
            row["center_angstrom"] = result["center_angstrom"]
        rows.append(row)
        payload = _payload(version, rows)
        (destination / "results.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(row), flush=True)
    return _payload(version, rows)


def _payload(version: str | None, rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "vina_version": version,
        "exhaustiveness": EXHAUSTIVENESS,
        "num_modes": NUM_MODES,
        "seed": SEED,
        "box_angstrom": BOX_ANGSTROM,
        "success_rmsd_angstrom": SUCCESS_RMSD_ANGSTROM,
        "rows": rows,
    }


def _heavy_count(lines: list[str]) -> int:
    count = 0
    for line in lines:
        element = line[76:78].strip().upper() if len(line) >= 78 else ""
        if element in {"", "H", "D"}:
            if element in {"H", "D"}:
                continue
            name = line[12:16].strip().upper()
            if name.startswith("H"):
                continue
        count += 1
    return count


def main() -> None:
    root = Path("backend/tests/fixtures")
    payload = write_benchmark(root, root / "vina" / "redock")
    print("vina", payload["vina_version"], flush=True)


if __name__ == "__main__":
    main()
