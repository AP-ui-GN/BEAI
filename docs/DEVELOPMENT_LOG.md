# Development log

## 2026-10-11 — Kickoff audit and plan

No application code, dependency, dataset, or git history change. Rules and slash commands were already committed as `c4a3a7b` before this inspection. This entry covers the inspection commands and their results.

### Git

- `git status` — on `cursor/beai-kickoff-rules-c3c0`, clean, up to date with origin. No uncommitted work. Did not stash, reset, or clean.
- `git log --oneline -20` — `c4a3a7b` docs: add BEAI agent brief and Cursor rules; `1c0b99b` Initialize project.
- `git branch -a` — local `cursor/beai-kickoff-rules-c3c0` and `main`; remotes `origin/main` and `origin/cursor/beai-kickoff-rules-c3c0`. `origin/HEAD` points at `origin/main`.
- `git ls-tree -r main --name-only` — empty output. The initialize commit has no files.
- `git ls-tree -r HEAD --name-only | wc -l` — 15 (agent brief, rules, commands, `.cursorignore` only, at inspection time).

### Tree and manifests

- `find . -maxdepth 3` ignoring `node_modules`, `.venv`, `.git`, `data`, and `models` — only `AGENTS.md`, `.cursorignore`, `.cursor/rules/`, `.cursor/commands/`.
- Absent: `README.md`, `package.json`, `pyproject.toml`, `requirements.txt`, lockfiles, Dockerfile, Compose, `.env.example`, Makefile, `backend/`, `frontend/`, `tests/`, `.github/`, `data/`, `models/`, `.venv`.

### Environment

- `python3 --version` — Python 3.12.3 (`/usr/bin/python3`).
- Project `.venv` — absent. Imports below used system Python. Nothing was installed.
- `node --version` — v22.14.0 (`/exec-daemon/node`).
- `npm --version` — 10.9.9 (`/home/ubuntu/.nvm/versions/node/v22.23.3/bin/npm`).
- `pnpm --version` — 10.33.4. `yarn --version` — 1.22.22.
- `uv` — absent. `conda` — absent.
- `pip --version` — pip 24.0 (system).
- `pytest` — absent. `ruff` — absent.
- `mkdssp`, `dssp`, `vina`, `obabel` — absent.
- OS — Ubuntu 24.04.5 LTS, Linux 6.12.94+, x86_64, 4 CPUs.
- `free -h` — 15 GiB total, about 4.2 GiB free, about 4.9 GiB available, swap 0.
- `nvidia-smi` — absent.
- Imports of `rdkit`, `Bio`, `biotite`, `openmm`, `torch` — each `ModuleNotFoundError`.

### Commands that were not run

No README or manifest documents install, start, test, or migrate. No server was started. No test suite exists to run. Proposed commands are in `docs/ARCHITECTURE.md` and are explicitly unverified.

### Network

- `curl -I --max-time 20 https://files.rcsb.org/download/1UBQ.pdb` — HTTP 200, `content-type: text/plain`, attachment filename `1UBQ.pdb`. Body not downloaded. Counts not read.

### Fake-behaviour search

- `rg` for `random(`, `Math.random`, `mock`, `fake`, `dummy`, `placeholder`, timers — matches only in `.cursor/rules/00-beai-core.mdc`, `.cursor/commands/anti-fake-audit.md`, and the command TODOs then in `AGENTS.md`. No application source.

### Docs written

