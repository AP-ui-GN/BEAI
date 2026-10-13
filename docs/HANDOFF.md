# Handoff

Date: 2026-10-13. Session 6F workflow orchestration is on `m6f-workflows`, branched from `m6e-generation`. Milestone 6 sessions 6A–6F are all on their own branches.

## Current state

`POST /api/workflows` validates a JSON workflow and runs `structure_overview`, `compound_descriptors`, or a docking step. A missing capability skips that step and every step that depends on it. `resume_from` skips steps that already succeeded. `POST /api/workflows/summarize` returns HTTP 503 unless `BEAI_LLM_ENABLED` is true. When it is on, a bracketed citation that is not in the retrieved id set is rejected. The summary is labelled `ml_generated`. The workflow result says it does not draw a scientific conclusion.

API: `http://127.0.0.1:8731`. App: `http://127.0.0.1:8732`. Alembic head is still `0007_embeddings`.

## Verified

- `.venv/bin/python -m pytest` — 109 passed, 3 deselected (`network` and `model`), 0 failed.
- `npm --prefix frontend run build` — completed.
- A workflow on the synthetic peptide plus ethanol returned a real polymer-residue measurement and canonical SMILES `CCO`.
- Resume reran only the failed step.
- With Vina hidden, docking and the dependent step were skipped with a reason.
- LLM summarize is 503 by default. With the flag on, `[PMID:9]` was rejected when only `PMID:1` was retrieved.

## Broken or incomplete

- The workflow docking step does not launch Vina even when Vina is installed. It skips with that reason.
- Simulation checkpoint resume is not implemented.
- NVE relative drift of 0.02 was not stable. Same-seed OpenMM energy missed 1.0 kJ/mol on one run (1.6878).
- fpocket is absent. The Milestone 4 redocking table is in `docs/SCIENTIFIC_VALIDATION.md` (tuning 3/5, held-out 2/5, three preparation failures with no RMSD).
- Open Targets, DailyMed, and Europe PMC were not built.
- Playwright was not re-run.

## Decisions

- Workflow state is the stored analysis JSON. There is no new table.
- LLM features default off. The citation check does not call an external model.

## Next task

Milestone 6 sessions 6A–6F are implemented on their branches. No further milestone was requested.

## UI controls

- Research Library: a JSON workflow form. The limitation sentence comes from the API.
- Drug Discovery generation controls, Simulation Center, and Model Laboratory remain.
