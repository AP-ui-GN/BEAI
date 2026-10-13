# Known limitations

Date: 2026-10-13. Limits after Milestone 2. They are not scientific results.

## Milestone 2

- The pocket detector is a grid heuristic. Held-out success was 3 of 5 at the pre-registered 4.0 Å centroid cutoff. 1FKF, 2PK4, 1TLP, and 4DFR failed. It is not a general binding-site predictor.
- fpocket is not installed. Pocket jobs skip that stage and say so.
- Relative SASA is not reported. No maximum-accessibility table is cited.
- Hydrogen bonds are backbone heavy-atom estimates. 1UBQ has no hydrogens.
- P-SEA is only the fallback. A file that is not valid PDB or mmCIF can make Biopython's DSSP wrapper warn and then fail over; the overview still records which algorithm ran.
- UniProt import stores the full returned sequence. P62988 is inactive (demerged) and is rejected with the successor accessions from the API. It is not silently replaced.
- Sequence mass is an average mass with terminal water included. It is not monoisotopic and not an experimental mass.
- Jobs are an in-process thread pool. There is still no separate worker service. Progress is null until a handler reports a fraction.
- Compound routes, docking, safety retrieval, and models are still unbuilt.

## Milestone 1 scope

- Only `structure_overview` is implemented. Docking, simulation, compounds, external retrieval, machine-learning models, authentication, PDF export, and Docker are not built. Those screens are Planned pages with no actions.
- The overview analyzes the first model only. PDB files with no `MODEL` record report a null author model serial. mmCIF reports the model number from the file (1 for 1UBQ).
- Radius of gyration is unweighted over C-alpha atoms. It is not a mass-weighted or hydrodynamic radius.
- Side-chain completeness uses 21 bundled chemical-component files (the 20 standard amino acids and MSE), downloaded 2026-10-11. Other residue types are not judged. Terminal OXT is a leaving atom in those files and is not required.
- Chain breaks are C-alpha distances above 4.5 Å by default. They are not crystallographic annotations.
- Secondary structure, SASA, and hydrogen bonds are not computed.
- Author R-free for 1UBQ and 4HHB is null because both files record FREE R VALUE as NULL (mmCIF `?`). The working R is not copied into the R-free field.
- Sequence agreement labelled `explained_by_missing_residues` compares residue-name multisets. It is not a residue-by-residue alignment.
- Jobs are synchronous. The dashboard job list is empty unless a request is in flight. There is no background worker.

## Repository

- `main` still has no files. Milestone 1 is on `m1-foundation`.
- There is no CI workflow.
- The README quick start is the command sequence used to create this environment. A second clone into an empty directory was not performed.

## Environment

- Project packages are installed in `.venv` (about 219 MB), created from `/usr/bin/python3` 3.12.3. They were not installed into system site-packages.
- Not importable on this machine: OpenMM, PyTorch. Biopython 1.88, Biotite 1.6.0, and RDKit 2025.09.1 are installed.
- `pytest` and `ruff` are inside `.venv`, not on the default `PATH`. `mkdssp` 4.2.2 is on PATH from the Ubuntu `dssp` package. Still absent from `PATH`: vina, obabel, fpocket.
- uv and conda are not installed. The planned installer is pip inside `.venv`.
- No NVIDIA GPU (`nvidia-smi` absent). CUDA-only tools and GPU model loading are unavailable.
- Memory: 15 GiB total, about 4.9 GiB available at inspection, no swap. A model whose declared footprint exceeds free RAM must be refused.
- Frontend scripts use Node v22.23.3 and npm 10.9.9 from `/home/ubuntu/.nvm/versions/node/v22.23.3`. `node` on the default `PATH` is still v22.14.0 at `/exec-daemon/node` and is not used for npm.
- Playwright's Chromium cache unpacked to about 681 MB under `~/.cache/ms-playwright`. The downloaded zips were 191.1 MB (Chrome for Testing), 120 MB (headless shell), and 2.2 MB (ffmpeg). That unpacked size is above the roughly 500 MB ask-first line. It was measured after `npx playwright install chromium` completed. Firefox and WebKit were not installed.
- Starlette's `TestClient` warns that `httpx` is deprecated in favor of `httpx2`. Tests ran on `httpx==0.28.1`. `httpx2` was not installed.

## Data and tools the app will miss until later milestones

- Secondary structure uses DSSP when `mkdssp` is on PATH and Biotite P-SEA otherwise. The method record names which one ran.
- Docking cannot run until Vina and a preparation route exist. The API must say so with HTTP 503. No pose will be invented.
- Simulation cannot run until OpenMM is installed. Same 503 rule.
- Compound routes run with RDKit. If that import is hidden they return HTTP 503 and protein routes still work.
- Fixture files saved on 2026-10-11: `1UBQ.pdb`, `1UBQ.cif`, and `4HHB.pdb` from `https://files.rcsb.org/download/`. Checksums are in `backend/tests/fixtures/README.md`. Expected counts are in `backend/tests/fixtures/rcsb_entry_snapshot.json`, copied from the RCSB Data API the same day. The HTML entry pages are client-rendered, so the API behind them was the source.
- No live call was made to PubChem, ChEMBL, UniProt, openFDA, or a model host. Their current endpoints are unchecked.

## Honesty gaps that are intentional

- Residue counts for 1UBQ and 4HHB are in `backend/tests/fixtures/rcsb_entry_snapshot.json`, copied from the RCSB Data API on 2026-10-11. They are not hardcoded in the application.
- Pocket, docking, embedding, and simulation thresholds that are not already fixed by the milestone contract stay unregistered until the chat that runs them writes the threshold down first.
