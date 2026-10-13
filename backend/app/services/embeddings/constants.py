"""Facts copied from the ESM-2 8M model card on 2026-10-13.

Licence and ``max_position_embeddings`` were read before the weight file was
used. The safetensors sha256 is the Hub LFS oid, checked against the file
after download. Sidecar sha256 values are the hashes of the files retrieved
the same day. ``tokenizer_config.json`` ``model_max_length`` is about 1e30 and
is not used as a limit.
"""

from __future__ import annotations

SOURCE_URL = "https://huggingface.co/facebook/esm2_t6_8M_UR50D"
HUB_COMMIT = "c731040fcd8d73dceaa04b0a8e6329b345b0f5df"
LICENCE = "MIT"
# config.json max_position_embeddings, retrieved 2026-10-13.
TOKEN_LIMIT = 1026
# Declared floor so a machine without this much free RAM is refused. Not a measured footprint.
MIN_RAM_BYTES = 512 * 1024 * 1024
WEIGHTS_RELATIVE = "esm2_t6_8M_UR50D/model.safetensors"
NOT_EXPERIMENTAL = "not experimental"

# sha256 of each file that from_pretrained needs. The weight hash was known from the Hub before use.
FILE_SHA256 = {
    "config.json": "facb9355e8252149f6f99dff5fd1e32e890c3c655362b261d0c81cd6b5839c85",
    "tokenizer_config.json": "7e9161ecdb548ec45a41cbc6b24aa4476fdd418461f491c4207baa99419a29ad",
    "special_tokens_map.json": "3aedcd4211c0d43aec4e607ff60a63255f3174ead795e997350f09a5f8cd9ee1",
    "vocab.txt": "0b82cc0a7c7cf9e567b1e5892d793285b9fbae822c964ca48696f7db44598e03",
    "model.safetensors": "24c5fa474c48f3b754b86efe752d5f189d2bcd88190fa2270fc92b2ef3034189",
}

POOLING = (
    "Mean of the last hidden state over residue tokens from EsmForMaskedLM. "
    "The first token (<cls>) and the last token (<eos>) are excluded. "
    "The masked-language-model head is not used."
)
