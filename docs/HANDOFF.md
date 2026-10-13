# Handoff

Date: 2026-10-13. Milestone 4 docking is on `m4-docking`, branched from `m3-compounds`. A full 5–10 complex redock RMSD table is not finished. Milestone 5 has not started.

## Current state

Compound routes sanitize SMILES with RDKit 2025.09.1, store canonical SMILES and InChIKey, calculate named descriptors, draw an SVG, and compute Morgan Tanimoto similarity. PubChem and ChEMBL imports keep retrieved fields apart from calculated descriptors. Activities are grouped by target, standard type, and units. Protein features from Milestone 2 still run.

API: `http://127.0.0.1:8731`. App: `http://127.0.0.1:8732`. Alembic head is `0004_compounds`.

## Verified

- `.venv/bin/python -m pytest` — 66 passed, 1 deselected (`network`), 0 failed.
- `npm --prefix frontend test` — 7 passed, 0 failed.
- `npm --prefix frontend run build` — completed.
- Playwright was not re-run.

## Broken or incomplete

- No docking, safety retrieval, simulation, or models.
- fpocket, Vina, OpenMM, and PyTorch are not installed.
- ChEMBL activity import requests at most 100 rows.
- The ChEMBL licence was not in the molecule JSON, so the record does not invent one.
- Playwright was not re-run after Compound Explorer replaced the planned page.

## Decisions

- RDKit 2025.9.1 from PyPI, about 73 MB, BSD-3-Clause. Under the 500 MB line.
- Salts stay multi-fragment unless `keep_largest_fragment` is true.
- Lipinski counts are property-filter observations, not a drug-likeness label.

## Next task

Milestone 4, docking, from this branch. If Vina cannot be installed, docking endpoints return 503 and the rest of the suite stays green. Do not invent a pose.

## UI controls

- Compound Explorer: SMILES submit, PubChem name import, compound list, depiction image, descriptor table with origin badges, compare the first two stored compounds, HTML report link.
- Protein controls from Milestone 2 remain.
- Drug Discovery, Drug Safety, Simulation Center, and Model Laboratory are still planned pages with no action buttons.
