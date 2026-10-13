"""Baseline geometric pocket detector, LigSite-style.

A grid is placed over the heavy atoms. A voxel is protein if its centre is
within ``protein_radius_angstrom`` of any heavy atom, and a candidate if it is
not protein but is within ``shell_radius_angstrom``. For each candidate, seven
directions (the axes and the three-dimensional diagonals) are scanned. A
direction counts when protein is seen on both sides within ``scan_steps``
index steps. Candidates with at least ``min_psp_directions`` hits are
clustered by 6-connectivity and ranked by voxel volume.

This is a baseline geometric heuristic. It is not fpocket and it is not a
validated binding-site predictor until the benchmark in
docs/SCIENTIFIC_VALIDATION.md says so.

The first grid used protein_radius 1.7 angstrom and min_psp_directions 4.
On the tuning set that left the protein core unfilled, so the largest cluster
was the core rather than a surface cleft (3PTB ligand distance about 11
angstrom). protein_radius was then set to 2.5 angstrom and min_psp_directions
to 5 using only the tuning IDs. scan_steps stayed 8. Held-out IDs were not
used to choose these values.

Pre-registered sets, not to be swapped after looking at held-out scores:
tuning 3PTB, 1STP, 1HSG, 1FKF, 2PK4;
held-out 1AQ1, 1TLP, 2GBP, 4DFR, 1DWD.
Success distance is 4.0 angstrom from a top-3 pocket centroid to the ligand
heavy-atom centroid. The narrow claim is called validated only if at least
3 of the 5 held-out complexes meet that distance. Otherwise the label stays
benchmarked and not validated.
"""

from __future__ import annotations

from collections import deque
from typing import Any

import numpy

from backend.app.services.structure.residues import ResidueRecord

POCKET_PARAMETERS: dict[str, float | int] = {
    "grid_spacing_angstrom": 1.0,
    "protein_radius_angstrom": 2.5,
    "shell_radius_angstrom": 5.0,
    "scan_steps": 8,
    "min_psp_directions": 5,
    "min_cluster_voxels": 8,
    "lining_distance_angstrom": 5.0,
    "top_k": 3,
    "max_pockets": 15,
    "ligand_success_distance_angstrom": 4.0,
    "ligand_contact_distance_angstrom": 4.0,
}

# Crystallographic buffer and ion names are not treated as the bound ligand.
BUFFER_RESIDUES = frozenset(
    {
        "HOH",
        "WAT",
        "SO4",
        "PO4",
        "GOL",
        "EDO",
        "PEG",
        "ACT",
        "DMS",
        "ACE",
        "FMT",
        "EOH",
        "MPD",
        "BME",
        "TRS",
        "MES",
        "CIT",
        "IPA",
        "PG4",
        "PGE",
        "1PE",
        "NO3",
        "CL",
        "NA",
        "MG",
        "CA",
        "ZN",
        "K",
        "MN",
        "FE",
        "CU",
        "NI",
        "CO",
        "CD",
        "HG",
        "IOD",
        "BR",
    }
)

DIRECTIONS = (
    (1, 0, 0),
    (0, 1, 0),
    (0, 0, 1),
    (1, 1, 0),
    (1, 0, 1),
    (0, 1, 1),
    (1, 1, 1),
)

METHOD_LABEL = (
    "baseline geometric heuristic. The narrow top-3, 4.0 angstrom claim met the "
    "pre-registered held-out bar (3 of 5) on the 2026-10-13 benchmark. "
    "Not a general binding-site validator. Failures are in docs/SCIENTIFIC_VALIDATION.md."
)


def detect_pockets(residues: list[ResidueRecord], progress: Any | None = None) -> dict[str, Any]:
    """Return ranked pockets for polymer heavy atoms. Ligands are not part of the protein grid."""

    polymer = [residue for residue in residues if residue.kind == "polymer"]
    coords = [
        atom.coord
        for residue in polymer
        for atom in residue.atoms
        if not atom.hydrogen
    ]
    if len(coords) < 4:
        return _empty("Fewer than 4 polymer heavy atoms.")
    points = numpy.array(coords, dtype=float)
    spacing = float(POCKET_PARAMETERS["grid_spacing_angstrom"])
    shell = float(POCKET_PARAMETERS["shell_radius_angstrom"])
    protein_radius = float(POCKET_PARAMETERS["protein_radius_angstrom"])
    origin = points.min(axis=0) - shell
    shape = numpy.ceil((points.max(axis=0) + shell - origin) / spacing).astype(int) + 1
    if int(shape.prod()) > 2_000_000:
        return _empty("The pocket grid would exceed 2,000,000 voxels, so detection was skipped.")
    occupied, near = _mark_voxels(points, origin, shape, spacing, protein_radius, shell)
    if progress is not None:
        progress(0.45)
    psp = _psp(occupied, int(POCKET_PARAMETERS["scan_steps"]))
    buried = (psp >= int(POCKET_PARAMETERS["min_psp_directions"])) & near & ~occupied
    clusters = _clusters(buried, int(POCKET_PARAMETERS["min_cluster_voxels"]))
    if progress is not None:
        progress(0.75)
    pockets = []
    lining_distance = float(POCKET_PARAMETERS["lining_distance_angstrom"])
    for voxels in clusters:
        centers = origin + voxels.astype(float) * spacing
        centroid = centers.mean(axis=0)
        volume = float(len(voxels) * spacing**3)
        mean_psp = float(psp[voxels[:, 0], voxels[:, 1], voxels[:, 2]].mean())
        lining = _lining(polymer, centers, centroid, lining_distance)
        pockets.append(
            {
                "volume_angstrom3": volume,
                "mean_psp": mean_psp,
                "centroid_angstrom": centroid.tolist(),
                "voxel_count": int(len(voxels)),
                "lining_residues": lining,
            }
        )
    pockets.sort(key=lambda item: (item["volume_angstrom3"], item["mean_psp"]), reverse=True)
    limit = int(POCKET_PARAMETERS["max_pockets"])
    ranked = []
    for rank, pocket in enumerate(pockets[:limit], start=1):
        pocket["rank"] = rank
        pocket["in_top_k"] = rank <= int(POCKET_PARAMETERS["top_k"])
        ranked.append(pocket)
    return {
        "label": METHOD_LABEL,
        "parameters": dict(POCKET_PARAMETERS),
        "pockets": ranked,
        "warning": None,
    }


