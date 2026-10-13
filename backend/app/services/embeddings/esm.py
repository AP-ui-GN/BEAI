"""On-demand ESM-2 8M embeddings. Torch is imported inside ``load_esm`` only."""

from __future__ import annotations

from typing import Any

from backend.app.core.errors import CapabilityUnavailable, InvalidInput
from backend.app.db.models import RegisteredModel
from backend.app.services.embeddings.constants import FILE_SHA256, POOLING, SOURCE_URL, TOKEN_LIMIT
from backend.app.services.embeddings.download import verify_checkpoint
from backend.app.services.models_registry.runtime import resolve_weights_path


def load_esm(row: RegisteredModel) -> dict[str, Any]:
    """Load the local checkpoint after its checksums match. Does not download."""

    if row.source_url.rstrip("/") != SOURCE_URL:
        raise InvalidInput("This ESM-2 loader only accepts the facebook/esm2_t6_8M_UR50D source URL.")
    if not row.weights_relative:
        raise CapabilityUnavailable("The ESM-2 registry row has no weight path.")
    weight_path = resolve_weights_path(row.weights_relative)
    directory = weight_path.parent
    verify_checkpoint(directory)
    try:
        import torch
        from transformers import AutoTokenizer, EsmForMaskedLM
    except Exception as exc:
        raise CapabilityUnavailable(f"ESM-2 could not be imported ({exc.__class__.__name__}).") from exc

    tokenizer = AutoTokenizer.from_pretrained(directory)
    model = EsmForMaskedLM.from_pretrained(directory)
    model.eval()
    limit = int(row.token_limit or TOKEN_LIMIT)

    def embed(sequence: str) -> list[float]:
        batch = tokenizer(sequence, return_tensors="pt", add_special_tokens=True, truncation=False)
        token_ids = batch["input_ids"][0]
        token_count = int(token_ids.shape[0])
        if token_count > limit:
            raise InvalidInput(
                f"Token count {token_count} exceeds the model token limit {limit}. "
                "The sequence was not truncated and no embedding was stored."
            )
        unk_id = tokenizer.convert_tokens_to_ids("<unk>")
        if unk_id is not None and int((token_ids == unk_id).sum()) > 0:
            raise InvalidInput("The tokenizer mapped part of this sequence to <unk>. No embedding was stored.")
        with torch.no_grad():
            output = model(**batch, output_hidden_states=True)
        hidden = output.hidden_states[-1][0, 1:-1]
        if int(hidden.shape[0]) == 0:
            raise InvalidInput("No residue tokens remained after removing special tokens.")
        pooled = hidden.mean(dim=0)
        return [float(value) for value in pooled.tolist()]

    return {
        "weights_loaded": True,
        "embed": embed,
        "note": (
            "Weights were loaded from model.safetensors after the sha256 check. "
            f"{POOLING} This is not an experimental measurement."
        ),
        "pooling": POOLING,
        "checkpoint_sha256": FILE_SHA256["model.safetensors"],
    }