`docs/AUDIT.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `docs/SCIENTIFIC_VALIDATION.md`, `docs/KNOWN_LIMITATIONS.md`, `docs/DEVELOPMENT_LOG.md`, `docs/HANDOFF.md`. `AGENTS.md` command TODOs replaced with the verified "not present" lines, and an as-is layout section added. `.cursor/rules/` not modified.

## 2026-10-11 — Milestone 1, backend skeleton and health

Baseline before edits: `git status` was clean on `cursor/beai-kickoff-rules-c3c0` at `526a53f`. No test suite existed (`pytest` was not installed; no `tests/` directory). Work continues on branch `m1-foundation`.

### Install

- Created `.venv` with `/usr/bin/python3 -m venv .venv` (Python 3.12.3). Nothing was installed into system Python.
- `.venv/bin/python -m pip install -U pip` then installed the direct packages recorded in `pyproject.toml`. `.venv` is about 218 MB.
- `.venv/bin/python -m pip install -e ".[dev]"`.

### Tests

- `.venv/bin/ruff check backend` — all checks passed.
- `.venv/bin/python -m pytest` — **6 passed, 0 failed**, 1 warning (`StarletteDeprecationWarning`: Starlette's `TestClient` prefers `httpx2`; tests still ran on `httpx==0.28.1`).

Health on a fresh SQLite file reports `degraded` because there is no Alembic revision yet. RDKit, mkdssp, Vina, OpenMM, PyTorch, and GPU are `available: false` with `version: null` and a reason. No server was left running for this step.

## 2026-10-11 — Milestone 1, database and structure upload

- Alembic revision `0001_initial` creates `structures` and `analyses`.
- `POST /api/structures` streams the body, enforces the byte limit, sniffs PDB or mmCIF, parses with Biopython 1.88, and stores the bytes under a UUID filename.
- `.venv/bin/python -m pytest` — **15 passed, 0 failed**, 1 warning (Starlette `TestClient` prefers `httpx2`; `httpx==0.28.1` still ran the suite).
- `.venv/bin/ruff check backend` — passed.

## 2026-10-11 — Milestone 1, structure_overview

- Downloaded 1UBQ PDB and mmCIF and 4HHB PDB from `https://files.rcsb.org/download/` and saved sha256 values in `backend/tests/fixtures/README.md`.
- Copied chain, solvent, heme, and phosphate counts from the RCSB Data API on 2026-10-11 into `backend/tests/fixtures/rcsb_entry_snapshot.json`. The HTML entry pages are client-rendered, so the API behind them was the source.
- Bundled chemical-component files for the 20 standard amino acids plus MSE from `https://files.rcsb.org/ligands/download/{ID}.cif` the same day. Required heavy atoms exclude hydrogens and atoms with `pdbx_leaving_atom_flag` Y (OXT).
- `.venv/bin/python -m pytest` — **31 passed, 0 failed**, 1 warning (Starlette `TestClient` / `httpx2`).
- `.venv/bin/ruff check backend` — passed.

## 2026-10-11 — Milestone 1, reports

- `GET /api/analyses/{id}/report?format=html|md|json` renders the stored `AnalysisResult` with Jinja2. HTML autoescape is on.
- `.venv/bin/python -m pytest` — **34 passed, 0 failed**, 1 warning (Starlette `TestClient` / `httpx2`).
- A TITLE containing `<script>alert("xss")</script>` is escaped in the HTML report and unchanged in the JSON report.

## 2026-10-11 — Milestone 1, frontend shell and dashboard

- Frontend toolchain is Node v22.23.3 with npm 10.9.9 from `/home/ubuntu/.nvm/versions/node/v22.23.3`. That pair is used on purpose so `node` and `npm` belong to the same install. The `node` binary earlier on `PATH` was v22.14.0.
- Vite dev server is configured for `127.0.0.1:8732` and proxies `/api` to `127.0.0.1:8731`.
- `npm --prefix frontend test` — **4 passed, 0 failed** (Vitest).
- `npm --prefix frontend run build` — `tsc -b && vite build` completed.
- Areas other than the dashboard are Planned pages with no action buttons. Protein Explorer is still planned in this commit.

## 2026-10-11 — Milestone 1, Protein Explorer and viewer

- 3Dmol.js 2.5.5 is isolated in `frontend/src/components/StructureViewer.tsx`.
- Protein Explorer uploads a file, runs `structure_overview`, and shows chains, composition, measurements, missing data, limitations, and report links.
- `npm --prefix frontend test` — **7 passed, 0 failed**.
- `npx tsc -b` in `frontend` — exit 0.

## 2026-10-11 — Milestone 1, end-to-end test and docs

Servers were started with logs in `.logs/backend.log` and `.logs/frontend.log`.

- `GET http://127.0.0.1:8731/api/health` — HTTP 200, status ok, revision `0001_initial`. RDKit, mkdssp, Vina, OpenMM, PyTorch, and GPU were `available: false` with reasons. No versions were invented.
- `curl -F file=@backend/tests/fixtures/1UBQ.pdb` to `POST /api/structures` — HTTP 201, format pdb, 78570 bytes, title `STRUCTURE OF UBIQUITIN REFINED AT 1.8 ANGSTROMS RESOLUTION`, chain A.
- `POST /api/structures/{id}/analyses` with `{"kind":"structure_overview"}` — HTTP 201, status succeeded, 76 polymer residues, 58 waters, resolution 1.8, R-free null.
- `GET /api/analyses/{id}` matched that create response. After uvicorn was stopped and started again, the same GET was identical.
- `GET /api/analyses/{id}/report?format=html` — HTTP 200, `Content-Disposition: attachment`, title present, no raw `<script>` tag.
- `.venv/bin/python -m pytest` — **34 passed, 0 failed** (2+8+4+3+8+9). One Starlette/`httpx2` warning.
- `npm --prefix frontend test` — **7 passed, 0 failed**.
- `npm --prefix frontend run e2e` — **1 passed, 0 failed**.
- UI search for `Math.random`, `random(`, `setTimeout`, and `setInterval` in `backend/` and `frontend/src` — no matches. The only `placeholder` hit is the Tailwind class `placeholder:text-muted-foreground` in the shadcn input. Controls are listed in `docs/HANDOFF.md`. None are unwired.
- Playwright Chromium unpacked to about 681 MB. Recorded in `docs/KNOWN_LIMITATIONS.md`. Firefox and WebKit were not installed. PyTorch, OpenMM, and Vina were not installed.

