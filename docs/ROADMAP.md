# BEAI roadmap

Date: 2026-10-11. The codebase has no application. Milestones below are the order to build it. One chat per milestone, except Milestone 6, which is six chats. Each chat reads `docs/HANDOFF.md` first and rewrites it last. Commit at each green step. Do not start a later milestone from the kickoff chat.

Branch suggestion after this kickoff is merged: `m1-foundation`, then one branch per milestone. This kickoff branch is only rules and docs.

## Priority if the order changes

1. Milestone 1 foundation (health, upload, offline structure overview, persistence, reports, Protein Explorer).
2. `AnalysisResult` enforced by tests in that same milestone, before any second module.
3. Independent fixtures (synthetic peptide, then RCSB files checked against the entry pages).

Compound work, docking, safety retrieval, and models wait. They have nothing honest to attach to yet.

## Milestone 1 — functional scientific foundation

- Depends on: this kickoff.
- Chat: one. Plan Mode first. Acceptance is the Milestone 1 checklist in the prompt pack (AC1–AC13).
- Goal: upload a PDB or mmCIF, show measurements from that file, view it, save and reopen the analysis, download HTML, Markdown, and JSON reports. Offline after dependencies are installed.

Commit steps inside the chat:

1. Backend skeleton and `GET /api/health`.
2. SQLite models, Alembic, and structure upload.
3. `structure_overview` with tests.
4. Reports.
5. Frontend shell and dashboard.
6. Protein Explorer and 3Dmol.js viewer.
7. Playwright smoke test and docs.

Out of scope: docking, simulation, compounds, external APIs, ML, authentication, PDF, Docker.

Risks: the slice is large for one context window. Stop at a green commit boundary and rewrite `docs/HANDOFF.md` rather than pushing past a drifting chat. Biopython is required. RDKit is not. Download 1UBQ (PDB and mmCIF) and 4HHB (PDB) from `files.rcsb.org`; a HEAD of `1UBQ.pdb` returned 200 on 2026-10-11. If a later download fails, use only the synthetic fixture and record the gap. Do not type RCSB structures from memory.

## Milestone 2 — protein intelligence

- Depends on: Milestone 1 tests green.
- Chat: one. Commits: jobs, sequences, deeper structure analysis, comparison, pockets and benchmark, RCSB and UniProt retrieval, frontend.
- Goal: FASTA statistics, DSSP or Biotite P-SEA, SASA, contacts, hydrogen-bond estimates, superposition RMSD, a baseline pocket detector with a real benchmark, and public import with provenance.

Risks: `mkdssp` is absent, so P-SEA is the expected fallback until someone installs DSSP. fpocket is not assumed. The pocket method stays labelled unvalidated until `docs/SCIENTIFIC_VALIDATION.md` has the held-out numbers. Pre-register the tuning and test PDB IDs before tuning.

## Milestone 3 — compound intelligence

- Depends on: Milestone 2 committed.
- Chat: one. Commits: validation and descriptors, depiction and similarity, PubChem, ChEMBL, persistence and comparison, reports, frontend.
- Goal: RDKit sanitization, named descriptors, Tanimoto, and retrieved records kept distinct from calculated values.

Risks: RDKit is absent today. Check install size and licence before installing. If it is over about 500 MB, stop and ask. Without RDKit, compound routes return 503 and protein tests still pass. Confirm PubChem and ChEMBL endpoints in the current official docs. Never merge assays of different type or unit.

## Milestone 4 — drug discovery and docking

- Depends on: Milestone 3, plus Milestone 2 pockets for the binding-region input.
- Chat: one. Commits: capabilities, ligand and receptor prep, Vina runner and parser, pose checks, benchmarks, ranking, report, frontend.
- Goal: a real Vina run when the tool exists, and a clear 503 when it does not. No simulated pose.

Risks: `vina` is absent. Meeko, PDBFixer, or Open Babel may be required and may be large or awkward on this platform. Ask before a dependency over about 500 MB. Redocking success is ≤ 2.0 Å heavy-atom RMSD, reported with the actual rate, including failures.

## Milestone 5 — therapeutic safety evidence

- Depends on: Milestone 3. Docking is not required. Can follow Milestone 3 or Milestone 4.
- Chat: one. Commits: each source, then evidence model, comparison, report, frontend.
- Goal: source-linked evidence with mandatory categories. Not medical advice.

Risks: safety rule 50 stays binding. FAERS stays observational. Literature stays unclassified until a person sets a category. No dosing, no personal medication lists, no interaction verdicts. Verify openFDA, DailyMed, ChEMBL, Open Targets, PubMed, and Europe PMC docs before coding. Do not call a retired or licensed interaction API.

## Milestone 6 — advanced scientific AI

Prerequisites: Milestones 1–3 green. Docking-related work also needs Milestone 4. Sessions 6B–6F depend on 6A. Skip 6E unless generation is still wanted.

| Session | Chat goal | Extra risk |
| --- | --- | --- |
| 6A | Model registry, real RAM report, Model Laboratory | No weights at startup |
| 6B | ESM-2 8M embeddings and a rank-correlation benchmark | Check the model card licence and token limit. CPU only here |
| 6C | Solubility baselines, then a GNN only if it installs cleanly | Public dataset checksum and scaffold split saved before training |
| 6D | OpenMM minimization, then a hard-capped short simulation | OpenMM absent; no GPU. Ask if the install is over about 500 MB |
| 6E | Optional hypothesis generation with liability filters forced on | No objective that rewards toxicity |
| 6F | Declarative workflows over the services above | LLM steps off unless an env var enables them |

Weights stay under gitignored `models/`. Every prediction is `ml_prediction` and labelled not experimental. This machine has no NVIDIA GPU and roughly 4.9 GiB free RAM. Refuse a model whose declared need exceeds the machine.

## Dependency sketch

```text
kickoff → M1 → M2 → M3 → M4
                    M3 → M5
                    M1–M3 → 6A → 6B, 6C, 6D, 6E, 6F
                    M4 → docking steps inside 6F
```

## What not to pull forward

Authentication, PDF, Redis, Docker, Postgres, and custom model training are not on this roadmap. Planned UI entries have no buttons that pretend otherwise.
