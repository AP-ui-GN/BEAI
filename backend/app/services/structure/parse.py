"""Open a structure with Biopython and collect the summary stored at upload time."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from Bio.PDB import MMCIFParser, PDBParser
from Bio.PDB.MMCIF2Dict import MMCIF2Dict

from backend.app.core.errors import InvalidInput

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParseSummary:
    model_count: int
    chain_ids: list[str]
    title: str | None
    coordinate_record_count: int


def parse_structure_file(
    path: Path,
    structure_format: str,
    coordinate_records: int,
) -> ParseSummary:
    """Parse ``path``. Failures become ``InvalidInput`` without the filesystem path."""

    try:
        if structure_format == "pdb":
            structure = PDBParser(QUIET=True).get_structure("upload", str(path))
            title = _pdb_title(path)
        elif structure_format == "mmcif":
            structure = MMCIFParser(QUIET=True).get_structure("upload", str(path))
            title = _mmcif_title(path)
        else:
            raise InvalidInput(f"Unsupported structure format: {structure_format}")
        models = list(structure.get_models())
        atom_count = sum(1 for _ in structure.get_atoms())
    except InvalidInput:
        raise
    except Exception:
        logger.info("structure parse failed", exc_info=True)
        raise InvalidInput("The file could not be parsed as a PDB or mmCIF structure.") from None
    if not models or atom_count == 0:
        raise InvalidInput("The file did not contain any coordinates that could be read.")
    chain_ids = [chain.id.strip() for chain in models[0].get_chains() if chain.id.strip()]
    return ParseSummary(
        model_count=len(models),
        chain_ids=chain_ids,
        title=title,
        coordinate_record_count=max(coordinate_records, atom_count),
    )


def _pdb_title(path: Path) -> str | None:
    parts: list[str] = []
    for line in path.read_text(encoding="latin-1").splitlines():
        if line.startswith("TITLE"):
            parts.append(line[10:80].strip())
    title = " ".join(part for part in parts if part)
    return title or None


def _mmcif_title(path: Path) -> str | None:
    try:
        table = MMCIF2Dict(str(path))
    except Exception:
        logger.info("mmCIF header read failed", exc_info=True)
        return None
    raw = table.get("_struct.title")
    if raw is None:
        return None
    if isinstance(raw, list):
        text = " ".join(str(item) for item in raw if str(item) not in {"?", "."})
    else:
        text = str(raw)
    text = " ".join(text.split())
    if text in {"", "?", "."}:
        return None
    return text