## 2026-10-13 — Milestone 2, protein intelligence

Baseline before edits: `m1-foundation` at `57e3a59`, `.venv/bin/python -m pytest` **34 passed, 0 failed**.

- Installed Ubuntu `dssp` 4.2.2 (`mkdssp`, BSD-2-Clause, about 6.4 MB) and pinned Biotite 1.6.0 (BSD-3-Clause, package directory about 132 MB) plus httpx 0.28.1. The `.venv` is about 526 MB. fpocket was not installed.
- `.venv/bin/python -m pytest` — **55 passed, 1 deselected, 0 failed**. The deselected test is marked `network`.
- `.venv/bin/python -m pytest --override-ini addopts= -m network backend/tests/test_retrieval.py` — **1 passed, 0 failed**. Live RCSB 1UBQ and UniProt P62987.
- `npm --prefix frontend test` — **7 passed, 0 failed**. `npm --prefix frontend run build` completed.
- 1UBQ DSSP, SASA, mass, and the pocket benchmark numbers are in `docs/SCIENTIFIC_VALIDATION.md`. They were copied from the commands in this entry's tests, not typed from memory.
- Pocket parameters were changed once using only the tuning set, after protein radius 1.7 Å left the core unfilled. Held-out success was 3/5, including the failures.
- The protein UI polls `GET /api/jobs/{id}` on a timer while a real job is running. The timer is not a progress value. Progress shown in the UI is the number the job row returns, or blank when that number is null.

## 2026-10-13 — Milestone 3, compound intelligence

- Installed `rdkit==2025.9.1` (BSD-3-Clause, about 73 MB). `rdkit.__version__` is `2025.09.1`. The `.venv` is about 610 MB.
- PubChem name lookup for aspirin on 2026-10-13 returned ConnectivitySMILES and a null CanonicalSMILES. The importer stores that null instead of copying the connectivity string into the canonical field.
- ChEMBL molecule JSON for CHEMBL25 did not include a licence field. The stored record says so.
- `.venv/bin/python -m pytest` — **66 passed, 1 deselected, 0 failed**.
- `npm --prefix frontend test` — **7 passed, 0 failed**. `npm --prefix frontend run build` completed.
- Aspirin, caffeine, and ethanol matched C9H8O4 / 180.16, C8H10N4O2 / 194.19, and C2H6O / 46.07 after rounding MolWt to 2 decimals.

## 2026-10-13 — Milestone 4, docking

- Ubuntu package `autodock-vina` 1.2.5. Meeko 0.8.0 (LGPL-2.1, about 9.2 MB) and gemmi 0.7.5 (MPL-2.0, about 6.9 MB). Meeko 0.6.1 does not support Python 3.12.
- A real Vina run on 3PTB / benzamidine wrote `backend/tests/fixtures/vina/3ptb_ben_seed1.pdbqt`. Parser scores match those REMARK lines. Two seed-1 runs differed by 0.006 kcal/mol. The test window is 0.05 kcal/mol.
- `.venv/bin/python -m pytest` — **71 passed, 1 deselected, 0 failed**. Docking tests included a real Vina run.

## 2026-10-13 — Milestone 6 session 6D, OpenMM

- Installed openmm 8.6.1 (wheel metadata: Python Software Foundation License (BSD-like); wheel about 14.4 MB; package directory about 70 MB) and pdbfixer 1.12.0 (MIT). Platforms: Reference and CPU.
- 1UBQ minimization lowered the potential energy. A 20-iteration probe went from -328.93633723496714 to -8331.638644503953 kJ/mol.
- NVE relative drift on one 20-step run was 0.0004987123454089311. An earlier run was 0.08066315438678218. The 0.02 bound is not stable.
- Langevin mean temperature 260.1331467073965 K. Same-seed total-energy gap 1.6878309150943096 kJ/mol, which missed the 1.0 kJ/mol target.
- `.venv/bin/python -m pytest` — **103 passed, 3 deselected, 0 failed**.
- `npm --prefix frontend test` — 9 passed. `npm --prefix frontend run build` completed.

