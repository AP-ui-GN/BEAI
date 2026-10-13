# Handoff

Date: 2026-10-13. Session 6C solubility models are on `m6c-properties`, branched from `m6b-embeddings`. Sessions 6D–6F have not started.

## Current state

Alembic head is still `0007_embeddings`. The solubility registry row is inserted at startup with the other builtins and is not trained or loaded then. Training is `POST /api/models/{id}/train`. The artifact, when a job finishes, is gitignored `models/esol/`. Predictions from `POST /api/models/{id}/predict` are `ml_prediction`, labelled not experimental, and carry a Morgan Tanimoto applicability flag at 0.3. The descriptor Ridge, Morgan Ridge, and two-layer GCN are all returned. On the Delaney scaffold split the GCN R-squared is negative.

API: `http://127.0.0.1:8731`. App: `http://127.0.0.1:8732`.

## Verified

- `.venv/bin/python -m pytest` — 98 passed, 3 deselected (`network` twice and `model`), 0 failed.
- `npm --prefix frontend test` — 9 passed, 0 failed. `npm --prefix frontend run build` completed.
- `.venv/bin/python -m pytest --override-ini addopts= -m network backend/tests/test_solubility.py::test_esol_held_out_metrics` — 1 passed.
- Descriptor Ridge test RMSE 1.3217993772506413, Morgan Ridge 1.6696791869919676, GCN 2.5347372633569814. Bootstrap intervals are in `docs/SCIENTIFIC_VALIDATION.md`.

## Broken or incomplete

- OpenMM is not installed. Simulation Center is still a planned page.
- fpocket is absent. The Milestone 4 5–10 complex RMSD table was not run.
- Open Targets, DailyMed, and Europe PMC were not built.
- The Delaney CSV is not in git. A machine without `data/solubility/delaney-processed.csv` cannot train until that file is downloaded and matches the checksum.
- Playwright was not re-run.

## Decisions

- Ridge alpha, fingerprint size, GCN width, epochs, and learning rate were fixed before the test metrics. They were not searched.
- The GCN is reported even though it is worse than the descriptor baseline on this split.
- Artifacts are numpy and safetensors, not a pickle.
- The published ESOL prediction column is not a model input.

## Next task

Session 6D, OpenMM, from this branch. If OpenMM cannot be installed, simulation endpoints return 503 and the rest of the suite stays green. Do not invent a trajectory.

## UI controls

- Model Laboratory: train is shown for the solubility row. After `trained` is true, a SMILES form posts a prediction and shows origin badges, the not-experimental label, and the applicability flag from the API.
- Embedding controls from session 6B remain.
- Simulation Center is still planned.
