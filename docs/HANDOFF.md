# Handoff

Date: 2026-10-13. Session 6A model registry is on `m6a-registry`, branched from `m5-safety`. Sessions 6B–6F have not started.

## Current state

`registered_models` is Alembic revision `0006_models`. `GET /api/models` lists registry rows and a psutil RAM report. CUDA and MPS are reported only when PyTorch is installed and answers; on this machine both say PyTorch is not installed, so they were not queried. Load and unload touch a process-local runtime. Startup does not call a loader. The only loader key is `registry_only`. It does not execute weights. The Model Laboratory at `/models` renders the API payload, including an empty list when nothing is registered.

API: `http://127.0.0.1:8731`. App: `http://127.0.0.1:8732`.

## Verified

- `.venv/bin/python -m pytest` — 88 passed, 1 deselected (`network`), 0 failed.
- `npm --prefix frontend test` — 9 passed, 0 failed.
- `npm --prefix frontend run build` — completed.
- A registry row inserted before process start stayed unloaded, and the loader function was not called.
- A model depending on a missing Python module returned HTTP 503 on load. `GET /api/health` stayed 200.
- A declared minimum RAM above the machine total returned HTTP 422 and was not marked loaded.

## Broken or incomplete

- No embedding, property, simulation, generation, or workflow code.
- PyTorch, OpenMM, and fpocket are not installed. No weight file is in `models/`.
- The Milestone 4 5–10 complex heavy-atom RMSD table was not run.
- Open Targets, DailyMed, and Europe PMC were not built.
- Playwright was not re-run.

## Decisions

- psutil 7.2.2 (BSD-3-Clause, wheel about 155 kB) reports RAM. It is a direct dependency because the registry has to read the machine.
- Hardware refusal is HTTP 422. A missing dependency is HTTP 503. Those are different failures.
- `registry_only` may verify a sha256 under `models/` and still reports `weights_loaded: false`.
- Training status is read from `model_training` job rows. Session 6A does not create those jobs itself.

## Next task

Session 6B, protein embeddings, from this branch. Read the ESM-2 8M model card (`facebook/esm2_t6_8M_UR50D`) for the licence and token limit before any download. Keep weights under gitignored `models/`. Plumbing tests use a stub. The real checkpoint test is opt-in. Do not load the model at startup.

## UI controls

- Model Laboratory: shows hardware bytes, CUDA/MPS reasons, and each registered model. Load is disabled when the API status is `disabled` or `incompatible`, with the reason visible. Unload is enabled only after a successful load. Empty registry copy is shown when the list is empty.
- Protein, compound, discovery, and safety controls from earlier milestones remain.
- Simulation Center is still a planned page.