def select_ligand(residues: list[ResidueRecord]) -> ResidueRecord | None:
    """Largest non-buffer ligand residue by heavy-atom count. Ties keep file order."""

    candidates = [
        residue
        for residue in residues
        if residue.kind == "ligand" and residue.name not in BUFFER_RESIDUES
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda residue: sum(1 for atom in residue.atoms if not atom.hydrogen),
    )


def ligand_centroid(residue: ResidueRecord) -> numpy.ndarray | None:
    coords = [atom.coord for atom in residue.atoms if not atom.hydrogen]
    if not coords:
        return None
    return numpy.array(coords, dtype=float).mean(axis=0)


def score_ligand(
    pockets: list[dict[str, Any]],
    residues: list[ResidueRecord],
    ligand: ResidueRecord,
) -> dict[str, Any]:
    """Distance of the ligand centroid to the top-k pockets, and residue recovery."""

    centre = ligand_centroid(ligand)
    if centre is None:
        return {"ligand_resname": ligand.name, "distance_angstrom": None, "success": False, "recovery": None}
    top = [pocket for pocket in pockets if pocket.get("in_top_k")]
    if not top:
        return {
            "ligand_resname": ligand.name,
            "chain_id": ligand.chain_id,
            "resseq": ligand.resseq,
            "distance_angstrom": None,
            "success": False,
            "recovery": None,
            "contact_residue_count": 0,
        }
    distances = [float(numpy.linalg.norm(numpy.array(pocket["centroid_angstrom"]) - centre)) for pocket in top]
    best_index = int(numpy.argmin(distances))
    best = top[best_index]
    cutoff = float(POCKET_PARAMETERS["ligand_success_distance_angstrom"])
    contact_cutoff = float(POCKET_PARAMETERS["ligand_contact_distance_angstrom"])
    contacting = _ligand_contacts(residues, ligand, contact_cutoff)
    lining_keys = {
        (item["chain_id"], item["resseq"], item["icode"]) for item in best["lining_residues"]
    }
    recovered = [key for key in contacting if key in lining_keys]
    recovery = (len(recovered) / len(contacting)) if contacting else None
    return {
        "ligand_resname": ligand.name,
        "chain_id": ligand.chain_id,
        "resseq": ligand.resseq,
        "distance_angstrom": distances[best_index],
        "success": distances[best_index] <= cutoff,
        "recovery": recovery,
        "contact_residue_count": len(contacting),
        "top_k_distances_angstrom": distances,
    }


def _mark_voxels(
    points: numpy.ndarray,
    origin: numpy.ndarray,
    shape: numpy.ndarray,
    spacing: float,
    protein_radius: float,
    shell: float,
) -> tuple[numpy.ndarray, numpy.ndarray]:
    occupied = numpy.zeros(tuple(int(value) for value in shape), dtype=bool)
    near = numpy.zeros_like(occupied)
    radius_steps = int(numpy.ceil(shell / spacing))
    offsets: list[tuple[int, int, int, float]] = []
    for dx in range(-radius_steps, radius_steps + 1):
        for dy in range(-radius_steps, radius_steps + 1):
            for dz in range(-radius_steps, radius_steps + 1):
                dist = spacing * float(numpy.sqrt(dx * dx + dy * dy + dz * dz))
                if dist <= shell:
                    offsets.append((dx, dy, dz, dist))
    nx, ny, nz = occupied.shape
    for point in points:
        center = numpy.rint((point - origin) / spacing).astype(int)
        for dx, dy, dz, dist in offsets:
            ix = int(center[0] + dx)
            iy = int(center[1] + dy)
            iz = int(center[2] + dz)
            if ix < 0 or iy < 0 or iz < 0 or ix >= nx or iy >= ny or iz >= nz:
                continue
            if dist <= protein_radius:
                occupied[ix, iy, iz] = True
            else:
                near[ix, iy, iz] = True
    near &= ~occupied
    return occupied, near


