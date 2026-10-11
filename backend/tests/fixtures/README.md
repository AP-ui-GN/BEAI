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
