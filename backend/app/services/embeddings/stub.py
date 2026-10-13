"""Amino-acid composition stand-in. This is not ESM-2 and not a learned model.

The vector is length 20, one axis per letter in ``ACDEFGHIKLMNPQRSTVWY``,
in that order. Each value is the count of that letter divided by the count of
those letters. Other letters are ignored in the denominator. The token count
used for the limit is the sequence length, with no special tokens.
"""

from __future__ import annotations

from typing import Any

from backend.app.core.errors import InvalidInput
from backend.app.db.models import RegisteredModel

AMINO_ACIDS = "ACDEFGHIKLMNPQRSTVWY"


def composition_vector(sequence: str) -> list[float]:
    """Return the 20-d composition. An independent implementation can copy this definition."""

    counts = [sequence.count(letter) for letter in AMINO_ACIDS]
    total = sum(counts)
    if total == 0:
        raise InvalidInput("The sequence has none of the 20 standard amino acids.")
    return [count / total for count in counts]


def load_stub(row: RegisteredModel) -> dict[str, Any]:
    """Return an in-memory embedder. No weight file is read."""

    limit = row.token_limit

    def embed(sequence: str) -> list[float]:
        token_count = len(sequence)
        if limit is not None and token_count > limit:
            raise InvalidInput(
                f"Token count {token_count} exceeds the model token limit {limit}. "
                "The sequence was not truncated and no embedding was stored."
            )
        return composition_vector(sequence)

    return {
        "weights_loaded": False,
        "embed": embed,
        "note": "This is a 20-dimensional amino-acid composition vector, not ESM-2 and not a learned model.",
        "pooling": "amino-acid composition, counts divided by the number of standard residues",
    }
