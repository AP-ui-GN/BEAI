# Handoff

Date: 2026-10-13. Session 6D OpenMM is on `m6d-simulation`, branched from `m6c-properties`. Sessions 6E and 6F have not started.

## Current state

`POST /api/simulation` prepares a structure with PDBFixer and runs either energy minimization or a short OpenMM trajectory. Steps are capped at 500. Minimization iterations are capped at 100. `GET /api/health` lists OpenMM platforms. On this machine they are Reference and CPU. The Simulation Center shows the two required labels and, when a job stores frames, a frame slider over the returned PDB text.

API: `http://127.0.0.1:8731`. App: `http://127.0.0.1:8732`. Alembic head is still `0007_embeddings`.

## Verified

- `.venv/bin/python -m pytest` — 103 passed, 3 deselected (`network` and `model`), 0 failed.
- `npm --prefix frontend test` — 9 passed, 0 failed. `npm --prefix frontend run build` completed.
- Minimization on 1UBQ with 5 iterations finished with a lower potential energy than it started.
- A 20-step NVE run after 20 minimization iterations had relative total-energy drift 0.0004987123454089311. An earlier run the same day was 0.08066315438678218. The 0.02 bound is not stable.
- Langevin mean temperature on the recorded run was 260.1331467073965 K, inside 150 K to 450 K.
- Same-seed final total energies differed by 1.6878309150943096 kJ/mol. The 1.0 kJ/mol target was missed.
- A residue the force field cannot template fails the job and stores no analysis.
- Hiding OpenMM returns HTTP 503. Health still answers.

## Broken or incomplete

- Checkpoint resume is not implemented.
- NVE drift and same-seed energy are not inside the original tight bounds on every run.
- fpocket is absent. The Milestone 4 5–10 complex RMSD table was not run.
- Open Targets, DailyMed, and Europe PMC were not built.
- Generation and workflows are not built.
- Playwright was not re-run.

## Decisions

- Implicit GBn2 solvent, not a water box, so a CPU run stays short.
- One OpenMM CPU thread, so a repeated seed is not dominated by reduction order.
- Verlet NVE starts from minimized coordinates with zero velocities. Langevin velocities use the request seed.

## Next task

Session 6E, molecular generation, from this branch. Therapeutic objectives only. PAINS, Brenk, and NIH filters stay on and cannot be switched off. Every output is labelled "computational hypothesis: unsynthesized, unvalidated".

## UI controls

- Simulation Center: choose a stored structure, minimize, or run short dynamics. Labels for minimization and for the short run are on the page. Results and limitations come from the analysis. The frame slider uses PDB text from the stored frames.
- Model Laboratory controls from 6C remain.
