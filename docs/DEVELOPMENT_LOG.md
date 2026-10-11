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
