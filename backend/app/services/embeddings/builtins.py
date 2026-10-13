"""Insert the ESM-2 registry row. This does not download or load weights."""

from __future__ import annotations

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from backend.app.services.embeddings.constants import (
    FILE_SHA256,
    HUB_COMMIT,
    LICENCE,
    MIN_RAM_BYTES,
    SOURCE_URL,
    TOKEN_LIMIT,
    WEIGHTS_RELATIVE,
)
from backend.app.services.models_registry.registry import register_model

KNOWN_LIMITATIONS = (
    "MIT licence from the model card README field license: mit, retrieved 2026-10-13 from "
    f"{SOURCE_URL}. config.json max_position_embeddings is {TOKEN_LIMIT}. "
    "tokenizer_config.json model_max_length is about 1e30 and is not used. "
    f"A sequence is refused when the tokenizer output, including special tokens, exceeds {TOKEN_LIMIT}. "
    "It is not truncated. The embedding is the mean of the last hidden state over residue tokens. "
    "It is not an experimental measurement and it supports no functional or structural claim. "
    "The masked-language-model head is not used. "
    f"The declared RAM floor is {MIN_RAM_BYTES} bytes. That number is not a measured footprint."
)


def esm_payload() -> dict:
    return {
        "name": "esm2_t6_8M_UR50D",
        "version": HUB_COMMIT,
        "task": "protein sequence embedding",
        "source_url": SOURCE_URL,
        "licence": LICENCE,
        "dependencies": [
            {"kind": "python", "name": "torch"},
            {"kind": "python", "name": "transformers"},
        ],
        "hardware": {"min_ram_bytes": MIN_RAM_BYTES, "device": "cpu"},
        "input_format": "amino-acid sequence",
        "output_format": "mean-pooled last hidden state, special tokens excluded",
        "benchmark": {
            "dataset": (
                "SEQRES chains selected by backend/app/services/embeddings/benchmark.py from "
                "1UBQ, 4HHB, 3PTB, 1STP, 2GBP, and 1HSG"
            ),
            "metric": "Spearman correlation of embedding cosine similarity with identity_including_gaps",
            "identity": "Biopython PairwiseAligner global BLOSUM62, open -10, extend -1",
            "pairs": 28,
            "sequences": 8,
            "spearman": 0.6990131578947367,
            "interval_low": 0.3788637829986782,
            "interval_high": 0.8820213682475236,
            "bootstrap_seed": 20261013,
            "bootstrap_resamples": 1000,
            "interval": "2.5 and 97.5 percentiles of finite resamples",
            "finite_resamples": 1000,
            "run_on": "2026-10-13",
            "command": (
                ".venv/bin/python -m pytest --override-ini addopts= -m model "
                "backend/tests/test_embeddings_model.py"
            ),
            "claim": "No functional or structural claim. Rank agreement with sequence identity on this small set only.",
        },
        "known_limitations": KNOWN_LIMITATIONS,
        "checksum_sha256": FILE_SHA256["model.safetensors"],
        "weights_relative": WEIGHTS_RELATIVE,
        "loader_key": "esm2_8m",
        "token_limit": TOKEN_LIMIT,
    }


def sync_builtin_models(session: Session) -> None:
    """Insert the ESM-2 row once. Missing tables are ignored so an unmigrated database still starts."""

    bind = session.get_bind()
    if not inspect(bind).has_table("registered_models"):
        return
    from backend.app.db.models import RegisteredModel

    existing = session.scalar(
        select(RegisteredModel).where(
            RegisteredModel.name == "esm2_t6_8M_UR50D",
            RegisteredModel.version == HUB_COMMIT,
        )
    )
    if existing is not None:
        return
    register_model(session, esm_payload())
