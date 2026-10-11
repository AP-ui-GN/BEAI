"""Select one conformer per atom and classify residues.

Alternate locations keep the highest occupancy. Ties use the alphabetically
first altloc id. Geometry and atom counts use that conformer only. Completeness
still treats an atom as present when any altloc contains it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.services.structure.ccd import ComponentTable

WATER_NAMES = frozenset({"HOH", "WAT"})


@dataclass
class AtomRecord:
    name: str
    element: str
    coord: tuple[float, float, float]
    occupancy: float
    bfactor: float
    altloc: str
    hydrogen: bool


@dataclass
class ResidueRecord:
    name: str
    chain_id: str
    resseq: int
    icode: str
    hetflag: str
    kind: str
    atoms: list[AtomRecord]
    altlocs: list[dict]
    present_atom_names: set[str] = field(default_factory=set)


def residue_records(model, components: ComponentTable) -> tuple[list[ResidueRecord], list[str]]:
    warnings: list[str] = []
    blank_element = False
    records: list[ResidueRecord] = []
    for chain in model.get_chains():
        chain_id = str(chain.id).strip()
        for residue in chain.get_residues():
            hetflag, resseq, icode = residue.id
            icode_text = "" if icode in {None, " "} else str(icode).strip()
            resname = residue.get_resname().strip().upper()
            atoms, altlocs, missing_element = _selected_atoms(residue)
            blank_element = blank_element or missing_element
            kind = _kind(resname, str(hetflag), components)
            records.append(
                ResidueRecord(
                    name=resname,
                    chain_id=chain_id,
                    resseq=int(resseq),
                    icode=icode_text,
                    hetflag=str(hetflag),
                    kind=kind,
                    atoms=atoms,
                    altlocs=altlocs,
                    present_atom_names={atom.name for atom in atoms} | _all_atom_names(residue),
                )
            )
    if blank_element:
        warnings.append(
            "At least one atom has a blank element symbol. "
            "Hydrogen classification then uses only atom names H or H followed by digits."
        )
    return records, warnings


def _kind(resname: str, hetflag: str, components: ComponentTable) -> str:
    if hetflag == "W" or resname in WATER_NAMES:
        return "water"
    if components.get(resname) is not None:
        return "polymer"
    if hetflag == " ":
        return "polymer"
    return "ligand"


def _selected_atoms(residue) -> tuple[list[AtomRecord], list[dict], bool]:
    grouped: dict[str, list] = {}
    for atom in _unpacked(residue):
        grouped.setdefault(atom.get_name().strip().upper(), []).append(atom)
    selected: list[AtomRecord] = []
    altlocs: list[dict] = []
    blank_element = False
    for name, atoms in grouped.items():
        chosen = min(atoms, key=lambda atom: (-_occupancy(atom), _altloc(atom)))
        element = (chosen.element or "").strip().upper()
        if not element:
            blank_element = True
        record = AtomRecord(
            name=name,
            element=element,
            coord=_coord(chosen),
            occupancy=_occupancy(chosen),
            bfactor=float(chosen.get_bfactor()),
            altloc=_altloc(chosen),
            hydrogen=_is_hydrogen(element, name),
        )
        selected.append(record)
        populated = [atom for atom in atoms if _altloc(atom)]
        if len(atoms) > 1 or populated:
            altlocs.append(
                {
                    "atom_name": name,
                    "selected_altloc": record.altloc,
                    "selected_occupancy": record.occupancy,
                    "conformers": [
                        {"altloc": _altloc(atom), "occupancy": _occupancy(atom)} for atom in sorted(atoms, key=_altloc)
                    ],
                }
            )
    return selected, altlocs, blank_element


def _all_atom_names(residue) -> set[str]:
    return {atom.get_name().strip().upper() for atom in _unpacked(residue)}


def _unpacked(residue) -> list:
    if hasattr(residue, "get_unpacked_list"):
        return list(residue.get_unpacked_list())
    return list(residue.get_atoms())


def _altloc(atom) -> str:
    value = getattr(atom, "altloc", " ") or " "
    text = str(value).strip()
    return "" if text in {"", "."} else text


def _occupancy(atom) -> float:
    value = atom.get_occupancy()
    if value is None:
        return 0.0
    return float(value)


def _coord(atom) -> tuple[float, float, float]:
    xyz = atom.get_coord()
    return (float(xyz[0]), float(xyz[1]), float(xyz[2]))


def _is_hydrogen(element: str, name: str) -> bool:
    if element in {"H", "D"}:
        return True
    if element:
        return False
    return name == "H" or (name.startswith("H") and name[1:].isdigit())
