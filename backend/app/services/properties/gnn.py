"""Small GCN used beside the Ridge baselines. The shape was fixed before test metrics."""

from __future__ import annotations

import torch
from rdkit import Chem
from torch_geometric.data import Data
from torch_geometric.nn import GCNConv, global_mean_pool

from backend.app.services.properties.constants import GNN_HIDDEN


class SolubilityGCN(torch.nn.Module):
    """Two graph convolutions, mean pool, and one linear unit. Not tuned on the test split."""

    def __init__(self) -> None:
        super().__init__()
        self.conv1 = GCNConv(4, GNN_HIDDEN)
        self.conv2 = GCNConv(GNN_HIDDEN, GNN_HIDDEN)
        self.out = torch.nn.Linear(GNN_HIDDEN, 1)

    def forward(self, x, edge_index, batch):
        hidden = torch.relu(self.conv1(x, edge_index))
        hidden = torch.relu(self.conv2(hidden, edge_index))
        return self.out(global_mean_pool(hidden, batch)).squeeze(-1)


def molecule_graph(mol: Chem.Mol, measured: float | None = None) -> Data:
    """Atom features are scaled counts. Bonds are stored in both directions."""

    features = []
    for atom in mol.GetAtoms():
        features.append(
            [
                atom.GetAtomicNum() / 100.0,
                atom.GetDegree() / 6.0,
                atom.GetTotalNumHs() / 4.0,
                1.0 if atom.GetIsAromatic() else 0.0,
            ]
        )
    edges: list[list[int]] = []
    for bond in mol.GetBonds():
        begin = bond.GetBeginAtomIdx()
        end = bond.GetEndAtomIdx()
        edges.append([begin, end])
        edges.append([end, begin])
    if edges:
        edge_index = torch.tensor(edges, dtype=torch.long).t().contiguous()
    else:
        edge_index = torch.zeros((2, 0), dtype=torch.long)
    target = 0.0 if measured is None else measured
    return Data(
        x=torch.tensor(features, dtype=torch.float32),
        edge_index=edge_index,
        y=torch.tensor(target, dtype=torch.float32),
    )
