"""Parse and validate protein FASTA text.

Allowed letters are the 20 standard amino acids plus the IUPAC ambiguity
codes B, Z, X, and J. Gap characters ``-`` and ``.`` are removed and counted.
A single terminal ``*`` is removed. Any other character rejects the upload
and nothing is stored.
"""

from __future__ import annotations

import hashlib
import re

from backend.app.core.errors import InvalidInput

STANDARD = frozenset("ACDEFGHIKLMNPQRSTVWY")
AMBIGUOUS = frozenset("BZXJ")
ALLOWED = STANDARD | AMBIGUOUS
_HEADER = re.compile(r"^>\s*(.*)$")


def parse_fasta(text: str) -> list[tuple[str, str]]:
    """Return ``(header, raw sequence)`` pairs. A headerless body is one record."""

    if "\x00" in text:
        raise InvalidInput("The sequence text is not valid FASTA.")
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    records: list[tuple[str, list[str]]] = []
    header: str | None = None
    chunks: list[str] = []
    saw_header = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(">"):
            saw_header = True
            if header is not None or chunks:
                records.append((header or "pasted", chunks))
            header = _HEADER.match(stripped).group(1).strip() if _HEADER.match(stripped) else stripped[1:].strip()
            header = header or "unlabelled"
            chunks = []
            continue
        if header is None and not chunks and saw_header:
            header = "unlabelled"
        chunks.append(stripped)
    if header is not None or chunks:
        records.append((header or "pasted", chunks))
    if not records:
        raise InvalidInput("No sequence text was provided.")
    return [(item_header[:500], "".join(item_chunks)) for item_header, item_chunks in records]


def validate_protein_sequence(raw: str) -> tuple[str, list[str]]:
    """Return the cleaned sequence and validation messages, or raise ``InvalidInput``."""

    messages: list[str] = []
    if raw != raw.upper():
        messages.append("Lowercase letters were converted to uppercase.")
    text = raw.upper()
    gap_count = text.count("-") + text.count(".")
    if gap_count:
        messages.append(f"{gap_count} gap characters were removed and are not part of the sequence.")
        text = text.replace("-", "").replace(".", "")
    text = "".join(text.split())
    if text.endswith("*"):
        messages.append("A terminal stop symbol was removed.")
        text = text[:-1]
    if "*" in text:
        raise InvalidInput("An internal stop symbol is not allowed.")
    if not text:
        raise InvalidInput("The sequence is empty after removing gaps and stops.")
    illegal = sorted({character for character in text if character not in ALLOWED})
    if illegal:
        shown = ", ".join(illegal[:12])
        raise InvalidInput(
            f"The sequence contains characters that are not the 20 standard amino acids "
            f"or the ambiguity codes B, Z, X, and J: {shown}."
        )
    if any(character in AMBIGUOUS for character in text):
        messages.append(
            "Ambiguity codes B, Z, X, or J are present. "
            "Molecular weight, isoelectric point, and GRAVY are not computed for ambiguous sequences."
        )
    return text, messages


def sequence_sha256(sequence: str) -> str:
    return hashlib.sha256(sequence.encode("utf-8")).hexdigest()
