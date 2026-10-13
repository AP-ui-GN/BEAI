# Handoff

Date: 2026-10-13. Session 6B protein embeddings are on `m6b-embeddings`, branched from `m6a-registry`. Sessions 6C–6F have not started.

## Current state

Alembic head is `0007_embeddings`. With `BEAI_REGISTER_BUILTINS` left at its default, startup inserts the ESM-2 8M registry row and does not load weights. The checkpoint on this machine is `models/esm2_t6_8M_UR50D/model.safetensors` (sha256 `24c5fa474c48f3b754b86efe752d5f189d2bcd88190fa2270fc92b2ef3034189`). Embeddings are mean-pooled residue states, origin `ml_prediction`, label "not experimental". Sequences over 1026 tokens, including special tokens, are refused and not truncated. Neighbours are cosine similarity of stored vectors.

API: `http://127.0.0.1:8731`. App: `http://127.0.0.1:8732`.

## Verified

- `.venv/bin/python -m pytest` — 94 passed, 2 deselected (`network` and `model`), 0 failed.
- `.venv/bin/python -m pytest --override-ini addopts= -m model backend/tests/test_embeddings_model.py` — 1 passed. Spearman 0.6990131578947367, interval 0.3788637829986782 to 0.8820213682475236, 28 pairs, seed 20261013, 1000 resamples.
- `npm --prefix frontend test` — 9 passed, 0 failed.
- `npm --prefix frontend run build` — completed.
- A pre-registered ESM row stayed unloaded across startup. The loader was not called.

## Broken or incomplete

- No solubility model, OpenMM simulation, generation, or workflow runner.
- OpenMM and fpocket are not installed.
- The Milestone 4 5–10 complex heavy-atom RMSD table was not run.
- Open Targets, DailyMed, and Europe PMC were not built.
- Playwright was not re-run.
- The embedding correlation is a small curated set. It is not a functional or structural result.

## Decisions

- CPU torch 2.9.1+cpu from `https://download.pytorch.org/whl/cpu`, not the PyPI CUDA wheel. Transformers 5.19.0.
- The loader is `EsmForMaskedLM`. The masked-language-model head is not used. A random pooler from `EsmModel` is not used.
- J maps to `<unk>` in this vocab, so the embedding is refused instead of stored.
- Plumbing tests use a 20-d amino-acid composition stub. That stub is not ESM-2.

## Next task

Session 6C, property prediction, from this branch. Use a public solubility set with a recorded checksum and licence, save a scaffold split before training, and report a descriptor or fingerprint baseline beside any neural model. Predictions stay `ml_prediction` and are labelled not experimental.

## UI controls

- Model Laboratory: hardware, registry rows, load, unload, and download when `can_download` is true. Embed is offered for a ready or loaded model and lists stored sequences. Empty sequence copy is shown when none are stored. Results show the API label and origin.
- Earlier protein, compound, discovery, and safety controls remain.
- Simulation Center is still a planned page.
