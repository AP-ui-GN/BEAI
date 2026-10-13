# esm2_t6_8M_UR50D

Retrieved 2026-10-13 from https://huggingface.co/facebook/esm2_t6_8M_UR50D.

- Licence: MIT (`license: mit` on the model card, Hub tag `license:mit`).
- Hub commit observed on the weight URL: `c731040fcd8d73dceaa04b0a8e6329b345b0f5df`.
- `config.json` `max_position_embeddings`: 1026.
- `tokenizer_config.json` `model_max_length` is about 1e30 and is not used.
- Weight file: `model.safetensors`, 31384292 bytes, sha256 `24c5fa474c48f3b754b86efe752d5f189d2bcd88190fa2270fc92b2ef3034189` (Hub LFS oid, checked after download).
- `pytorch_model.bin` was not downloaded. The loader uses `EsmForMaskedLM` and does not use the masked-language-model head.
- Pooling: mean of the last hidden state over residue tokens. `<cls>` and `<eos>` are excluded.
- Sequences whose tokenizer length, including special tokens, exceeds 1026 are refused. They are not truncated.
- A letter the tokenizer maps to `<unk>` (J is not in `vocab.txt`) stores no embedding.
- Declared RAM floor: 536870912 bytes. That is not a measured footprint.
- Output label: not experimental. Origin: `ml_prediction`. No functional or structural claim.

The checkpoint stays under gitignored `models/esm2_t6_8M_UR50D/`. It is not loaded at startup.
