# Test fixtures

## Synthetic peptide

`synthetic_peptide.pdb` is hand-built by `build_synthetic_peptide.py`. It is not a biological structure.

C-alpha atoms sit at x = 0, 3, and 8 angstroms. Residue A2 alanine has no CB. REMARK 465 lists GLY A 3, which is also in SEQRES and has no coordinates. CB on residue A1 has altloc A (occupancy 0.70, z = 1) and altloc B (occupancy 0.30, z = 2). One water (HOH A 101) sits at (20, 20, 20).

## RCSB entries

Downloaded 2026-10-11 from `https://files.rcsb.org/download/`. RCSB PDB data is CC0.

| File | sha256 |
| --- | --- |
| `1UBQ.pdb` | `d4a6812d8951cf6594e6a0763f089e35f5a80b62acb3c117b2c5565228a7b161` |
| `1UBQ.cif` | `056f98710cb2b36f633c45e41902a02eb446e82871da21ff2dd44f74a56ca0f6` |
| `4HHB.pdb` | `abf382e0fd84b53bd4c08b373d37c0d7fe9fbe1a9a9c3851b2f5f2fbbe627101` |

`rcsb_entry_snapshot.json` holds the counts and sequences copied the same day from the RCSB Data API (`https://data.rcsb.org/rest/v1/core/entry/{id}`, the polymer-entity routes, and the 4HHB nonpolymer-entity routes). Tests read that file. The application does not.

The HTML entry pages are client-rendered, so the counts were taken from the Data API that backs those entries rather than from memory.

## Redocking poses

`vina/redock/*.pdbqt` are AutoDock Vina 1.2.5 outputs from 2026-10-13. `vina/redock/results.json` is the table written by that run. `vina/redock/ccd/*.cif` are chemical-component files downloaded the same day from `https://files.rcsb.org/ligands/download/{ID}.cif`. RCSB PDB data is CC0.

| File | sha256 |
| --- | --- |
| `ACA.cif` | `4a980f2fa5e34750b3df2c9c5b23de8c7cee0769983899169a7a821eabc66201` |
| `BEN.cif` | `a7ce813cbbac599168d4772f635ae23d7c6edb4d83a9891ebabcbe9e8bb66849` |
| `BGC.cif` | `f5bb693508c257f731303e53d18fdcc03cd572bfce1d289c21ec1a2e76f3bb82` |
| `BTN.cif` | `9fff069dc9e0387d49c3ef62cab0867a10dae56274931a779fb87f377b9c11ea` |
| `FK5.cif` | `f953e9ee6171736f0d47d2129e25844842b41f799ed6fd16e02dd5907b63bd78` |
| `MID.cif` | `889658c8b8bf84c0cf12707c992be59e48e5cec02f6cb7f82654f61a287f82e7` |
| `MK1.cif` | `c1d46b02c24a3f7e6c089762a365c094078d9a00aee824131d75768d2805141a` |
| `MTX.cif` | `bed9ca70cb64fdfd313d5b203dc1eaebc9545d849e63ac7a27758c44692fdf75` |
| `RDF.cif` | `8a99c75cdfa1759b11daca4eb82c1644c3d09c189b7c2b74228821c0797e349c` |
| `STU.cif` | `97af6d3dd9f98e5a27d218b19d770d9a11d9467094a290f85b6412b6eb5d4339` |
