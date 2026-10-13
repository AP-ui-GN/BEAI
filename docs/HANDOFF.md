# Handoff

Date: 2026-10-13. Session 6E molecular generation is on `m6e-generation`, branched from `m6d-simulation`. Session 6F has not started.

## Current state

`POST /api/generation` recombines reference molecules with RDKit BRICS. PAINS, Brenk, and NIH filters always run. A request that turns them off, or that mentions toxicity or hazard, is rejected and stores nothing. Displayed SMILES are sanitized and labelled "computational hypothesis: unsynthesized, unvalidated". The Drug Discovery page shows the three filters as checked controls that cannot be cleared.

API: `http://127.0.0.1:8731`. App: `http://127.0.0.1:8732`. Alembic head is still `0007_embeddings`.

## Verified

- `.venv/bin/python -m pytest` — 105 passed, 3 deselected (`network` and `model`), 0 failed.
- `npm --prefix frontend run build` — completed.
- Generated SMILES in the test sanitized, and each output carried the hypothesis label.

## Broken or incomplete

- Checkpoint resume for simulations is not implemented.
- NVE drift and same-seed OpenMM energy are not inside the original tight bounds on every run.
- fpocket is absent. The Milestone 4 5–10 complex RMSD table was not run.
- Open Targets, DailyMed, and Europe PMC were not built.
- Workflows are not built.
- Playwright was not re-run. `npm --prefix frontend test` was not re-run after the generation form.

## Decisions

- Objectives are similarity to a reference or a MolWt, MolLogP, or TPSA range. Nothing else is accepted.
- Filter hits are stored and are not shown as hypotheses.
- The generator is RDKit BRICS, not a trained generative model.

## Next task

Session 6F, workflow orchestration, from this branch. A workflow is validated JSON. Steps that lack a capability are skipped with a reason, and so are steps that depend on them. LLM features stay off unless `BEAI_LLM_ENABLED` is set. No autonomous scientific conclusion.

## UI controls

- Drug Discovery: docking form when Vina and Meeko are available, plus fragment recombination with the three filters locked on.
- Simulation Center and Model Laboratory controls remain.
