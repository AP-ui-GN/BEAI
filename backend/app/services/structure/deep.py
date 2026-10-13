"""Deeper structure sections attached to a structure_overview result.

Phi and psi are backbone dihedrals in degrees. Ramachandran bins are a coarse
geometric partition, not a MolProbity assessment. Relative SASA is not
reported because no maximum-accessibility table is cited.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from backend.app.services.structure.annotations import file_secondary_structure, residue_in_ranges
from backend.app.services.structure.geometry import dihedral_degrees
from backend.app.services.structure.residues import ResidueRecord
from backend.app.services.structure.secondary import HELIX_CODES, STRAND_CODES, assign_secondary_structure
from backend.app.services.structure.surface import (
    CONTACT_CUTOFF,
    HBOND_MAX,
    HBOND_MIN,
    HBOND_MIN_ANGLE,
    SASA_N_POINTS,
    SASA_PROBE_RADIUS,
    hydrogen_bond_estimates,
    residue_contacts,
    shrake_rupley,
)


def enrich_overview(
    result: dict[str, Any],
    residues: list[ResidueRecord],
    path: Path,
    structure_format: str,
    model: Any,
) -> dict[str, Any]:
    """Add calculated structure sections. Failures become skipped stages, not invented numbers."""

    warnings = list(result["warnings"])
    skipped = list(result["skipped_stages"])
    methods = list(result["methods"])
    measurements = list(result["measurements"])
    limitations = list(result["limitations"])
    polymer = [residue for residue in residues if residue.kind == "polymer"]
    details: dict[str, Any] = {}

    torsions = _torsions(polymer)
    measurements.append(
        _calc(
            "phi_psi_defined_count",
            sum(1 for item in torsions if item["phi_degrees"] is not None and item["psi_degrees"] is not None),
            "1",
            "Residues with both phi and psi. Terminals and chain breaks are null.",
        )
    )
    region_counts = Counter(item["ramachandran_region"] for item in torsions if item["ramachandran_region"])
    measurements.append(
        _calc(
            "ramachandran_region_counts",
            dict(sorted(region_counts.items())),
            "1",
            "Coarse geometric bins of phi and psi. Not a MolProbity Ramachandran validation.",
        )
    )
    details["ramachandran"] = {
        "bins": {
            "right_handed_helix_bin": "-140 <= phi <= -40 and -60 <= psi <= 40",
            "beta_bin": "-180 <= phi <= -45 and (60 <= psi <= 180 or -180 <= psi <= -170)",
            "left_handed_helix_bin": "40 <= phi <= 90 and 0 <= psi <= 80",
            "other": "any other defined phi and psi",
        },
        "residues": torsions,
    }
    limitations.append("Ramachandran bins are a coarse geometric summary. They are not a structure-validation score.")

    try:
        codes, method, ss_warnings = assign_secondary_structure(model, path, polymer)
        methods.append(method)
        warnings.extend(ss_warnings)
    except Exception:
        codes = {}
        warnings.append("Secondary structure could not be computed.")
        skipped.append({"stage": "secondary_structure", "reason": "DSSP and P-SEA both failed."})
    annotations = file_secondary_structure(path, structure_format)
    counts = Counter(codes.values())
    measurements.append(
        _calc(
            "secondary_structure_counts",
            dict(sorted(counts.items())),
            "1",
            "Counts of computed secondary-structure codes. DSSP uses H, G, I, E, B, T, S, and loop. "
            "P-SEA is mapped to H, E, and C.",
        )
    )
    disagreement = _disagreement(polymer, codes, annotations)
    measurements.append(
        _calc(
            "secondary_structure_disagreement",
            disagreement,
            "1",
            "Author HELIX and SHEET ranges compared with computed helix codes (H, G, I) and strand codes (E, B). "
            "The two definitions are not the same, so the counts are not expected to match.",
        )
    )
    details["secondary_structure"] = {"per_residue": codes_to_rows(codes), "file_annotations": annotations}
    limitations.append(
        "Computed secondary structure and depositor HELIX/SHEET records use different definitions and are both shown."
    )

    try:
        total, per_residue = shrake_rupley(model)
        measurements.append(
            _calc(
                "sasa_total",
                total,
                "angstrom^2",
                f"Biopython Shrake-Rupley, probe {SASA_PROBE_RADIUS} angstrom, n_points {SASA_N_POINTS}, "
                "default Biopython atomic radii. Water residues are excluded; other ligands are kept.",
            )
        )
        methods.append(
            {
                "name": "sasa",
                "software": "Biopython",
                "version": methods[0]["version"] if methods else None,
                "parameters": {
                    "algorithm": "Shrake-Rupley",
                    "probe_radius_angstrom": SASA_PROBE_RADIUS,
                    "n_points": SASA_N_POINTS,
                    "radii": "Bio.PDB.SASA default radii_dict",
                    "relative_sasa": "not reported; no maximum-accessibility table is cited",
                },
            }
        )
        details["sasa"] = {
            "probe_radius_angstrom": SASA_PROBE_RADIUS,
            "n_points": SASA_N_POINTS,
            "per_residue": [
                {
                    "chain_id": key[0],
                    "resseq": key[1],
                    "icode": key[2],
                    "sasa_angstrom2": value,
                }
                for key, value in sorted(per_residue.items())
            ],
        }
    except Exception:
        warnings.append("Solvent-accessible surface area could not be computed.")
        skipped.append({"stage": "sasa", "reason": "Shrake-Rupley failed."})
        per_residue = {}

    try:
        contacts = residue_contacts(residues)
    except Exception:
        contacts = []
        warnings.append("Residue contacts could not be computed.")
        skipped.append({"stage": "contacts", "reason": "The contact search failed."})
    measurements.append(
        _calc(
            "contact_pair_count",
            len(contacts),
            "1",
            f"Polymer residue pairs with a heavy-atom distance at or below {CONTACT_CUTOFF} angstrom.",
        )
    )
    details["contacts"] = {
        "cutoff_angstrom": CONTACT_CUTOFF,
        "atom_selection": "heavy atoms",
        "pairs": contacts,
    }

    try:
        bonds = hydrogen_bond_estimates(residues)
    except Exception:
        bonds = []
        warnings.append("Hydrogen-bond estimates could not be computed.")
        skipped.append({"stage": "hydrogen_bonds", "reason": "The estimate failed."})
    measurements.append(
        _calc(
            "hydrogen_bond_estimate_count",
            len(bonds),
            "1",
            f"Backbone N...O between {HBOND_MIN} and {HBOND_MAX} angstrom, sequence separation at least 2, "
            f"angle C-O...N at least {HBOND_MIN_ANGLE} degrees. Heavy-atom estimate, not an explicit hydrogen bond.",
        )
    )
    details["hydrogen_bonds"] = {
        "criterion": (
            f"N...O in [{HBOND_MIN}, {HBOND_MAX}] angstrom, |i-j| >= 2 on the same chain, "
            f"angle C-O-N >= {HBOND_MIN_ANGLE} degrees"
        ),
        "explicit_hydrogens": False,
        "bonds": bonds,
    }
    details["torsions"] = torsions
    result["measurements"] = measurements
    result["methods"] = methods
    result["warnings"] = warnings
    result["skipped_stages"] = skipped
    result["limitations"] = limitations
    result["details"] = details
    return result


def residue_table(path: Path, structure_format: str, chain_id: str | None) -> list[dict[str, Any]]:
    """Per-residue rows for one chain, or every chain when ``chain_id`` is null."""

    from Bio.PDB import MMCIFParser, PDBParser

    from backend.app.services.structure.ccd import component_table
    from backend.app.services.structure.residues import residue_records

    components = component_table()
    if structure_format == "pdb":
        structure = PDBParser(QUIET=True).get_structure("residues", str(path))
    elif structure_format == "mmcif":
        structure = MMCIFParser(QUIET=True).get_structure("residues", str(path))
    else:
        return []
    model = next(structure.get_models())
    residues, _warnings = residue_records(model, components)
    polymer = [residue for residue in residues if residue.kind == "polymer"]
    torsions = {(item["chain_id"], item["resseq"], item["icode"]): item for item in _torsions(polymer)}
    try:
        codes, _method, _warnings_ss = assign_secondary_structure(model, path, polymer)
    except Exception:
        codes = {}
    try:
        _total, sasa = shrake_rupley(model)
    except Exception:
        sasa = {}
    rows: list[dict[str, Any]] = []
    for residue in residues:
        if chain_id is not None and residue.chain_id != chain_id:
            continue
        key = (residue.chain_id, residue.resseq, residue.icode)
        torsion = torsions.get(key, {})
        rows.append(
            {
                "chain_id": residue.chain_id,
                "resname": residue.name,
                "resseq": residue.resseq,
                "icode": residue.icode,
                "kind": residue.kind,
                "phi_degrees": torsion.get("phi_degrees"),
                "psi_degrees": torsion.get("psi_degrees"),
                "ramachandran_region": torsion.get("ramachandran_region"),
                "secondary_structure": codes.get(key),
                "sasa_angstrom2": sasa.get(key),
            }
        )
    return rows


def codes_to_rows(codes: dict[tuple[str, int, str], str]) -> list[dict[str, Any]]:
    return [
        {"chain_id": key[0], "resseq": key[1], "icode": key[2], "code": value}
        for key, value in sorted(codes.items())
    ]


def _torsions(polymer: list[ResidueRecord]) -> list[dict[str, Any]]:
    index = {(residue.chain_id, residue.resseq, residue.icode): residue for residue in polymer}
    rows: list[dict[str, Any]] = []
    for residue in polymer:
        previous = index.get((residue.chain_id, residue.resseq - 1, residue.icode))
        nxt = index.get((residue.chain_id, residue.resseq + 1, residue.icode))
        phi = _phi(previous, residue)
        psi = _psi(residue, nxt)
        rows.append(
            {
                "chain_id": residue.chain_id,
                "resname": residue.name,
                "resseq": residue.resseq,
                "icode": residue.icode,
                "phi_degrees": phi,
                "psi_degrees": psi,
                "ramachandran_region": _region(phi, psi),
            }
        )
    return rows


def _phi(previous: ResidueRecord | None, residue: ResidueRecord) -> float | None:
    if previous is None:
        return None
    points = (_named(previous, "C"), _named(residue, "N"), _named(residue, "CA"), _named(residue, "C"))
    return _safe_dihedral(points)


def _psi(residue: ResidueRecord, nxt: ResidueRecord | None) -> float | None:
    if nxt is None:
        return None
    points = (_named(residue, "N"), _named(residue, "CA"), _named(residue, "C"), _named(nxt, "N"))
    return _safe_dihedral(points)


def _safe_dihedral(points: tuple[Any, Any, Any, Any]) -> float | None:
    if any(point is None for point in points):
        return None
    try:
        return dihedral_degrees(points[0], points[1], points[2], points[3])
    except ValueError:
        return None


def _named(residue: ResidueRecord, name: str) -> tuple[float, float, float] | None:
    for atom in residue.atoms:
        if atom.name == name and not atom.hydrogen:
            return atom.coord
    return None


def _region(phi: float | None, psi: float | None) -> str | None:
    if phi is None or psi is None:
        return None
    if -140 <= phi <= -40 and -60 <= psi <= 40:
        return "right_handed_helix_bin"
    if -180 <= phi <= -45 and (60 <= psi <= 180 or -180 <= psi <= -170):
        return "beta_bin"
    if 40 <= phi <= 90 and 0 <= psi <= 80:
        return "left_handed_helix_bin"
    return "other"


def _disagreement(
    polymer: list[ResidueRecord],
    codes: dict[tuple[str, int, str], str],
    annotations: dict[str, list[dict[str, Any]]],
) -> dict[str, int]:
    both_helix = dssp_only_helix = file_only_helix = 0
    both_strand = dssp_only_strand = file_only_strand = 0
    for residue in polymer:
        key = (residue.chain_id, residue.resseq, residue.icode)
        code = codes.get(key, "")
        in_helix = residue_in_ranges(residue.chain_id, residue.resseq, residue.icode, annotations["helices"])
        in_sheet = residue_in_ranges(residue.chain_id, residue.resseq, residue.icode, annotations["sheets"])
        computed_helix = code in HELIX_CODES
        computed_strand = code in STRAND_CODES
        if computed_helix and in_helix:
            both_helix += 1
        elif computed_helix:
            dssp_only_helix += 1
        elif in_helix:
            file_only_helix += 1
        if computed_strand and in_sheet:
            both_strand += 1
        elif computed_strand:
            dssp_only_strand += 1
        elif in_sheet:
            file_only_strand += 1
    return {
        "both_helix": both_helix,
        "computed_only_helix": dssp_only_helix,
        "file_only_helix": file_only_helix,
        "both_strand": both_strand,
        "computed_only_strand": dssp_only_strand,
        "file_only_strand": file_only_strand,
        "file_helix_ranges": len(annotations["helices"]),
        "file_sheet_ranges": len(annotations["sheets"]),
    }


def _calc(name: str, value: Any, unit: str | None, method: str) -> dict[str, Any]:
    return {
        "name": name,
        "value": value,
        "unit": unit,
        "origin": "calculated",
        "method": method,
        "uncertainty": None,
        "source": None,
    }
