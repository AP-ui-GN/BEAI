# Scientific validation plan

Date: 2026-10-11. No BEAI method has been run. This file has no results, no residue counts, and no benchmark scores. Fill numbers only after the command that produced them has been run, and name the independent source of each expected value.

A method presented as accurate stays labelled unvalidated until its section below contains dataset provenance, the metric, and a real result.

## Structure overview (Milestone 1)

| Check | Dataset | Metric | Acceptance | Result |
| --- | --- | --- | --- | --- |
| Radius of gyration | Analytic: two equal points 3.0 Å apart | unweighted Rg | 1.5 Å, tolerance 1e-6 | passed 2026-10-11 (`.venv/bin/python -m pytest`, 31 passed, 0 failed). The two-point case returned 1.5 within 1e-6 |
| Distances, missing side-chain atom, REMARK 465 | Hand-built synthetic peptide with known coordinates | exact match to the hand calculation | exact | passed in the same run. C-alpha distances 3.0 Å and 5.0 Å; the 5.0 Å pair is a chain break at the 4.5 Å threshold; residue A2 is missing CB; REMARK 465 GLY A 3 is reported. Three C-alpha atoms at x = 0, 3, 8 give Rg = sqrt(98/9) |
| Chain and residue counts | 1UBQ PDB and mmCIF, downloaded from `files.rcsb.org` | counts equal each other and the RCSB entry page | exact match to the page read at implementation time | passed in the same run. Chain A has 76 polymer residues in both formats, matching `rcsb_sample_sequence_length` 76 and `deposited_polymer_monomer_count` 76 from the RCSB Data API snapshot taken 2026-10-11 (`backend/tests/fixtures/rcsb_entry_snapshot.json`). Water residue count 58 matches `deposited_solvent_atom_count`. Atom count 660 and hydrogen count 0 match the entry. R-free is null because the file records it as missing; that null is not a calculated substitute |
| Multichain, heme, waters | 4HHB PDB from `files.rcsb.org` | chains A–D, HEM in the ligand inventory, waters separate | exact match to the RCSB entry page | passed in the same run. Observed polymer counts A 141, B 146, C 141, D 146 (total 574). HEM is on chains A–D (4 residues). PO4 is on chains B and D (2 residues). Water residue count 221, kept out of the polymer counts. Counts match the same snapshot |

Do not write the 1UBQ or 4HHB counts into the test from memory. Open the entry page, record the URL and the date it was read, then put that count in the test.

Provenance for the RCSB files: RCSB PDB data is CC0. Store the download URL and retrieval date in `backend/tests/fixtures/README.md`.

## Sequence statistics (Milestone 2)

| Check | Dataset | Metric | Acceptance | Result |
| --- | --- | --- | --- | --- |
| Length and mass | Ubiquitin FASTA copied from the 1UBQ record, not typed from memory | length; average mass | length 76; mass within 1 Da of a named independent calculator | not run |
| Invalid alphabet | synthetic illegal characters | rejection | no sequence stored | not run |

State the mass convention in the test comment (average mass, terminal water included) and the pI method.

## Deeper structure (Milestone 2)

| Check | Dataset | Metric | Acceptance | Result |
| --- | --- | --- | --- | --- |
| Secondary structure | 1UBQ | helix and strand content versus file `HELIX` and `SHEET` records | algorithm name recorded; any difference explained here | not run |
| SASA | 1UBQ | total SASA, two independent implementations | inside a tolerance written down before looking at the 1UBQ comparison | not run |
| Superposition | analytic copies | C-alpha RMSD | self-fit and rotated-copy fit near 0 (tolerance 1e-6 Å); refuse below 3 pairs | not run |

Secondary structure uses DSSP if `mkdssp` exists, otherwise Biotite P-SEA. Today `mkdssp` is absent, so the planned algorithm is P-SEA until that changes. File-annotated helices and sheets are shown separately either way.

SASA plan: Shrake-Rupley, probe radius 1.4 Å, radii set named in the method record. Relative SASA only if the maximum-accessibility table is cited.

## Pocket detector (Milestone 2)

Run on 2026-10-13 with the frozen parameters in `backend/app/services/structure/pockets.py`: grid 1.0 Å, protein radius 2.5 Å, shell 5.0 Å, 8 scan steps, at least 5 of 7 LigSite-style directions, clusters of at least 8 voxels, lining distance 5.0 Å. The first settings (protein radius 1.7 Å, 4 directions) left the protein core unfilled on the tuning set, so those two values were changed using only the tuning IDs. Held-out IDs were not used for that change.

