# BEAI Agent Brief

BEAI (Biochemical Engineering AI) is a modular research platform for protein analysis, compound analysis, computational drug discovery and therapeutic-safety evidence review. It is research software, not a clinical tool.

## Non-negotiables (full text: .cursor/rules/00-beai-core.mdc)

- Never fabricate scientific data, citations, benchmarks, API responses, tool output or test results.
- Never mark work done until you ran its verification command and read the output.
- Optional tools may be missing. Degrade gracefully and report the real state via GET /api/health.
- Never give individualized medical advice (see .cursor/rules/50-safety-boundaries.mdc).

## Stack (existing repo tooling wins over these defaults)

- Backend: Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2 + Alembic, SQLite locally.
- Science: Biopython, Biotite, NumPy, SciPy, pandas, RDKit. Optional: AutoDock Vina, OpenMM, PyTorch.
- Frontend: React, TypeScript, Vite, 3Dmol.js viewer.
- Tests: pytest, Vitest, Playwright smoke test.

## Target layout (create only what the current milestone needs)

- backend/app/api/routes/ : thin FastAPI routers, no science here
- backend/app/schemas/ : Pydantic request/response models, including AnalysisResult
- backend/app/services/structure/ : parsing, metrics, secondary structure, SASA, contacts, pockets
- backend/app/services/sequence/ : FASTA parsing and sequence statistics
- backend/app/services/compounds/ : SMILES, descriptors, similarity, depiction
- backend/app/services/docking/, safety/, simulation/, reports/, models_registry/
- backend/app/data_access/ : one module per external source plus a shared HTTP client (timeouts, retries, cache)
- backend/app/db/ : SQLAlchemy models, session, Alembic migrations
- backend/app/jobs/ : job records and runner
- backend/app/core/ : config, logging, error types
- backend/tests/ and backend/tests/fixtures/ : tests and small redistributable fixtures
- frontend/src/ : pages, components, api client, viewer wrapper
- docs/ : ARCHITECTURE, ROADMAP, SCIENTIFIC_VALIDATION, KNOWN_LIMITATIONS, DEVELOPMENT_LOG, HANDOFF, AUDIT

## Commands (the kickoff chat replaces these with verified commands)

- Install backend: TODO
- Run backend: TODO
- Run frontend: TODO
- Run backend tests: TODO
- Run frontend tests: TODO
- Migrate database: TODO

## Shared result schema (AnalysisResult)

Every analysis, in every module, returns this envelope:

- analysis_id (uuid), kind, created_at (UTC ISO 8601), status: pending | running | succeeded | partial | failed | cancelled
- inputs: list of {role, filename or source_id, sha256, validation_status, validation_messages}
- methods: list of {name, software, version, parameters}
- measurements: list of {name, value, unit, origin, method, uncertainty?, source?}
  - origin is one of: experimental_record | database_reported | calculated | ml_prediction | user_supplied (database_reported = computed or curated by an external database, not measured or calculated by BEAI)
- evidence: list of {claim, category, sources}
  - category is one of: established | observational | computational_prediction | hypothesis | unclassified (literature awaiting human review)
  - each source has {title, identifier (DOI, PMID, accession), url, retrieved_at, license?}
- limitations, warnings: lists of plain strings
- skipped_stages: list of {stage, reason}; errors: list of {code, message}
- reproducibility: {software_versions, random_seed?, config_hash, platform}

Rule: an absent value is null plus a warning. Never 0, "N/A" or a default standing in for a measurement.

## Working agreements

- Sequence: plan, implement, run, fix, verify, document.
- One milestone per chat. Read docs/HANDOFF.md first and rewrite it last.
- Commit at each green step using conventional commit messages.
- Ask the user only about: credentials, deleting data, dependencies over about 500 MB, changing the database engine, licensing doubts, or contradictory requirements. Otherwise decide, record the decision in docs/DEVELOPMENT_LOG.md and continue.
