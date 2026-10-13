# BEAI

BEAI is local research software for protein coordinate files, sequences, compounds, docking, and sourced safety evidence. It uploads a PDB or mmCIF file, computes a structure overview (including DSSP or P-SEA, SASA, contacts, and backbone angles), shows it in a 3Dmol.js viewer, stores the analysis in SQLite, and downloads HTML, Markdown, and JSON reports. Sequences can be pasted or imported from UniProt. Pockets, chain comparison, and docking run as jobs. The Model Laboratory lists registered models and the live RAM report. No weights are loaded at startup.

It is not a clinical tool and does not give medical advice.

## Quick start

These commands were used to build this environment from an empty virtualenv. A second clone was not created. Verified with Python 3.12.3 and Node v22.23.3 / npm 10.9.9. If `node` and `npm` come from different installs, put the directory that contains `npm` first on `PATH`.

```bash
/usr/bin/python3 -m venv .venv
.venv/bin/python -m pip install -U pip
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m alembic -c backend/alembic.ini upgrade head
.venv/bin/uvicorn backend.app.main:app --host 127.0.0.1 --port 8731
```

In another terminal:

```bash
npm --prefix frontend install
npm --prefix frontend run dev
```

Open [http://127.0.0.1:8732](http://127.0.0.1:8732). The Vite server proxies `/api` to port 8731.

Copy `.env.example` to `.env` only if you need to change ports, the upload limit, or the database path.

## Tests

```bash
.venv/bin/python -m pytest
npm --prefix frontend test
npm --prefix frontend run e2e
```

The Playwright smoke test needs both servers running and the Chromium browser Playwright downloaded (`npx playwright install chromium` from `frontend/`). On this machine that browser cache unpacked to about 681 MB.

## Troubleshooting

- `GET /api/health` reports `degraded` and mentions `alembic_version` when the database has not been migrated. Run the Alembic command above.
- RDKit, Vina, OpenMM, PyTorch, fpocket, and GPU stay unavailable until those tools are installed. On this machine `mkdssp` 4.2.2 and Biotite are installed, so secondary structure uses DSSP. Without `mkdssp`, the same overview falls back to Biotite P-SEA and says so.
- Default `pytest` skips tests marked `network`. Run `.venv/bin/python -m pytest -m network` for the live RCSB and UniProt import.
- Uploads over the configured limit return HTTP 413. The default limit is 50 MB (`BEAI_MAX_UPLOAD_BYTES`).
- The HTML report escapes text from the file, including a `TITLE` that contains a script tag. Open reports as downloads, not as a place to paste untrusted HTML into the app.
