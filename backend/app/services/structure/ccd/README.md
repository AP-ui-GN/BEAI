# Chemical component reference

Downloaded 2026-10-11 from `https://files.rcsb.org/ligands/download/{ID}.cif` for the 20 standard amino acids plus MSE (selenomethionine).

`structure_overview` treats a component atom as required when its element is not H or D and `pdbx_leaving_atom_flag` is not Y. In these files that flag is Y for OXT, so a missing terminal OXT is not reported as an incomplete side chain.

These files are nomenclature for the completeness check. They are not experimental measurements. The application does not modify them at runtime.
