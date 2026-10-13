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
| Length and mass | Ubiquitin FASTA built from 1UBQ SEQRES and the bundled chemical-component one-letter codes | length; average mass | length 76; mass within 1 Da of an independent elemental sum | passed 2026-10-13. Length 76. Biopython average mass 8564.736 Da. Independent sum of free-amino-acid formulas (C 12.0107, H 1.00794, N 14.0067, O 15.9994, S 32.065) minus (n-1) water molecules was 8564.737 Da. Difference 0.00086 Da |
| Invalid alphabet | synthetic illegal characters | rejection | no sequence stored | passed in the same suite. `ACDE1` returns HTTP 422 and the sequence list stays empty |

State the mass convention in the test comment (average mass, terminal water included) and the pI method.

## Deeper structure (Milestone 2)

| Check | Dataset | Metric | Acceptance | Result |
| --- | --- | --- | --- | --- |
| Secondary structure | 1UBQ | helix and strand content versus file `HELIX` and `SHEET` records | algorithm name recorded; any difference explained here | passed 2026-10-13. mkdssp 4.2.2. Codes: H 12, G 6, I 0, E 24, B 2, T 12, S 4, P 4, loop 12. File HELIX ranges are 23–34 (class 1) and 56–59 (class 5). Overlap: both helix 15, computed-only helix 3, file-only helix 1; both strand 24, computed-only strand 2, file-only strand 9. DSSP uses hydrogen-bond patterns. The file records are depositor annotations, including a 3-10 helix class that DSSP can mark G rather than H. The counts are not expected to match |
| SASA | 1UBQ | total SASA, two independent implementations | relative difference at most 20% of the Biopython total, chosen before the comparison | passed 2026-10-13. Biopython Shrake-Rupley, probe 1.4 Å, 100 points, waters excluded: 4893.04 Å². Biotite `sasa` with ProtOr radii, probe 1.4 Å, 100 points, waters excluded: 4834.72 Å². Relative difference 1.19% |
| Superposition | analytic copies and 1UBQ against itself | C-alpha RMSD | self-fit and rotated-copy fit near 0 (tolerance 1e-6 Å); refuse below 3 pairs | passed 2026-10-13. Analytic self-fit and a 90-degree rotated copy were within 1e-6 Å. 1UBQ chain A against itself was within 1e-6 Å with 76 pairs. A two-residue chain failed the job and named the 3-pair minimum |

Secondary structure uses DSSP if `mkdssp` exists, otherwise Biotite P-SEA. On 2026-10-13 `mkdssp` 4.2.2 was on PATH, so 1UBQ used DSSP. File-annotated helices and sheets are shown separately either way.

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
| Aspirin `CC(=O)Oc1ccccc1C(=O)O` | C9H8O4 | 180.16 | passed 2026-10-13. RDKit 2025.09.1 `Descriptors.MolWt` rounded to 2 decimals |
| Caffeine `CN1C=NC2=C1C(=O)N(C(=O)N2C)C` | C8H10N4O2 | 194.19 | passed in the same run |
| Ethanol `CCO` | C2H6O | 46.07 | passed in the same run |

When the tests are written, confirm each value with RDKit and a second source named in the test comment. Also require: self-Tanimoto 1.0, a symmetric matrix, aspirin closer to salicylic acid than to caffeine, salts left as multi-fragment unless the caller asks, and a mocked network failure that stores nothing.

Descriptors are named by their RDKit function. Crippen logP is an estimate. No drug-likeness label.

## Docking (Milestone 4)

| Check | Dataset | Metric | Acceptance | Result |
| --- | --- | --- | --- | --- |
| Redock | 3PTB / BEN, Vina 1.2.5, exhaustiveness 4, seed 1, 20 Å box on the crystal ligand centroid | docking score from the real PDBQT | parser scores equal the REMARK lines | passed 2026-10-13. Captured file `backend/tests/fixtures/vina/3ptb_ben_seed1.pdbqt` modes −6.073, −5.062, −4.839 kcal/mol. A second seed-1 run differed by 0.006 kcal/mol. Acceptance window for that spread is 0.05 kcal/mol |
| Redock RMSD | 10 ligand-bound RCSB complexes already split for the pocket benchmark. Vina 1.2.5, exhaustiveness 8, seed 1, 1 mode, 20 Å box on the crystal ligand heavy-atom centroid | heavy-atom RMSD to the crystal pose, symmetry handled by RDKit `CalcRMS`, success at or below 2.0 Å | record every complex, including failures | run 2026-10-13. Tuning success 3/5. Held-out success 2/5. Table below |
| Score versus activity | one target, one ChEMBL standard type and unit | rank correlation with a bootstrap interval | report the number even if it is weak | not run |
| Seeds | same inputs | score reproduction | same seed within a tolerance written down before the run; spread reported | not run |

A docking score is not an affinity. Parser tests use a Vina output file captured from a real run, not a hand-typed score.

