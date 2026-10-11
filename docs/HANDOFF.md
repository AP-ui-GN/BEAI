# Handoff

Date: 2026-10-11. Milestone 1 is implemented on `m1-foundation`. Milestone 2 has not started.

## Current state

A user can upload a PDB or mmCIF file, run `structure_overview`, see measurements from that file, view it with 3Dmol.js, reload the saved analysis, and download HTML, Markdown, and JSON reports. SQLite is `data/beai.sqlite`. Structure bytes are under `data/structures/` with UUID filenames.

API: `http://127.0.0.1:8731`. App: `http://127.0.0.1:8732`. Both were left running at the end of this chat. Logs: `.logs/backend.log` and `.logs/frontend.log`.

## Verified (command → result)

- `.venv/bin/python -m pytest` — 34 passed, 0 failed. One warning: Starlette `TestClient` prefers `httpx2`; the suite used `httpx==0.28.1`.
- `npm --prefix frontend test` — 7 passed, 0 failed (Vitest). Playwright's spec is excluded from Vitest.
- `npm --prefix frontend run e2e` — 1 passed, 0 failed. Uploaded `1UBQ.pdb`, canvas bounding box was non-zero, chain select changed to A, HTML report download started.
- `npm --prefix frontend run build` — `tsc -b && vite build` completed.
- `GET /api/health` — HTTP 200, `status` ok, revision `0001_initial`, RDKit/mkdssp/Vina/OpenMM/PyTorch/GPU `available: false` with reasons.
- `curl` upload of `backend/tests/fixtures/1UBQ.pdb` — HTTP 201. Analyze — HTTP 201, status succeeded, chain A, 76 polymer residues, 58 waters, resolution 1.8 Å, R-free null. Fetch of that analysis matched the create response. After stopping and starting uvicorn, the same fetch was identical.
- HTML report for that analysis — HTTP 200, `Content-Disposition: attachment`, title text present, no raw `<script>` tag.

Counts for 1UBQ and 4HHB were copied from the RCSB Data API on 2026-10-11 into `backend/tests/fixtures/rcsb_entry_snapshot.json`, not from memory.

## Broken or incomplete

- No docking, simulation, compounds, external APIs, models, authentication, PDF, or Docker.
- `mkdssp` is absent, so secondary structure is not computed. That is Milestone 2.
- Playwright's unpacked browser cache is about 681 MB. See `docs/KNOWN_LIMITATIONS.md`.
- The README quick start was the sequence used to create this `.venv` and `frontend/node_modules`. It was not repeated from a second empty clone.
- Planned pages have no actions. Protein Explorer and Research Library are the working surfaces besides the dashboard.

## Decisions made and why

Unchanged from kickoff: SQLite, 3Dmol.js, synchronous analysis in the request, HTML/Markdown/JSON reports, pip inside `.venv`. Node v22.23.3 was selected so `node` and `npm` are the same install. Chemical-component files for the 20 amino acids plus MSE were vendored from `files.rcsb.org` on 2026-10-11 so completeness checks do not use atom names typed from memory. Rules in `.cursor/rules` were not edited.

## Next task

Milestone 2, after this branch is reviewed. Read this file first. Confirm `pytest`, Vitest, and Playwright are still green. Do not install PyTorch, OpenMM, or Vina without checking size. `mkdssp` is still absent, so secondary structure should use the planned Biotite P-SEA fallback and say so in the method record.

## UI controls

- Menu (narrow screens): shows or hides navigation.
- Navigation links: open Dashboard, Protein Explorer, Compound Explorer, Drug Discovery, Drug Safety, Simulation Center, Research Library, or Model Laboratory.
- Dashboard Retry: shown only after a failed load; requests `/api/health` and `/api/analyses` again.
- Recent-analysis links: open that structure in Protein Explorer.
- File input and drag-and-drop: upload, then run `structure_overview`.
- Structure list links: open a saved structure.
- Run structure overview: shown when a structure has no successful overview.
- Chain select, ligand checkbox, water checkbox, Reset view: change the 3Dmol.js wrapper.
- Residue buttons in the missing and incomplete tables: ask the viewer to highlight that residue. Missing residues also say they have no coordinates.
- Report links: download HTML, Markdown, or JSON for the stored result.
- Planned pages: text only, no buttons. Drug Safety includes the research-use banner.
