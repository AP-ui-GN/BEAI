# Known limitations

Date: 2026-10-11. These are limits found during kickoff. They are not scientific results.

## Repository

- `main` has no files. There is no application, README, test, CI workflow, or fixture.
- No command can install, start, test, or migrate the app, because those entrypoints do not exist.
- `AGENTS.md` records that absence. Proposed commands live only in `docs/ARCHITECTURE.md` and are not verified.

## Environment

- No project virtualenv. System Python is 3.12.3 at `/usr/bin/python3`. Project packages must not be installed into system site-packages. Create `.venv` in Milestone 1 first.
- Not importable on this machine: RDKit, Biopython, Biotite, OpenMM, PyTorch.
- Not on `PATH`: pytest, ruff, mkdssp, dssp, vina, obabel.
- uv and conda are not installed. The planned installer is pip inside `.venv`.
- No NVIDIA GPU (`nvidia-smi` absent). CUDA-only tools and GPU model loading are unavailable.
- Memory: 15 GiB total, about 4.9 GiB available at inspection, no swap. A model whose declared footprint exceeds free RAM must be refused.
- `node` on `PATH` is v22.14.0 (`/exec-daemon/node`). `npm` 10.9.9 is the nvm binary for Node v22.23.3. Using them as a pair can disagree about `node` inside scripts. Milestone 1 should choose one Node and record the choice.

## Data and tools the app will miss until later milestones

- Secondary structure cannot use DSSP until `mkdssp` is installed. The planned fallback is Biotite P-SEA, and the method record has to say which one ran.
- Docking cannot run until Vina and a preparation route exist. The API must say so with HTTP 503. No pose will be invented.
- Simulation cannot run until OpenMM is installed. Same 503 rule.
- Compound routes cannot run until RDKit is installed. Same 503 rule.
- RCSB file download was reachable: HTTP 200 from `https://files.rcsb.org/download/1UBQ.pdb` (HEAD only). The PDB body was not saved, and 4HHB was not requested. Fixture files are still absent.
- No live call was made to PubChem, ChEMBL, UniProt, openFDA, or a model host. Their current endpoints are unchecked.

## Honesty gaps that are intentional

- Residue counts for 1UBQ and 4HHB are not in the repo. Putting them here from memory would violate the testing rule.
- Pocket, docking, embedding, and simulation thresholds that are not already fixed by the milestone contract stay unregistered until the chat that runs them writes the threshold down first.