Redocking RMSD, command `.venv/bin/python -m backend.app.services.docking.redock` on 2026-10-13. AutoDock Vina v1.2.5. The split is the pocket-detector split and was not changed after these distances. The ligand is the largest residue of the named type in the file. Bond orders come from the CACTVS canonical SMILES in the RCSB chemical-component file downloaded the same day from `https://files.rcsb.org/ligands/download/{ID}.cif`. Meeko wrote the ligand PDBQT from those crystal coordinates plus hydrogens. The receptor dropped waters and that residue name, then `mk_prepare_receptor.py`. RDKit `CalcRMS` compared heavy atoms in the crystal frame and accounted for symmetry. It did not superimpose the pose onto the crystal ligand. `AssignBondOrdersFromTemplate` warned "More than one matching pattern found - picking one" on complexes that produced a pose. Poses are in `backend/tests/fixtures/vina/redock/`. A preparation failure has no pose and no RMSD.

| Split | PDB | Ligand | Heavy-atom RMSD (Å) | Success at 2.0 Å | Vina score (kcal/mol) |
| --- | --- | --- | --- | --- | --- |
| tuning | 3PTB | BEN | 0.38634036044964726 | yes | -6.196 |
| tuning | 1STP | BTN | 0.6946867472014318 | yes | -7.04 |
| tuning | 1HSG | MK1 | 0.42136429418226423 | yes | -11.567 |
| tuning | 1FKF | FK5 | 7.823345721495985 | no | -6.548 |
| tuning | 2PK4 | ACA | not computed | no | not computed |
| held-out | 1AQ1 | STU | 0.3478932885966152 | yes | -13.841 |
| held-out | 1TLP | RDF | 8.278915104289972 | no | -8.39 |
| held-out | 2GBP | BGC | 0.19162198907988706 | yes | -7.357 |
| held-out | 4DFR | MTX | not computed | no | not computed |
| held-out | 1DWD | MID | not computed | no | not computed |

2PK4 failed in Meeko receptor preparation: `matched with excess inter-residue bond(s): A:32`. 4DFR failed the same way: `matched with excess inter-residue bond(s): B:131`. 1DWD failed with `CGLN       heavy_miss=9 heavy_excess=0 H_excess=[] bond_miss=set() bond_excess=set()`. Those three have no RMSD. 1FKF and 1TLP docked and missed 2.0 Å. The Vina score column is a docking score, not an affinity. Tuning success 3/5. Held-out success 2/5.

## Safety evidence (Milestone 5)

This module is not a clinical model and has no accuracy target.

Validation is provenance tests: label text stored verbatim, FAERS always observational, similarity off-targets always `computational_prediction` and "unverified", literature `unclassified` until a person sets a category, and no interaction pair that is absent from retrieved text. Network failure stores no report content.

DailyMed is the fallback when openFDA label retrieval fails. The warfarin search and SPL saved on 2026-10-13 are `backend/tests/fixtures/safety/dailymed_warfarin_spls.json` and `dailymed_warfarin_spl.xml`. Section text is copied from the SPL. Europe PMC search responses saved the same day are `europepmc_aspirin.json` and `europepmc_oa.json`. The aspirin record is not open access, so its abstract is not stored. The open-access record keeps `abstractText` and licence `cc by`. The Open Targets VKORC1 response is `opentargets_vkorc1.json`. Safety liabilities and disease scores are unclassified. A failed request stores no row.

## Models and simulation (Milestone 6)

### Embeddings (session 6B)

Dataset: SEQRES one-letter chains from local RCSB fixtures `1UBQ.pdb`, `4HHB.pdb`, `pockets/3PTB.pdb`, `pockets/1STP.pdb`, `pockets/2GBP.pdb`, and `pockets/1HSG.pdb`. At most two chains per file. A chain is kept when every residue maps to a one-letter code other than X, the length is at least 20, and the length is at most `max_position_embeddings` 1026 minus 2. That rule was written in `backend/app/services/embeddings/benchmark.py` before the coefficient below was computed.

Kept chains from the run on 2026-10-13: 1UBQ A 76, 4HHB A 141, 4HHB B 146, 3PTB A 223, 1STP A 159, 2GBP A 309, 1HSG A 99, 1HSG B 99. Eight sequences, 28 pairs.

Identity is `identity_including_gaps` from Biopython `PairwiseAligner` global alignment, BLOSUM62, open gap -10, extend -1: identical non-gap letters divided by alignment columns. Embedding cosine uses the mean of the ESM-2 8M last hidden state over residue tokens. Spearman uses SciPy `spearmanr`. The interval is the 2.5 and 97.5 percentiles of 1000 resamples with seed 20261013. All 1000 resamples were finite.

| Metric | Result |
| --- | --- |
| Spearman | 0.6990131578947367 |
| 2.5 percentile | 0.3788637829986782 |
| 97.5 percentile | 0.8820213682475236 |

Command: `.venv/bin/python -m pytest --override-ini addopts= -m model backend/tests/test_embeddings_model.py` — 1 passed. This is rank agreement with sequence identity on that set. It is not a functional or structural result.

### Solubility (session 6C)

