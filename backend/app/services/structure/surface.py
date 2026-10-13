"""SASA, residue contacts, and hydrogen-bond estimates.

SASA is Shrake-Rupley from Biopython: probe radius 1.4 angstrom, 100 points,
default Biopython atomic radii. Water residues are removed before the
calculation so crystal solvent does not define the reported area. Ligands
that remain in the model can still bury polymer surface.

Contacts are residue pairs whose closest heavy atoms are within 4.5 angstrom.
The residue itself is excluded.

Hydrogen bonds are a heavy-atom estimate: backbone N and O separated by at
least two sequence numbers, N...O between 2.5 and 3.5 angstrom, and angle
C-O...N at least 120 degrees when the carbonyl carbon is present. This is not
a hydrogen bond located from explicit hydrogen atoms.
"""

from __future__ import annotations

from typing import Any

import numpy

from backend.app.services.structure.geometry import angle_degrees, distance
from backend.app.services.structure.residues import ResidueRecord

SASA_PROBE_RADIUS = 1.4
SASA_N_POINTS = 100
CONTACT_CUTOFF = 4.5
HBOND_MIN = 2.5
HBOND_MAX = 3.5
HBOND_MIN_ANGLE = 120.0


def shrake_rupley(model: Any) -> tuple[float, dict[tuple[str, int, str], float]]:
    """Return total SASA and a per-residue map, both in square angstroms."""

    from Bio.PDB.SASA import ShrakeRupley

    calculator = ShrakeRupley(probe_radius=SASA_PROBE_RADIUS, n_points=SASA_N_POINTS)
    copied = model.copy()
    for chain in list(copied.get_chains()):
        for residue in list(chain.get_residues()):
            hetflag, _resseq, _icode = residue.id
            if hetflag == "W" or residue.get_resname().strip() in {"HOH", "WAT"}:
                chain.detach_child(residue.id)
    calculator.compute(copied, level="A")
    total = 0.0
    per_residue: dict[tuple[str, int, str], float] = {}
    for chain in copied.get_chains():
        chain_id = str(chain.id).strip()
        for residue in chain.get_residues():
            _het, resseq, icode = residue.id
            icode_text = "" if icode in {None, " "} else str(icode).strip()
            area = 0.0
            for atom in residue.get_atoms():
                area += float(getattr(atom, "sasa", 0.0))
            total += area
            per_residue[(chain_id, int(resseq), icode_text)] = area
    return total, per_residue


def residue_contacts(residues: list[ResidueRecord]) -> list[dict[str, Any]]:
    """Residue-residue heavy-atom contacts inside the cutoff."""

    polymer = [residue for residue in residues if residue.kind == "polymer"]
    heavy: list[tuple[int, tuple[float, float, float]]] = []
    for index, residue in enumerate(polymer):
        for atom in residue.atoms:
            if not atom.hydrogen:
                heavy.append((index, atom.coord))
    if not heavy:
        return []
    coords = numpy.array([item[1] for item in heavy], dtype=float)
    owners = numpy.array([item[0] for item in heavy], dtype=int)
    cutoff2 = CONTACT_CUTOFF * CONTACT_CUTOFF
    pairs: set[tuple[int, int]] = set()
    # Cell list on a grid of the cutoff so each atom visits only nearby cells.
    cell = CONTACT_CUTOFF
    buckets: dict[tuple[int, int, int], list[int]] = {}
    keys = numpy.floor(coords / cell).astype(int)
    for atom_index, key in enumerate(keys):
        buckets.setdefault((int(key[0]), int(key[1]), int(key[2])), []).append(atom_index)
    for (ix, iy, iz), members in buckets.items():
        neighbor_ids: list[int] = []
        for dx in (0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    if dx == 0 and dy < 0:
                        continue
                    if dx == 0 and dy == 0 and dz < 0:
                        continue
                    neighbor_ids.extend(buckets.get((ix + dx, iy + dy, iz + dz), []))
        if not neighbor_ids:
            continue
        left = numpy.array(members, dtype=int)
        right = numpy.array(neighbor_ids, dtype=int)
        # Compare each member with neighbor atoms in other residues.
        for atom_index in left:
            others = right[owners[right] != owners[atom_index]]
            if others.size == 0:
                continue
            delta = coords[others] - coords[atom_index]
            close = others[numpy.einsum("ij,ij->i", delta, delta) <= cutoff2]
            for other in close:
                a = int(owners[atom_index])
                b = int(owners[other])
                if a == b:
                    continue
                pairs.add((a, b) if a < b else (b, a))
    contacts: list[dict[str, Any]] = []
    for left_index, right_index in sorted(pairs):
        left = polymer[left_index]
        right = polymer[right_index]
        separation = None
        if left.chain_id == right.chain_id and left.icode == "" and right.icode == "":
            separation = abs(right.resseq - left.resseq)
        contacts.append(
            {
                "left": _label(left),
                "right": _label(right),
                "sequence_separation": separation,
            }
        )
    return contacts


def hydrogen_bond_estimates(residues: list[ResidueRecord]) -> list[dict[str, Any]]:
    """Backbone N...O estimates. Sequential neighbors are excluded."""

    donors: list[tuple[ResidueRecord, tuple[float, float, float]]] = []
    acceptors: list[tuple[ResidueRecord, tuple[float, float, float], tuple[float, float, float] | None]] = []
    for residue in residues:
        if residue.kind != "polymer":
            continue
        nitrogen = _atom(residue, "N")
        oxygen = _atom(residue, "O")
        carbon = _atom(residue, "C")
        if nitrogen is not None:
            donors.append((residue, nitrogen))
        if oxygen is not None:
            acceptors.append((residue, oxygen, carbon))
    bonds: list[dict[str, Any]] = []
    for donor, nitrogen in donors:
        for acceptor, oxygen, carbon in acceptors:
            if donor.chain_id == acceptor.chain_id and donor.icode == "" and acceptor.icode == "":
                if abs(donor.resseq - acceptor.resseq) < 2:
                    continue
            elif (
                donor.chain_id == acceptor.chain_id
                and donor.resseq == acceptor.resseq
                and donor.icode == acceptor.icode
            ):
                continue
            span = distance(nitrogen, oxygen)
            if span < HBOND_MIN or span > HBOND_MAX:
                continue
            angle = None
            if carbon is not None:
                try:
                    angle = angle_degrees(carbon, oxygen, nitrogen)
                except ValueError:
                    angle = None
                if angle is None or angle < HBOND_MIN_ANGLE:
                    continue
            bonds.append(
                {
                    "donor": _label(donor),
                    "acceptor": _label(acceptor),
                    "distance_angstrom": span,
                    "angle_c_o_n_degrees": angle,
                    "estimate": True,
                }
            )
    return bonds


def _atom(residue: ResidueRecord, name: str) -> tuple[float, float, float] | None:
    for atom in residue.atoms:
        if atom.name == name and not atom.hydrogen:
            return atom.coord
    return None


def _label(residue: ResidueRecord) -> dict[str, Any]:
    return {
        "chain_id": residue.chain_id,
        "resname": residue.name,
        "resseq": residue.resseq,
        "icode": residue.icode,
    }
