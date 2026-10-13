"""Solubility training choices fixed before any test metric was computed.

The Delaney CSV checksum is from the file downloaded on 2026-10-13 from the
URL named in DeepChem's ``load_delaney``. The CSV has no licence line.
DeepChem's repository LICENSE, retrieved the same day, is MIT and covers the
software. The loader names the table as Delaney, J. Chem. Inf. Comput. Sci.
44 (2004) 1000-1005. No separate dataset licence was invented.
"""

from __future__ import annotations

DATASET_URL = "https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/delaney-processed.csv"
DATASET_SHA256 = "8c06a76f0c6487d29ab0f903e6a7a7139f189ab3c1178f159c8be8964602f189"
DATASET_BYTES = 96699
TARGET_COLUMN = "measured log solubility in mols per litre"
SMILES_COLUMN = "smiles"
SPLIT_SEED = 20261013
TEST_FRACTION = 0.2
RIDGE_ALPHA = 1.0
MORGAN_RADIUS = 2
MORGAN_BITS = 2048
APPLICABILITY_MAX_TANIMOTO = 0.3
BOOTSTRAP_SEED = 20261013
BOOTSTRAP_RESAMPLES = 1000
ENSEMBLE_SIZE = 5
GNN_EPOCHS = 20
GNN_HIDDEN = 32
GNN_LR = 0.01
REPRODUCTION_TOLERANCE = 1e-6
NOT_EXPERIMENTAL = "not experimental"
DESCRIPTOR_NAMES = (
    "MolWt",
    "MolLogP",
    "TPSA",
    "NumHDonors",
    "NumHAcceptors",
    "NumRotatableBonds",
    "RingCount",
)
