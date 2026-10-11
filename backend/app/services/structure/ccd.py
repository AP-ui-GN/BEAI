"""Heavy-atom expectations from bundled wwPDB chemical component files.

The files were downloaded from ``https://files.rcsb.org/ligands/download/{ID}.cif``
on 2026-10-11. A required heavy atom has element symbol other than H or D and
``pdbx_leaving_atom_flag`` other than Y. Leaving atoms include the terminal OXT,
which is therefore not required. See ``ccd/README.md``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from Bio.PDB.MMCIF2Dict import MMCIF2Dict

_CCD_DIR = Path(__file__).resolve().parent / "ccd"


@dataclass(frozen=True)
class Component:
    comp_id: str
    one_letter: str | None
    heavy_atoms: frozenset[str]


@dataclass(frozen=True)
class ComponentTable:
    components: dict[str, Component]
    table_sha256: str

    def get(self, resname: str) -> Component | None:
        return self.components.get(resname.strip().upper())


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _clean_token(value: str) -> str:
    return value.strip().strip('"').strip("'")


def load_component_table(directory: Path | None = None) -> ComponentTable:
    """Read every ``*.cif`` component file in ``directory``."""

    root = directory or _CCD_DIR
    components: dict[str, Component] = {}
    for path in sorted(root.glob("*.cif")):
        table = MMCIF2Dict(str(path))
        comp_ids = _as_list(table.get("_chem_comp.id"))
        if not comp_ids:
            continue
        comp_id = _clean_token(comp_ids[0]).upper()
        letters = _as_list(table.get("_chem_comp.one_letter_code"))
        letter = _clean_token(letters[0]) if letters else ""
        one_letter = letter if len(letter) == 1 and letter not in {"?", "."} else None
        atom_ids = _as_list(table.get("_chem_comp_atom.atom_id"))
        symbols = _as_list(table.get("_chem_comp_atom.type_symbol"))
        leaving = _as_list(table.get("_chem_comp_atom.pdbx_leaving_atom_flag"))
        heavy: set[str] = set()
        for atom_id, symbol, flag in zip(atom_ids, symbols, leaving, strict=True):
            if _clean_token(symbol).upper() in {"H", "D"}:
                continue
            if _clean_token(flag).upper() == "Y":
                continue
            heavy.add(_clean_token(atom_id).upper())
        components[comp_id] = Component(comp_id, one_letter, frozenset(heavy))
    digest_lines = [
        f"{item.comp_id}:{item.one_letter or ''}:{','.join(sorted(item.heavy_atoms))}"
        for item in (components[key] for key in sorted(components))
    ]
    table_sha256 = hashlib.sha256("\n".join(digest_lines).encode()).hexdigest()
    return ComponentTable(components, table_sha256)


_TABLE: ComponentTable | None = None


def component_table() -> ComponentTable:
    global _TABLE
    if _TABLE is None:
        _TABLE = load_component_table()
    return _TABLE
