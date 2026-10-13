"""Rank correlation between embedding cosine and alignment identity.

The curated files and the bootstrap settings were chosen before the ESM-2
numbers were computed. Identity is ``identity_including_gaps`` from the
existing global BLOSUM62 alignment. One or two polymer chains are taken from
each file when the one-letter sequence is at least 20 residues, at most the
model token limit minus two special tokens, and contains no X.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.app.services.embeddings.vectors import cosine, spearman_with_bootstrap
from backend.app.services.sequence.align import align_sequences
from backend.app.services.structure.ccd import component_table
from backend.app.services.structure.header import read_sequences

CURATED_FILES = (
    "1UBQ.pdb",
    "4HHB.pdb",
    "pockets/3PTB.pdb",
    "pockets/1STP.pdb",
    "pockets/2GBP.pdb",
    "pockets/1HSG.pdb",
)
MAX_CHAINS_PER_FILE = 2
MIN_LENGTH = 20


def curated_sequences(fixtures: Path, token_limit: int) -> list[dict[str, str]]:
    """Read SEQRES one-letter sequences. The selection rule is fixed above."""

    table = component_table()
    residue_budget = token_limit - 2
    chosen: list[dict[str, str]] = []
    for relative in CURATED_FILES:
        path = fixtures / relative
        chains = read_sequences(path, "pdb")
        kept = 0
        for chain in chains:
            letters: list[str] = []
            skipped = False
            for name in chain.residue_names:
                component = table.get(name)
                letter = component.one_letter if component and component.one_letter else "X"
                if letter == "X":
                    skipped = True
                    break
                letters.append(letter)
            sequence = "".join(letters)
            if skipped or len(sequence) < MIN_LENGTH or len(sequence) > residue_budget:
                continue
            chosen.append(
                {
                    "source": relative,
                    "chain_id": chain.chain_id,
                    "sequence": sequence,
                }
            )
            kept += 1
            if kept >= MAX_CHAINS_PER_FILE:
                break
    return chosen


def rank_correlation(sequences: list[dict[str, str]], embed) -> dict[str, Any]:
    """Compare embedding cosine with alignment identity on every unordered pair."""

    vectors = [embed(item["sequence"]) for item in sequences]
    cosines: list[float] = []
    identities: list[float] = []
    pairs: list[dict[str, Any]] = []
    for left in range(len(sequences)):
        for right in range(left + 1, len(sequences)):
            similarity = cosine(vectors[left], vectors[right])
            aligned = align_sequences(
                sequences[left]["sequence"],
                sequences[right]["sequence"],
                left_id=f"{sequences[left]['source']}:{sequences[left]['chain_id']}",
                right_id=f"{sequences[right]['source']}:{sequences[right]['chain_id']}",
                left_sha256="curated",
                right_sha256="curated",
            )
            identity = next(
                item["value"] for item in aligned["measurements"] if item["name"] == "identity_including_gaps"
            )
            if similarity is None or identity is None:
                continue
            cosines.append(float(similarity))
            identities.append(float(identity))
            pairs.append(
                {
                    "left": f"{sequences[left]['source']}:{sequences[left]['chain_id']}",
                    "right": f"{sequences[right]['source']}:{sequences[right]['chain_id']}",
                    "cosine": float(similarity),
                    "identity_including_gaps": float(identity),
                }
            )
    summary = spearman_with_bootstrap(cosines, identities)
    summary["sequences"] = [
        {"source": item["source"], "chain_id": item["chain_id"], "length": len(item["sequence"])} for item in sequences
    ]
    summary["pairs"] = pairs
    return summary
