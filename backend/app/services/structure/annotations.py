"""Author HELIX and SHEET records, kept separate from computed secondary structure.

PDB columns follow the wwPDB PDB format. mmCIF uses ``_struct_conf`` and
``_struct_sheet_range`` author sequence numbers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from Bio.PDB.MMCIF2Dict import MMCIF2Dict


def file_secondary_structure(path: Path, structure_format: str) -> dict[str, list[dict[str, Any]]]:
    """Return author helix and sheet ranges. Missing records are empty lists."""

    if structure_format == "pdb":
        return _pdb(path)
    if structure_format == "mmcif":
        return _mmcif(path)
    return {"helices": [], "sheets": []}


def _pdb(path: Path) -> dict[str, list[dict[str, Any]]]:
    helices: list[dict[str, Any]] = []
    sheets: list[dict[str, Any]] = []
    for line in path.read_text(encoding="latin-1").splitlines():
        if line.startswith("HELIX ") and len(line) >= 40:
            helices.append(
                {
                    "record": "HELIX",
                    "helix_id": line[11:14].strip(),
                    "chain_id": line[19].strip(),
                    "start_resseq": _int_field(line[21:25]),
                    "start_icode": line[25].strip(),
                    "end_resseq": _int_field(line[33:37]),
                    "end_icode": line[37].strip(),
                    "helix_class": _int_field(line[38:40]),
                }
            )
        elif line.startswith("SHEET ") and len(line) >= 38:
            sheets.append(
                {
                    "record": "SHEET",
                    "sheet_id": line[11:14].strip(),
                    "chain_id": line[21].strip(),
                    "start_resseq": _int_field(line[22:26]),
                    "start_icode": line[26].strip(),
                    "end_resseq": _int_field(line[33:37]),
                    "end_icode": line[37].strip(),
                }
            )
    return {"helices": helices, "sheets": sheets}


def _mmcif(path: Path) -> dict[str, list[dict[str, Any]]]:
    table = MMCIF2Dict(str(path))
    helices: list[dict[str, Any]] = []
    starts = _column(table, "_struct_conf.beg_auth_seq_id")
    ends = _column(table, "_struct_conf.end_auth_seq_id")
    chains = _column(table, "_struct_conf.beg_auth_asym_id")
    classes = _column(table, "_struct_conf.pdbx_PDB_helix_class")
    helix_ids = _column(table, "_struct_conf.pdbx_PDB_helix_id")
    for index, start in enumerate(starts):
        helices.append(
            {
                "record": "_struct_conf",
                "helix_id": helix_ids[index] if index < len(helix_ids) else "",
                "chain_id": chains[index] if index < len(chains) else "",
                "start_resseq": _int_or_none(start),
                "start_icode": "",
                "end_resseq": _int_or_none(ends[index]) if index < len(ends) else None,
                "end_icode": "",
                "helix_class": _int_or_none(classes[index]) if index < len(classes) else None,
            }
        )
    sheets: list[dict[str, Any]] = []
    sheet_starts = _column(table, "_struct_sheet_range.beg_auth_seq_id")
    sheet_ends = _column(table, "_struct_sheet_range.end_auth_seq_id")
    sheet_chains = _column(table, "_struct_sheet_range.beg_auth_asym_id")
    sheet_ids = _column(table, "_struct_sheet_range.sheet_id")
    for index, start in enumerate(sheet_starts):
        sheets.append(
            {
                "record": "_struct_sheet_range",
                "sheet_id": sheet_ids[index] if index < len(sheet_ids) else "",
                "chain_id": sheet_chains[index] if index < len(sheet_chains) else "",
                "start_resseq": _int_or_none(start),
                "start_icode": "",
                "end_resseq": _int_or_none(sheet_ends[index]) if index < len(sheet_ends) else None,
                "end_icode": "",
            }
        )
    return {"helices": helices, "sheets": sheets}


def residue_in_ranges(chain_id: str, resseq: int, icode: str, ranges: list[dict[str, Any]]) -> bool:
    """True when the residue number falls inside an inclusive author range on the same chain."""

    for item in ranges:
        if item.get("chain_id") != chain_id:
            continue
        start = item.get("start_resseq")
        end = item.get("end_resseq")
        if start is None or end is None:
            continue
        if icode not in {"", item.get("start_icode") or "", item.get("end_icode") or ""} and icode != "":
            # Insertion-code ranges are only matched when both ends are blank or equal the residue.
            if (item.get("start_icode") or "") not in {"", icode} or (item.get("end_icode") or "") not in {"", icode}:
                continue
        if start <= resseq <= end:
            return True
    return False


def _column(table: dict, key: str) -> list[str]:
    raw = table.get(key)
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(item) for item in raw]
    return [str(raw)]


def _int_field(text: str) -> int | None:
    stripped = text.strip()
    if not stripped:
        return None
    try:
        return int(stripped)
    except ValueError:
        return None


def _int_or_none(text: str) -> int | None:
    if text in {"", ".", "?"}:
        return None
    try:
        return int(text)
    except ValueError:
        return None
