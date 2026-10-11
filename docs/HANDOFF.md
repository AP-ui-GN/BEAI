# Handoff

Date: 2026-10-11. Kickoff is finished. Milestone 1 has not started.

## Current state

`main` is empty (`1c0b99b`, "Initialize project"). Branch `cursor/beai-kickoff-rules-c3c0` contains the agent brief, six Cursor rules, seven slash commands, `.cursorignore`, and the kickoff docs. There is no application, virtualenv, test, or fixture.

## Verified (command → result)

- `git ls-tree -r main --name-only` → empty.
- `git status` → clean on the kickoff branch before these docs were added.
- Manifest and directory checks → no README, backend, frontend, tests, CI, Docker, or `.venv`.
- `python3 --version` → Python 3.12.3. System imports of rdkit, Bio, biotite, openmm, torch → absent.
- `mkdssp`, `vina`, `nvidia-smi`, `pytest` → absent.
- `free -h` → 15 GiB RAM, about 4.9 GiB available, no GPU.
- `curl -I https://files.rcsb.org/download/1UBQ.pdb` → HTTP 200. Body not saved.
- Install, start, test, and migrate → not present, so not run.

## Broken or incomplete

The whole product is unbuilt. Health, upload, parsing, analysis, viewer, database, reports, and all five scientific areas are Missing. No fake implementation was found because there is no implementation.

`node` (v22.14.0) and `npm` (Node v22.23.3) are different installs.

## Decisions made and why

Recorded in `docs/ARCHITECTURE.md`: FastAPI on Python 3.12, SQLite, 3Dmol.js, in-process jobs from Milestone 2, HTML/Markdown/JSON reports, pip inside `.venv`. The prompt-pack defaults stand because the repo has no competing stack. Rules were not edited.

Override any of those in the Milestone 1 plan before coding if you disagree. Do not install PyTorch, OpenMM, or Vina in Milestone 1.

## Next task

Milestone 1, first green commit only:

1. Open a new chat. Read this file, `AGENTS.md`, `docs/ROADMAP.md`, and `docs/ARCHITECTURE.md`. Use Plan Mode and match the plan to Milestone 1 AC1–AC13 before coding.
2. Run `git status`. Confirm there is still no test suite.
3. Create `.venv` with `/usr/bin/python3 -m venv .venv`. Do not install into system Python.
4. Add only the backend skeleton: config, logging, error types, a capabilities module, and `GET /api/health`. Health must report the database, whether storage is writable, and RDKit, mkdssp, Vina, OpenMM, PyTorch, and GPU as real `{available, version, reason}` values.
5. Test it with `.venv/bin/python -m pytest`. Record the pass and fail counts in `docs/DEVELOPMENT_LOG.md`.
6. Commit that step. Then continue the Milestone 1 commit list in `docs/ROADMAP.md`. Do not build the frontend in the first commit.

## Files touched in kickoff

`AGENTS.md`, `docs/AUDIT.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `docs/SCIENTIFIC_VALIDATION.md`, `docs/KNOWN_LIMITATIONS.md`, `docs/DEVELOPMENT_LOG.md`, `docs/HANDOFF.md`.

Rules, slash commands, and `.cursorignore` were the previous commit and were not changed here.