Success was pre-registered as a top-3 pocket centroid within 4.0 Å of the ligand heavy-atom centroid. The ligand is the largest non-buffer HET residue. Recovery is the fraction of polymer residues within 4.0 Å of that ligand that also line the closest top-3 pocket. The narrow claim is treated as met on the held-out set only because 3 of 5 succeeded. That is not a general binding-site validation.

Files were downloaded from `https://files.rcsb.org/download/{ID}.pdb` on 2026-10-13. Checksums are in `backend/tests/test_pockets.py`.

| Split | PDB | Ligand | Distance (Å) | Success | Recovery |
| --- | --- | --- | --- | --- | --- |
| tuning | 3PTB | BEN | 0.565 | yes | 1.000 |
| tuning | 1STP | BTN | 2.245 | yes | 0.750 |
| tuning | 1HSG | MK1 | 0.675 | yes | 1.000 |
| tuning | 1FKF | FK5 | 5.460 | no | 0.643 |
| tuning | 2PK4 | ACA | 12.835 | no | 0.000 |
| held-out | 1AQ1 | STU | 2.111 | yes | 1.000 |
| held-out | 1TLP | RDF | 4.595 | no | 0.933 |
| held-out | 2GBP | BGC | 2.878 | yes | 1.000 |
| held-out | 4DFR | MTX | 5.388 | no | 0.938 |
| held-out | 1DWD | MID | 2.892 | yes | 0.722 |

Tuning success 3/5. Held-out success 3/5. Failures are 1FKF, 2PK4, 1TLP, and 4DFR. fpocket was not on PATH, so it did not contribute.

## Compounds (Milestone 3)

Reference values from the milestone contract. They are checks for a future RDKit build, not outputs of this repository.

| Input | Formula | Molecular weight | Result |
| --- | --- | --- | --- |
| Aspirin `CC(=O)Oc1ccccc1C(=O)O` | C9H8O4 | 180.16 | not run |
| Caffeine `CN1C=NC2=C1C(=O)N(C(=O)N2C)C` | C8H10N4O2 | 194.19 | not run |
| Ethanol `CCO` | C2H6O | 46.07 | not run |

When the tests are written, confirm each value with RDKit and a second source named in the test comment. Also require: self-Tanimoto 1.0, a symmetric matrix, aspirin closer to salicylic acid than to caffeine, salts left as multi-fragment unless the caller asks, and a mocked network failure that stores nothing.

Descriptors are named by their RDKit function. Crippen logP is an estimate. No drug-likeness label.

## Docking (Milestone 4)

| Check | Dataset | Metric | Acceptance | Result |
| --- | --- | --- | --- | --- |
| Redock | 5–10 ligand-bound complexes, tuning split from held-out, IDs recorded first | heavy-atom RMSD to the crystal pose, symmetry handled | success counted at ≤ 2.0 Å; report the rate and the Vina version | not run |
| Score versus activity | one target, one ChEMBL standard type and unit | rank correlation with a bootstrap interval | report the number even if it is weak | not run |
| Seeds | same inputs | score reproduction | same seed within a tolerance written down before the run; spread reported | not run |

A docking score is not an affinity. Parser tests use a Vina output file captured from a real run, not a hand-typed score.

## Safety evidence (Milestone 5)

This module is not a clinical model and has no accuracy target.

Validation is provenance tests: label text stored verbatim, FAERS always observational, similarity off-targets always `computational_prediction` and "unverified", literature `unclassified` until a person sets a category, and no interaction pair that is absent from retrieved text. Network failure stores no report content.

## Models and simulation (Milestone 6)

No results.

- Embeddings: on a small curated pair set, rank correlation between embedding cosine similarity and pairwise alignment identity, with a bootstrap interval. No functional or structural claim.
- Solubility: public set such as ESOL, checksum and licence recorded, scaffold split saved with its seed, baseline beside any neural model, RMSE, MAE, and R-squared with bootstrap intervals.
- OpenMM: minimization lowers potential energy; a short NVE run on a small system stays inside a pre-registered energy drift; a thermostatted run has mean temperature near the target inside a pre-registered tolerance; same seed and platform reproduce inside a pre-registered tolerance. Labels: minimization is not dynamics; a short simulation is not evidence of stability, binding, or efficacy.
- Generation, only if requested: validity, uniqueness, novelty, diversity, and filter pass rate, with liability filters on.

Stub tests do not count as model-quality results.