def _psp(occupied: numpy.ndarray, steps: int) -> numpy.ndarray:
    count = numpy.zeros(occupied.shape, dtype=numpy.uint8)
    for direction in DIRECTIONS:
        positive = numpy.zeros(occupied.shape, dtype=bool)
        negative = numpy.zeros(occupied.shape, dtype=bool)
        forward = occupied
        backward = occupied
        for _step in range(steps):
            forward = _shift(forward, direction)
            backward = _shift(backward, tuple(-value for value in direction))
            positive |= forward
            negative |= backward
        count += (positive & negative).astype(numpy.uint8)
    return count


def _shift(grid: numpy.ndarray, direction: tuple[int, int, int]) -> numpy.ndarray:
    """Return grid pulled so that out[i] = previous[i + direction], false off the edge."""

    output = numpy.zeros_like(grid)
    dx, dy, dz = direction
    src = (
        slice(max(dx, 0), grid.shape[0] + min(dx, 0)),
        slice(max(dy, 0), grid.shape[1] + min(dy, 0)),
        slice(max(dz, 0), grid.shape[2] + min(dz, 0)),
    )
    dst = (
        slice(max(-dx, 0), grid.shape[0] + min(-dx, 0)),
        slice(max(-dy, 0), grid.shape[1] + min(-dy, 0)),
        slice(max(-dz, 0), grid.shape[2] + min(-dz, 0)),
    )
    output[dst] = grid[src]
    return output


def _clusters(buried: numpy.ndarray, minimum: int) -> list[numpy.ndarray]:
    visited = numpy.zeros(buried.shape, dtype=bool)
    found: list[numpy.ndarray] = []
    xs, ys, zs = numpy.where(buried)
    for start in zip(xs.tolist(), ys.tolist(), zs.tolist(), strict=True):
        if visited[start]:
            continue
        queue: deque[tuple[int, int, int]] = deque([start])
        visited[start] = True
        members: list[tuple[int, int, int]] = []
        while queue:
            current = queue.popleft()
            members.append(current)
            cx, cy, cz = current
            for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                nxt = (cx + dx, cy + dy, cz + dz)
                if (
                    nxt[0] < 0
                    or nxt[1] < 0
                    or nxt[2] < 0
                    or nxt[0] >= buried.shape[0]
                    or nxt[1] >= buried.shape[1]
                    or nxt[2] >= buried.shape[2]
                    or visited[nxt]
                    or not buried[nxt]
                ):
                    continue
                visited[nxt] = True
                queue.append(nxt)
        if len(members) >= minimum:
            found.append(numpy.array(members, dtype=int))
    return found


def _lining(
    polymer: list[ResidueRecord],
    centers: numpy.ndarray,
    centroid: numpy.ndarray,
    distance_cutoff: float,
) -> list[dict[str, Any]]:
    radius = float(numpy.linalg.norm(centers - centroid, axis=1).max()) if len(centers) else 0.0
    limit = radius + distance_cutoff
    rows: list[dict[str, Any]] = []
    cutoff2 = distance_cutoff * distance_cutoff
    for residue in polymer:
        atoms = numpy.array([atom.coord for atom in residue.atoms if not atom.hydrogen], dtype=float)
        if len(atoms) == 0:
            continue
        if float(numpy.linalg.norm(atoms.mean(axis=0) - centroid)) > limit + 4.0:
            continue
        # Compare to the centroid first, then to cluster points only when close.
        if float(numpy.min(numpy.sum((atoms - centroid) ** 2, axis=1))) > (limit + 2.0) ** 2:
            continue
        delta = atoms[:, None, :] - centers[None, :, :]
        if float(numpy.min(numpy.sum(delta * delta, axis=2))) <= cutoff2:
            rows.append(
                {
                    "chain_id": residue.chain_id,
                    "resname": residue.name,
                    "resseq": residue.resseq,
                    "icode": residue.icode,
                }
            )
    return rows


def _ligand_contacts(
    residues: list[ResidueRecord],
    ligand: ResidueRecord,
    cutoff: float,
) -> list[tuple[str, int, str]]:
    ligand_atoms = numpy.array([atom.coord for atom in ligand.atoms if not atom.hydrogen], dtype=float)
    keys: list[tuple[str, int, str]] = []
    cutoff2 = cutoff * cutoff
    for residue in residues:
        if residue.kind != "polymer":
            continue
        atoms = numpy.array([atom.coord for atom in residue.atoms if not atom.hydrogen], dtype=float)
        if len(atoms) == 0:
            continue
        delta = atoms[:, None, :] - ligand_atoms[None, :, :]
        if float(numpy.min(numpy.sum(delta * delta, axis=2))) <= cutoff2:
            keys.append((residue.chain_id, residue.resseq, residue.icode))
    return keys


def _empty(reason: str) -> dict[str, Any]:
    return {
        "label": METHOD_LABEL,
        "parameters": dict(POCKET_PARAMETERS),
        "pockets": [],
        "warning": reason,
    }
