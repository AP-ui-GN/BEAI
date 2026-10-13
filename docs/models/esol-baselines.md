# esol-baselines

Aqueous log solubility models for the Delaney table. Predictions are not experimental measurements.

- Source URL: `https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/delaney-processed.csv`
- sha256: `8c06a76f0c6487d29ab0f903e6a7a7139f189ab3c1178f159c8be8964602f189`
- The CSV has no licence line. DeepChem's software LICENSE retrieved 2026-10-13 is MIT. The loader cites Delaney, J. Chem. Inf. Comput. Sci. 44 (2004) 1000-1005.
- Target: `measured log solubility in mols per litre`. The published ESOL prediction column is not a feature.
- Split seed 20261013, Murcko scaffolds kept together, about 20 percent test: 902 train, 226 test.
- Models: Ridge on seven named RDKit descriptors; Ridge on Morgan radius 2, 2048 bits; a two-layer GCN (hidden 32, 20 epochs, learning rate 0.01).
- Held-out numbers are in `docs/SCIENTIFIC_VALIDATION.md`. The GCN R-squared on this split is negative.
- Applicability: maximum Morgan Tanimoto to the training set below 0.3 is out of domain.
- Fingerprint uncertainty is the standard deviation of five bootstrap refits of the training set. The GCN has no ensemble uncertainty.
