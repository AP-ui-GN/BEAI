# BEAI audit

Date: 2026-10-11. Scope: kickoff inspection only. No application code, dependencies, data, or git history were changed.

## Repository

`main` is a single commit, `1c0b99b` ("Initialize project"). `git ls-tree -r main --name-only` prints nothing. The working tree was clean. Nothing was stashed, reset, or cleaned.

This branch is `cursor/beai-kickoff-rules-c3c0`. Its first commit, `c4a3a7b`, adds `AGENTS.md`, `.cursor/rules/`, `.cursor/commands/`, and `.cursorignore`. Kickoff then added `docs/` and replaced the command TODOs in `AGENTS.md`.

`git status` at inspection: clean, tracking `origin/cursor/beai-kickoff-rules-c3c0`.

`git branch -a`:

- `cursor/beai-kickoff-rules-c3c0` (current)
- `main`
- `remotes/origin/HEAD -> origin/main`
- `remotes/origin/main`
- `remotes/origin/cursor/beai-kickoff-rules-c3c0`

Depth-3 tree, ignoring `node_modules`, `.venv`, `.git`, `data`, and model weights: `AGENTS.md`, `.cursorignore`, `.cursor/rules/*.mdc`, `.cursor/commands/*.md`. No `README`, `package.json`, `pyproject.toml`, requirements file, lockfile, Dockerfile, Compose file, `.env.example`, Makefile, `backend/`, `frontend/`, `tests/`, `.github/`, `data/`, `models/`, or `.venv`.

There is no documented install or start command, so no server was started and no test suite was run.

## Platform

| Check | Result |
| --- | --- |
| OS | Ubuntu 24.04.5 LTS, Linux 6.12.94+, x86_64 |
| CPU | 4 cores |
| RAM | 15 GiB total, about 4.9 GiB available, no swap |
| GPU | `nvidia-smi` absent |
| Python | 3.12.3 at `/usr/bin/python3` (satisfies the 3.11+ default) |
| Project virtualenv | absent |
| pip | 24.0 (system). Do not install into it |
| Node on `PATH` | v22.14.0 at `/exec-daemon/node` |
| npm | 10.9.9, from nvm Node v22.23.3 |
| pnpm / yarn | 10.33.4 / 1.22.22, same nvm prefix |
| uv, conda | absent |
| pytest, ruff | absent |
| mkdssp, dssp, vina, obabel | absent |

Imports with system Python, because no project environment exists:

| Module | Result |
| --- | --- |
| rdkit | absent (`ModuleNotFoundError`) |
| Bio (Biopython) | absent |
| biotite | absent |
| openmm | absent |
| torch | absent |

`curl -I --max-time 20 https://files.rcsb.org/download/1UBQ.pdb` returned HTTP 200 (`content-type: text/plain`, `content-disposition: attachment;filename=1UBQ.pdb`). The body was not saved. Residue counts were not read and are not recorded here.

## Capability classification

Nothing is Working, Partial, Broken, or Mock. There is no application to run.

| Capability | Status | Evidence |
| --- | --- | --- |
| Backend start | Missing | no `backend/`; no entrypoint file |
| Frontend start | Missing | no `package.json`; no `frontend/` |
| Database | Missing | no SQLAlchemy models or Alembic tree |
| Upload | Missing | no routes |
| Parsing | Missing | no structure service |
| Analysis | Missing | no analysis service |
| Viewer | Missing | no frontend |
| Persistence | Missing | no database and no storage directory |
| Reports | Missing | no report service |
| Tests | Missing | `pytest` absent; no `tests/` |
| Health endpoint | Missing | no API |
| Protein | Missing | no `services/structure` or `services/sequence` |
| Compound | Missing | no `services/compounds`; `rdkit` import absent |
| Drug discovery | Missing | no docking service; `vina` absent |
| Safety | Missing | no safety service |
| Simulation | Missing | no simulation service; `openmm` import absent |

## Fake behaviour

No application code exists, so there is no hardcoded scientific output, timer-driven progress, random confidence score, dead button, mock API, or swallowing `try/except`.

Search (rules and command text only; no `*.py`, `*.ts`, or `*.tsx` files):

```text
rg -n "random\\(|Math\\.random|TODO|mock|fake|dummy|placeholder|setTimeout|time\\.sleep"
```

Hits were the anti-fake command, the "no fake progress" rule, the `.env.example` placeholder rule, and the command TODOs in `AGENTS.md`. Those TODOs are replaced in this kickoff with the verified "not present" lines. No scientific value was invented to fill them.

## Risks

- The product is entirely unbuilt. Milestone 1 is a greenfield slice, not a repair.
- Installing into system Python is forbidden, and there is no virtualenv yet. The first Milestone 1 step has to create `.venv` before any package is installed.
- About 4.9 GiB RAM is free and there is no GPU. Large models and long simulations do not belong in early milestones.
- `node` and `npm` resolve to different Node installs (v22.14.0 vs v22.23.3). Frontend scripts must use one of them on purpose.
- Playwright's browser download and later PyTorch, OpenMM, and Vina installs may be large. Check size before installing. Anything over about 500 MB waits for an explicit yes.
- Expected residue counts for 1UBQ and 4HHB must be copied from the RCSB entry pages during implementation. They are intentionally absent from this audit.
- Optional tools are missing. Later milestones must return HTTP 503 and an honest health reason, not a stand-in result.

## Proposed `.cursor/rules` changes

No rule file was edited. The scientific-integrity and safety rules stay as committed.

The globs in rules 10, 20, 30, and 40 match the proposed layout and currently match no source files. That is correct for an empty repository. Do not retarget them at a guessed stack. Revisit a glob only if Milestone 1 deliberately chooses a different path, and record that choice in `docs/ARCHITECTURE.md` first.

No change is proposed to rules 00 or 50.