## 2026-10-13 — Milestone 6 session 6C, solubility models

- Delaney CSV downloaded from the DeepChem `load_delaney` URL. sha256 `8c06a76f0c6487d29ab0f903e6a7a7139f189ab3c1178f159c8be8964602f189`, 96699 bytes. The file has no licence line. DeepChem's LICENSE is MIT for the software.
- Installed scikit-learn 1.9.1 (BSD-3-Clause, package directory about 49 MB) and torch-geometric 2.8.1 (MIT, about 13 MB).
- Scaffold split seed 20261013: 902 train, 226 test, 0 dropped. Descriptor Ridge test RMSE 1.3217993772506413, Morgan Ridge 1.6696791869919676, two-layer GCN 2.5347372633569814 (R-squared -0.4764081172372039). A second seed-matched run stayed within 1e-6. The GCN result is worse than the mean of the test labels and is recorded as produced.
- `.venv/bin/python -m pytest` — **98 passed, 3 deselected, 0 failed**. `npm --prefix frontend test` — **9 passed**. `npm --prefix frontend run build` completed.
- `.venv/bin/python -m pytest --override-ini addopts= -m network backend/tests/test_solubility.py::test_esol_held_out_metrics` — 1 passed.

## 2026-10-13 — Milestone 6 session 6B, protein embeddings

- ESM-2 8M model card read before use: MIT licence, `max_position_embeddings` 1026. `model.safetensors` sha256 `24c5fa474c48f3b754b86efe752d5f189d2bcd88190fa2270fc92b2ef3034189` matched the Hub LFS oid. 31384292 bytes. The pickle weight file was not downloaded.
- Installed `torch==2.9.1+cpu` (BSD-3-Clause, wheel 184.4 MB, package directory about 725 MB) and `transformers==5.19.0` (Apache 2.0, package directory about 116 MB) from the PyTorch CPU index.
- `.venv/bin/python -m pytest` — **94 passed, 2 deselected (`network` and `model`), 0 failed**.
- `.venv/bin/python -m pytest --override-ini addopts= -m model backend/tests/test_embeddings_model.py` — **1 passed**. Spearman 0.6990131578947367 on 28 pairs, bootstrap interval 0.3788637829986782 to 0.8820213682475236, seed 20261013, 1000 resamples.
- `npm --prefix frontend test` — **9 passed, 0 failed**. `npm --prefix frontend run build` completed.

## 2026-10-13 — Milestone 6 session 6A, model registry

Baseline before edits: `m5-safety` at `65d80c7`. `.venv/bin/python -m pytest` — **78 passed, 1 deselected (`network`), 0 failed**.

- Added Alembic `0006_models` and `GET/POST /api/models`, `GET /api/models/hardware`, load, and unload. RAM is `psutil.virtual_memory`. CUDA and MPS are queried only if PyTorch imports.
- psutil 7.2.2, wheel metadata BSD-3-Clause, wheel about 155 kB, package directory about 900 kB.
- `.venv/bin/python -m pytest` — **88 passed, 1 deselected (`network`), 0 failed**.
- `npm --prefix frontend test` — **9 passed, 0 failed**. `npm --prefix frontend run build` completed.
- Startup with a pre-inserted registry row did not call the loader. A declared RAM requirement above the machine total was refused. A missing Python dependency returned HTTP 503 and `GET /api/health` stayed 200.

## 2026-10-13 — Milestone 5, therapeutic safety evidence

- openFDA label and FAERS count responses, and a PubMed esearch/esummary pair, were saved from live calls on 2026-10-13 and used as mock bodies.
- Label section text is stored verbatim. FAERS items are observational and include the not-causal statement. Literature stays unclassified. Similarity off-targets are computational_prediction and unverified.
- An overdose-worded query returns the poison-control pointer. The Drug Safety page carries the research-use banner and does not offer dosing or medication changes.
- `.venv/bin/python -m pytest` — **78 passed, 1 deselected, 0 failed**.
- `npm --prefix frontend run build` — completed.
- A 5–10 complex heavy-atom RMSD table was not run. That gap is in `docs/SCIENTIFIC_VALIDATION.md`. No pose was invented.
