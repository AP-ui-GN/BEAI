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
