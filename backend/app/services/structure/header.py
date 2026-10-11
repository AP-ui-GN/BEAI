"""Author-reported header fields and declared sequences.

Experimental metadata is copied from the file. It is not re-derived. A missing
number stays null. The Biopython sentinel date 1909-01-08 and the sentinel
method ``unknown`` are not reported as measurements.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from Bio.PDB.MMCIF2Dict import MMCIF2Dict

_MONTHS = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}
_DATE_TOKEN = re.compile(r"\d{2}-[A-Za-z]{3}-\d{2}")
_RESOLUTION = re.compile(
    r"REMARK\s+2\s+RESOLUTION\.\s+([0-9]*\.?[0-9]+)\s+ANGSTROM",
    re.IGNORECASE,
)
_FREE_R = re.compile(r"FREE R VALUE\s*:\s*(\S+)", re.IGNORECASE)


@dataclass
class AuthorMetadata:
    title: str | None = None
    experimental_method: str | None = None
    resolution_angstrom: float | None = None
    r_free: float | None = None
    deposition_date: str | None = None
    title_source: str = ""
    method_source: str = ""
    resolution_source: str = ""
    r_free_source: str = ""
    deposition_source: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass
class ChainSequence:
    chain_id: str
    residue_names: list[str]
    declared_count: int | None
    source: str


def read_author_metadata(path: Path, structure_format: str) -> AuthorMetadata:
    if structure_format == "pdb":
        return _pdb_metadata(path.read_text(encoding="latin-1"))
    if structure_format == "mmcif":
        return _mmcif_metadata(path)
    raise ValueError(f"unsupported format {structure_format}")


def read_sequences(path: Path, structure_format: str) -> list[ChainSequence]:
    if structure_format == "pdb":
        return _pdb_sequences(path.read_text(encoding="latin-1"))
    if structure_format == "mmcif":
        return _mmcif_sequences(path)
    raise ValueError(f"unsupported format {structure_format}")


def read_missing_residues_pdb(header: dict) -> tuple[list[dict], list[str]]:
    """Map Biopython's REMARK 465 parse into plain records.

    Biopython's keys are model, res_name, chain, ssseq, and insertion.
    """

    warnings: list[str] = []
    rows = header.get("missing_residues") or []
    records: list[dict] = []
    for row in rows:
        if not isinstance(row, dict) or "res_name" not in row or "chain" not in row:
            continue
        insertion = row.get("insertion") or ""
        if insertion == " ":
            insertion = ""
        resseq = row.get("ssseq")
        if not isinstance(resseq, int):
            warnings.append("A REMARK 465 row was skipped because the residue number was not an integer.")
            continue
        records.append(
            {
                "chain_id": str(row.get("chain") or "").strip(),
                "resname": str(row["res_name"]).strip().upper(),
                "resseq": resseq,
                "icode": str(insertion).strip(),
                "model": row.get("model"),
                "source": "REMARK 465",
                "reason": "unobserved",
            }
        )
    if header.get("has_missing_residues") and not records:
        warnings.append("REMARK 465 is present, but no residue rows could be parsed.")
    return records, warnings


def read_missing_residues_mmcif(path: Path) -> tuple[list[dict], list[str]]:
    """Read ``_pdbx_unobs_or_zero_occ_residues`` when the category is present.

    occupancy_flag 1 means unobserved and 0 means zero occupancy, from the
    PDBx item description read on 2026-10-11.
    """

    warnings: list[str] = []
    try:
        table = MMCIF2Dict(str(path))
    except Exception:
        warnings.append("The mmCIF header could not be read for unobserved residues.")
        return [], warnings
    chains = _column(table, "_pdbx_unobs_or_zero_occ_residues.auth_asym_id")
    if not chains:
        return [], warnings
    names = _column(table, "_pdbx_unobs_or_zero_occ_residues.auth_comp_id")
    seqs = _column(table, "_pdbx_unobs_or_zero_occ_residues.auth_seq_id")
    icodes = _column(table, "_pdbx_unobs_or_zero_occ_residues.PDB_ins_code")
    models = _column(table, "_pdbx_unobs_or_zero_occ_residues.PDB_model_num")
    flags = _column(table, "_pdbx_unobs_or_zero_occ_residues.occupancy_flag")
    polymers = _column(table, "_pdbx_unobs_or_zero_occ_residues.polymer_flag")
    records: list[dict] = []
    for index, chain in enumerate(chains):
        resseq_text = _at(seqs, index)
        try:
            resseq = int(resseq_text)
        except ValueError:
            warnings.append("An unobserved-residue row was skipped because the sequence number was not an integer.")
            continue
        flag = _at(flags, index)
        if flag == "1":
            reason = "unobserved"
        elif flag == "0":
            reason = "zero_occupancy"
        else:
            reason = "unparsed_occupancy_flag"
            warnings.append(f"Unobserved-residue occupancy_flag {flag!r} is not 0 or 1.")
        model_text = _at(models, index)
        model: int | None
        try:
            model = int(model_text) if model_text not in {"", ".", "?"} else None
        except ValueError:
            model = None
        records.append(
            {
                "chain_id": chain.strip(),
                "resname": _at(names, index).upper(),
                "resseq": resseq,
                "icode": _blank_token(_at(icodes, index)),
                "model": model,
                "polymer_flag": _at(polymers, index) or None,
                "source": "_pdbx_unobs_or_zero_occ_residues",
                "reason": reason,
            }
        )
    return records, warnings


def _pdb_metadata(text: str) -> AuthorMetadata:
    meta = AuthorMetadata(
        title_source="PDB TITLE records",
        method_source="PDB EXPDTA records",
        resolution_source="PDB REMARK 2",
        r_free_source="PDB REMARK 3 FREE R VALUE",
        deposition_source="PDB HEADER date",
    )
    titles: list[str] = []
    methods: list[str] = []
    deposition: str | None = None
    resolution: float | None = None
    saw_resolution = False
    r_free: float | None = None
    saw_free_r = False
    free_r_null = False
    for line in text.splitlines():
        if line.startswith("TITLE"):
            titles.append(line[10:80].strip())
        elif line.startswith("EXPDTA"):
            methods.append(line[10:80].strip())
        elif line.startswith("HEADER") and deposition is None:
            match = _DATE_TOKEN.search(line)
            if match:
                deposition = _pdb_date(match.group(0))
        elif line.startswith("REMARK") and "RESOLUTION." in line and "REMARK   2" in line[:12]:
            saw_resolution = True
            match = _RESOLUTION.search(line)
            if match:
                resolution = float(match.group(1))
        elif line.startswith("REMARK   3") and _is_primary_free_r(line):
            saw_free_r = True
            match = _FREE_R.search(line[10:])
            if match:
                token = match.group(1).upper().rstrip(".,")
                if token in {"NULL", "?", ".", "NONE"}:
                    free_r_null = True
                else:
                    try:
                        r_free = float(token)
                    except ValueError:
                        meta.warnings.append(f"Author FREE R VALUE {token!r} is not a number.")
    meta.title = _join(titles)
    meta.experimental_method = _join(methods)
    meta.resolution_angstrom = resolution
    meta.r_free = r_free
    meta.deposition_date = deposition
    if meta.title is None:
        meta.warnings.append("The file has no TITLE record.")
    if meta.experimental_method is None:
        meta.warnings.append("The file has no EXPDTA record.")
    if meta.deposition_date is None:
        meta.warnings.append("The file HEADER has no deposition date.")
    if resolution is None:
        if saw_resolution:
            meta.warnings.append("REMARK 2 is present, but no resolution in angstroms was parsed.")
        else:
            meta.warnings.append("The file has no REMARK 2 resolution.")
    if r_free is None:
        if free_r_null:
            meta.warnings.append("Author REMARK 3 FREE R VALUE is NULL.")
        elif saw_free_r:
            meta.warnings.append("Author REMARK 3 FREE R VALUE was present but not a number.")
        else:
            meta.warnings.append("The file has no REMARK 3 FREE R VALUE.")
    return meta


def _mmcif_metadata(path: Path) -> AuthorMetadata:
    meta = AuthorMetadata(
        title_source="mmCIF _struct.title",
        method_source="mmCIF _exptl.method",
        resolution_source="mmCIF _refine.ls_d_res_high",
        r_free_source="mmCIF _refine.ls_R_factor_R_free",
        deposition_source="mmCIF _pdbx_database_status.recvd_initial_deposition_date",
    )
    try:
        table = MMCIF2Dict(str(path))
    except Exception:
        meta.warnings.append("The mmCIF header could not be read.")
        return meta
    meta.title = _first_text(table.get("_struct.title"))
    meta.experimental_method = _first_text(table.get("_exptl.method"))
    meta.resolution_angstrom = _first_float(table.get("_refine.ls_d_res_high"))
    r_free_present = "_refine.ls_R_factor_R_free" in table
    r_free_token = _first_raw(table.get("_refine.ls_R_factor_R_free"))
    meta.r_free = _float_or_none(r_free_token)
    deposited = _first_raw(table.get("_pdbx_database_status.recvd_initial_deposition_date"))
    if deposited and len(deposited) >= 10 and deposited[4] == "-" and deposited[7] == "-":
        meta.deposition_date = deposited[:10]
    if meta.title is None:
        meta.warnings.append("The mmCIF file has no _struct.title.")
    if meta.experimental_method is None:
        meta.warnings.append("The mmCIF file has no _exptl.method.")
    if meta.resolution_angstrom is None:
        meta.warnings.append("The mmCIF file has no numeric _refine.ls_d_res_high.")
    if meta.deposition_date is None:
        meta.warnings.append("The mmCIF file has no initial deposition date.")
    if meta.r_free is None:
        if not r_free_present:
            meta.warnings.append("The mmCIF file has no _refine.ls_R_factor_R_free.")
        elif r_free_token is None:
            meta.warnings.append("Author mmCIF R-free is recorded as missing.")
        else:
            meta.warnings.append(f"Author mmCIF R-free value {r_free_token!r} is not a number.")
    return meta


def _pdb_sequences(text: str) -> list[ChainSequence]:
    names: dict[str, list[str]] = {}
    declared: dict[str, int] = {}
    order: list[str] = []
    for line in text.splitlines():
        if not line.startswith("SEQRES") or len(line) < 18:
            continue
        chain = line[11].strip()
        if not chain:
            continue
        if chain not in names:
            order.append(chain)
            names[chain] = []
        try:
            declared[chain] = int(line[13:17])
        except ValueError:
            declared.setdefault(chain, -1)
        names[chain].extend(token.upper() for token in line[19:].split())
    sequences: list[ChainSequence] = []
    for chain in order:
        count = declared.get(chain)
        sequences.append(
            ChainSequence(
                chain_id=chain,
                residue_names=names[chain],
                declared_count=count if count is not None and count >= 0 else None,
                source="PDB SEQRES",
            )
        )
    return sequences


def _mmcif_sequences(path: Path) -> list[ChainSequence]:
    table = MMCIF2Dict(str(path))
    strands = _column(table, "_pdbx_poly_seq_scheme.pdb_strand_id")
    monomers = _column(table, "_pdbx_poly_seq_scheme.mon_id")
    if strands and monomers:
        grouped: dict[str, list[str]] = {}
        order: list[str] = []
        for strand, monomer in zip(strands, monomers, strict=False):
            chain = strand.strip()
            if chain in {"", ".", "?"}:
                continue
            if chain not in grouped:
                order.append(chain)
                grouped[chain] = []
            grouped[chain].append(monomer.strip().upper())
        return [
            ChainSequence(chain, grouped[chain], len(grouped[chain]), "mmCIF _pdbx_poly_seq_scheme.mon_id")
            for chain in order
        ]
    entity_names = _column(table, "_entity_poly_seq.mon_id")
    entity_strands = _first_raw(table.get("_entity_poly.pdbx_strand_id"))
    if not entity_names or not entity_strands:
        return []
    residues = [name.strip().upper() for name in entity_names]
    sequences: list[ChainSequence] = []
    for chain in entity_strands.replace(" ", "").split(","):
        if chain:
            sequences.append(ChainSequence(chain, list(residues), len(residues), "mmCIF _entity_poly_seq.mon_id"))
    return sequences


def _pdb_date(token: str) -> str | None:
    """Convert ``DD-Mon-YY`` using the PDB two-digit window (00–49 → 2000, else 1900)."""

    try:
        day = int(token[0:2])
        month = _MONTHS[token[3:6].upper()]
        year_two = int(token[7:9])
    except (KeyError, ValueError):
        return None
    year = (2000 if year_two < 50 else 1900) + year_two
    if not 1 <= day <= 31:
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"


def _is_primary_free_r(line: str) -> bool:
    body = line[10:].strip().upper()
    if not body.startswith("FREE R VALUE"):
        return False
    blocked = ("TEST", "BIN", "NO CUTOFF", "ERROR", "SIZE", "COUNT")
    return not any(token in body for token in blocked)


def _join(parts: list[str]) -> str | None:
    text = " ".join(part for part in parts if part)
    text = " ".join(text.split())
    return text or None


def _column(table: dict, key: str) -> list[str]:
    value = table.get(key)
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value]
    return [str(value).strip()]


def _at(values: list[str], index: int) -> str:
    if index >= len(values):
        return ""
    return values[index].strip()


def _blank_token(value: str) -> str:
    if value in {"", ".", "?"}:
        return ""
    return value


def _first_raw(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        if not value:
            return None
        value = value[0]
    text = str(value).strip()
    if text in {"", ".", "?"}:
        return None
    return text


def _first_text(value: object) -> str | None:
    raw = _first_raw(value)
    if raw is None:
        return None
    return " ".join(raw.split()) or None


def _first_float(value: object) -> float | None:
    return _float_or_none(_first_raw(value))


def _float_or_none(token: str | None) -> float | None:
    if token is None or token.upper() in {"NULL", "NONE", ".", "?"}:
        return None
    try:
        return float(token)
    except ValueError:
        return None
