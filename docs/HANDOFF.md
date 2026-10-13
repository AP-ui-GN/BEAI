# Handoff

Date: 2026-10-13. Milestone 2 is implemented on `m2-protein`. Milestone 3 has not started.

## Current state

A user can upload or import a structure, run `structure_overview` (header, geometry, DSSP, SASA, contacts, hydrogen-bond estimates, phi/psi), view it, compare two chains, run the baseline pocket detector as a job, paste or import a protein sequence, and download HTML, Markdown, and JSON reports. SQLite is `data/beai.sqlite`. Alembic head is `0003_sequences`.

API: `http://127.0.0.1:8731`. App: `http://127.0.0.1:8732`.

## Verified (command → result)

- `.venv/bin/python -m pytest` — 55 passed, 1 deselected (`network`), 0 failed.
- `.venv/bin/python -m pytest --override-ini addopts= -m network backend/tests/test_retrieval.py` — 1 passed, 0 failed. Live import of PDB 1UBQ and UniProt P62987.
- `npm --prefix frontend test` — 7 passed, 0 failed.
- `npm --prefix frontend run build` — `tsc -b && vite build` completed.
- Playwright was not re-run in this milestone. The smoke spec from Milestone 1 is unchanged.

1UBQ chain A is 76 polymer residues. DSSP 4.2.2 assigned H 12, G 6, E 24, B 2. Shrake-Rupley total SASA with waters excluded was 4893.04 Å²; Biotite on the same exclusion was 4834.72 Å² (1.19% relative difference, inside the 20% window written down first). Ubiquitin average mass was 8564.736 Da, 0.00086 Da from an independent elemental sum.

Pocket held-out success was 3 of 5. Failures: 1FKF, 2PK4, 1TLP, 4DFR. Numbers are in `docs/SCIENTIFIC_VALIDATION.md`.

## Broken or incomplete

- No docking, compounds, safety retrieval, models, authentication, PDF, or Docker.
- fpocket, RDKit, Vina, OpenMM, and PyTorch are not installed.
- The README quick start was not repeated from a second empty clone.
- Playwright was not re-run after the protein panels were added.

## Decisions made and why

- DSSP is preferred because `mkdssp` 4.2.2 installed from Ubuntu and Biopython could parse its classic output. P-SEA remains the fallback and is tested by hiding the binary.
- Pocket protein radius moved from 1.7 Å to 2.5 Å and the direction threshold from 4 to 5 after the tuning set showed an unfilled core. Held-out IDs were not used for that change.
- Relative SASA is omitted. No maximum-accessibility table was cited.
- Inactive UniProt entries are rejected with the successor list from the response. Nothing is stored.
- httpx and Biotite were added. The `.venv` is about 526 MB. fpocket was left absent and the job says so.

## Next task

Milestone 3, compound intelligence, from this branch. Confirm `pytest` and Vitest are still green. Install RDKit only after checking size and licence. Without RDKit, compound routes must return 503 and these protein tests must still pass.

## UI controls

- Menu, navigation, dashboard retry, structure upload, chain select, ligand and water checkboxes, reset view, residue highlight, and report downloads still work as in Milestone 1.
- Import structure: submits a PDB ID to `/api/structures/import`.
- Analyse sequence: submits FASTA or a UniProt accession.
- Detect pockets: starts a job, shows the returned status and progress, and can cancel while the job is pending or running.
- Load structures / Compare chains: starts a comparison job and shows the returned C-alpha RMSD.
- Secondary-structure track, Ramachandran points, SASA bars, and the contact map render values from the stored analysis.
- Planned pages for compounds, docking, safety, simulation, and models still have no action buttons.