Dataset: `delaney-processed.csv` from `https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/delaney-processed.csv`, the URL in DeepChem's `load_delaney` as retrieved 2026-10-13. sha256 `8c06a76f0c6487d29ab0f903e6a7a7139f189ab3c1178f159c8be8964602f189`, 96699 bytes, 1128 data rows. The CSV has no licence line. DeepChem's repository LICENSE is MIT for the software. The loader names the table as Delaney, J. Chem. Inf. Comput. Sci. 44 (2004) 1000-1005. The target column is `measured log solubility in mols per litre`. The column `ESOL predicted log solubility in mols per litre` was not used as a feature or as a prediction.

Split, chosen before fitting: Murcko scaffolds kept together, scaffolds shuffled with numpy Generator seed 20261013, test side filled until at least 20 percent of rows. Result of that split: 902 train, 226 test, 0 rows dropped. Ridge `alpha` 1.0 was not tuned. Morgan fingerprints are radius 2 and 2048 bits from `GetMorganGenerator`. The GCN is two layers, hidden size 32, 20 epochs, Adam learning rate 0.01, seed 20261013, and was not tuned on the test split. Bootstrap: 1000 resamples, seed 20261013, 2.5 and 97.5 percentiles. All 1000 resamples were finite for every metric below.

| Model | RMSE | MAE | R-squared |
| --- | --- | --- | --- |
| Descriptor Ridge | 1.3217993772506413 (1.147560194604866 to 1.4920541722551173) | 1.0004937427916745 (0.8907326010644745 to 1.1141110380395272) | 0.5985128816471968 (0.45973007459714554 to 0.7074329222377606) |
| Morgan Ridge | 1.6696791869919676 (1.506008911536875 to 1.8300778122281194) | 1.3029135097542737 (1.1760270767204246 to 1.4366200664112465) | 0.3593709962979724 (0.1757942096236605 to 0.4941057951191802) |
| Two-layer GCN | 2.5347372633569814 (2.3179658213153536 to 2.7474698037745178) | 2.056036578614957 (1.8600800380376539 to 2.264292208255532) | -0.4764081172372039 (-0.7456244760034777 to -0.2633770633818176) |

Intervals are the bootstrap percentiles. A second run with the same seed matched RMSE within 1e-6. The GCN R-squared is negative on this split: it did worse than the mean of the test labels. That result is the one the run produced. None of these numbers are experimental solubilities.

### OpenMM (session 6D)

Platforms reported by OpenMM 8.6.1 on this machine: Reference and CPU. CUDA, OpenCL, and Metal were not in that list.

Preparation is PDBFixer 1.12.0 at pH 7.0: missing residues, nonstandard residues, heterogen removal, missing atoms, hydrogens. Force field files `amber14-all.xml` and `implicit/gbn2.xml`, nonbonded method NoCutoff, constraints HBonds. CPU platform with `OPENMM_CPU_THREADS=1`.

Minimization on 1UBQ, 5 iterations, lowered the potential energy (the automated test asserts final < initial). A separate 20-iteration probe the same day went from -328.93633723496714 kJ/mol to -8331.638644503953 kJ/mol. Minimization is not molecular dynamics.

NVE: 20 steps, 1 fs, Verlet, zero initial velocities, after 20 minimization iterations. The pre-registered relative total-energy drift bound was 0.02. It was not stable. One run was 0.0004987123454089311 (E0 -10170.949423790193 kJ/mol, E1 -10176.021801832367 kJ/mol). An earlier run the same day was 0.08066315438678218 (E0 -694.7754278681138, E1 -750.818205470382). The 0.02 bound is not treated as met.

Langevin: 15 steps, 1 fs, seed 7, velocities drawn with that seed, after 15 minimization iterations. Mean kinetic temperature 260.1331467073965 K, inside the pre-registered window 150 K to 450 K. Two runs on the same prepared system differed by 1.6878309150943096 kJ/mol in final total energy. The pre-registered 1.0 kJ/mol reproduction bound was missed. Unseeded runs earlier were hundreds to thousands of kJ/mol apart.

A short simulation is not evidence of stability, binding, or efficacy.

### Generation (session 6E)

BRICS recombination records validity, uniqueness, novelty, diversity, and filter pass rate on each request, with the seed. Those values are calculated from that request. They are not a fixed model-quality benchmark. Every displayed structure is a computational hypothesis: unsynthesized, unvalidated.

- Embeddings: on a small curated pair set, rank correlation between embedding cosine similarity and pairwise alignment identity, with a bootstrap interval. No functional or structural claim.
- Solubility: public set such as ESOL, checksum and licence recorded, scaffold split saved with its seed, baseline beside any neural model, RMSE, MAE, and R-squared with bootstrap intervals.
- OpenMM: minimization lowers potential energy; a short NVE run on a small system stays inside a pre-registered energy drift; a thermostatted run has mean temperature near the target inside a pre-registered tolerance; same seed and platform reproduce inside a pre-registered tolerance. Labels: minimization is not dynamics; a short simulation is not evidence of stability, binding, or efficacy.
- Generation, only if requested: validity, uniqueness, novelty, diversity, and filter pass rate, with liability filters on.

Stub tests do not count as model-quality results.
