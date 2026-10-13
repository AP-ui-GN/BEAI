# BEAI architecture

Date: 2026-10-13. Milestone 2 is implemented on `m2-protein`. The "Milestone 1 as built" section is unchanged history. The "Milestone 2 as built" section is what the code does now.

## Milestone 2 as built

Protein work adds an in-process job runner, sequence statistics, DSSP or P-SEA secondary structure, Shrake-Rupley SASA, contacts, hydrogen-bond estimates, C-alpha superposition, a baseline pocket detector, and RCSB/UniProt import. Optional tools that are still absent stay on `/api/health` with a reason. Pocket detection and comparison run as jobs. A missing fpocket install skips that stage and still runs the baseline detector.

Direct packages added for this milestone, and the licence metadata their wheels reported:

| Package | Version | Licence metadata | Notes |
| --- | --- | --- | --- |
| biotite | 1.6.0 | BSD-3-Clause | P-SEA fallback. The installed package directory is about 132 MB |
| biotraj | 1.2.2 | LGPL-2.1 | Pulled in by Biotite. Not imported by BEAI directly |
| httpx | 0.28.1 | BSD-3-Clause | Shared external HTTP client. Already present as a test dependency |

`mkdssp` 4.2.2 is the Ubuntu `dssp` package (installed size about 6.4 MB, BSD-2-Clause, homepage https://github.com/PDB-REDO/dssp). It is not a pip package. The project `.venv` is about 610 MB after RDKit.

RDKit 2025.9.1 (wheel reports BSD-3-Clause) is installed for compound routes. The `rdkit` package directory is about 73 MB. `import rdkit` reports version `2025.09.1`. fpocket is not installed.

## Milestone 1 as built

The browser talks only to FastAPI on `127.0.0.1:8731`. Vite on `127.0.0.1:8732` proxies `/api`. `structure_overview` runs inside the request and still writes an `Analysis` row through `pending` → `running` → `succeeded` or `failed`. Reports are Jinja2 HTML (autoescape on), Markdown, and JSON from the stored `AnalysisResult` only.

Direct Python packages, pinned to the versions pip installed, and the licence metadata those wheels reported:

| Package | Version | Licence metadata |
| --- | --- | --- |
| fastapi | 0.143.0 | MIT |
| uvicorn | 0.54.0 | BSD-3-Clause |
| pydantic | 2.14.1 | MIT |
| SQLAlchemy | 2.1.4 | MIT |
| alembic | 1.20.0 | MIT |
| biopython | 1.88 | Biopython licence agreement |
| Jinja2 | 3.1.6 | (wheel metadata field empty) |
| python-multipart | 0.0.32 | Apache-2.0 |
| numpy (via Biopython) | 2.5.4 | BSD-3-Clause AND others |

The project `.venv` is about 219 MB. Playwright's unpacked browser cache on this machine is about 681 MB (Chrome for Testing zip 191 MB, headless shell zip 120 MB, ffmpeg zip 2.2 MB). That unpacked size is above the roughly 500 MB ask-first line. It was measured after `npx playwright install chromium` finished. No PyTorch, OpenMM, or Vina was installed.

Node v22.23.3 and npm 10.9.9 from the same nvm prefix are the frontend toolchain. `node` on the default `PATH` is v22.14.0 and is not used for `npm` scripts.

## As-is at kickoff

There was no running system. `main` (`1c0b99b`) contains no files. The kickoff branch added agent rules and docs only.

What exists:

- `AGENTS.md` — agent brief, target layout, and verified "not present" commands
- `.cursor/rules/` — mission, backend, frontend, scientific, testing, and safety rules
- `.cursor/commands/` — reusable slash commands
- `.cursorignore` — `data/`, `models/`, `.venv/`, `node_modules/`, `.logs/`, `.env`
- `docs/` — this kickoff

What did not exist at kickoff: an API, a database, a frontend, a viewer, jobs, reports, fixtures, tests, CI, or a virtualenv. Milestone 1 added those except CI.

## Target architecture

A local research app. The browser talks only to a FastAPI process on `127.0.0.1`. Science lives in services. Routes validate, call a service, and return an `AnalysisResult`. SQLite stores metadata and result JSON. Structure files live on disk under server-generated UUID names, with path and sha256 on the row. Optional tools are probed, never required for import. Missing tools become `{available: false, version: null, reason}` on `GET /api/health` and HTTP 503 on the routes that need them.

```text
backend/app/api/routes/     thin routers
backend/app/schemas/        Pydantic v2 models, including AnalysisResult
backend/app/services/       structure, sequence, compounds, docking, safety,
                            simulation, reports, models_registry
backend/app/data_access/    one module per external source, shared HTTP client
backend/app/db/             SQLAlchemy 2 models, session, Alembic
backend/app/jobs/           job records and in-process runner (Milestone 2)
backend/app/core/           config, logging, errors, capabilities
backend/tests/fixtures/     synthetic peptide plus redistributable RCSB files
frontend/src/               pages, components, one API client, one viewer wrapper
```

Create only the directories the current milestone uses. Unbuilt areas are Planned pages with no actions.

Every analysis returns the `AnalysisResult` envelope in `AGENTS.md`. An absent measurement is null plus a warning. `database_reported` is part of the origin enum from the first schema, not a later patch.

Milestone 1 runs `structure_overview` in the request and still writes an `Analysis` row through `pending` → `running` → `succeeded` or `failed`. The in-process job runner arrives in Milestone 2 for pocket detection and comparison. Reports are rendered with Jinja2 (autoescape on) from the stored result only, as HTML, Markdown, and JSON.

### Proposed Milestone 1 files

Do not treat this list as already created.

- `pyproject.toml` — minimum backend dependencies, Python `>=3.11`
- `.venv/` — gitignored; create with `python3 -m venv .venv`
- `.env.example` — placeholders only
- `.gitignore` — `data/`, `.logs/`, `.venv/`, `node_modules/`, `.env`, `models/`
- `backend/app/main.py` — FastAPI app, CORS allowlist, bind `127.0.0.1`
- `backend/app/core/` — settings, logging, typed errors, capabilities
- `backend/app/api/routes/health.py` — `GET /api/health`
- `backend/app/db/` — `Structure`, `Analysis`, first Alembic revision
- `backend/app/api/routes/structures.py` and `analyses.py`
- `backend/app/services/structure/` — parse and `structure_overview`
- `backend/app/services/reports/` — HTML, Markdown, JSON
- `backend/tests/` — health, upload rejection, synthetic geometry, report equality
- `frontend/` — Vite, React, TypeScript, 3Dmol.js wrapper, Planned pages for unbuilt areas
- `README.md` — quick start written from commands that were actually run

Milestone 1 dependencies to consider, and nothing else up front: FastAPI, uvicorn, Pydantic v2, pydantic-settings, SQLAlchemy 2, Alembic, Biopython, Jinja2, python-multipart, pytest. Add the frontend toolchain and Playwright when that commit starts. Do not preinstall RDKit, Biotite, NumPy stacks beyond what Biopython needs, Vina, OpenMM, or PyTorch.

Pin the versions that `pip` and `npm` actually install. Do not copy version numbers from memory. Record each addition, its licence, and its size in the decision log below.

### Proposed commands

These are not verified. They are the commands Milestone 1 should create and then run. Until that happens, `AGENTS.md` stays on "not present".

```text
python3 -m venv .venv
.venv/bin/python -m pip install -U pip
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/uvicorn backend.app.main:app --host 127.0.0.1 --port 8731
npm --prefix frontend install
npm --prefix frontend run dev -- --host 127.0.0.1 --port 8732
.venv/bin/python -m pytest
npm --prefix frontend test
.venv/bin/python -m alembic -c backend/alembic.ini upgrade head
```

Start servers in the background with logs under `.logs/`. `node` on `PATH` is v22.14.0 and `npm` belongs to Node v22.23.3. The frontend commit should print both versions and pick one Node on purpose.

Suggested ports are 8731 (API) and 8732 (Vite) so they do not sit on 3000, 5173, or 8080. Put them in `.env.example`.

## Decision records

### Backend stack

- Decision: Python 3.12.3, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic.
- Alternatives: Django, Flask, a Node API.
- Reason: the repository has no existing tool, so the prompt-pack default wins. The checked `python3` is 3.12.3, which meets 3.11+. The science libraries BEAI needs are Python libraries.

### Database

- Decision: SQLite file for local research use.
- Alternatives: PostgreSQL now.
- Reason: one user, one machine, no existing database. Switching engine later is a question that must be asked before it happens. UUID primary keys and UTC timestamps keep a later move possible.

### 3D viewer

- Decision: 3Dmol.js inside one wrapper component.
- Alternatives: Mol*, NGL, a custom WebGL view.
- Reason: 3Dmol.js is the default for a reliable React integration in Milestone 1. Mol* is the upgrade path if cartoon quality or very large assemblies outgrow it. The wrapper is the only import site, so the swap stays local.

### Job runner

- Decision: in-process runner with status stored on a database row, starting in Milestone 2. Milestone 1 persists analysis status but does the work in the request.
- Alternatives: Celery, RQ, Redis from the start.
- Reason: there is no load to justify another service. Progress is a number only when the work can measure it; otherwise null. No timer-based progress.

### Report format

- Decision: HTML (Jinja2, autoescape on), Markdown, and JSON, all from the stored `AnalysisResult`.
- Alternatives: PDF in Milestone 1.
- Reason: PDF adds a heavy renderer. JSON makes the report-equals-API test straightforward. HTML must escape author text such as a PDB `TITLE` that contains a script tag.

### Package install

- Decision: a project `.venv` created from `/usr/bin/python3`, installs with pip. No uv and no conda.
- Alternatives: install uv, Miniconda, or use system site-packages.
- Reason: uv and conda are not installed. System pip must not receive project packages. Optional conda-forge tools (Vina, OpenMM) wait until the milestone that needs them, and only after a size and licence check.

### Result schema

- Decision: implement the full origin enum now, including `database_reported` and `ml_prediction`, even though Milestone 1 only emits `experimental_record` and `calculated`.
- Alternatives: add origins when later milestones need them.
- Reason: the envelope is the honesty contract. A second schema would let calculated and database-reported numbers sit in the same field unlabeled.
