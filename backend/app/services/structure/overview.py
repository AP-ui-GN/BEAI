"""structure_overview: header metadata and geometry computed from one coordinate file.

The first model is analyzed. Radius of gyration is the unweighted geometric Rg
of C-alpha atoms, in angstroms. Consecutive C-alpha distances above
``ca_break_threshold_angstrom`` are flagged as chain breaks. Incomplete
residues are those whose heavy-atom names, from the bundled chemical component
dictionary, are not all present. Terminal OXT is a leaving atom in that
dictionary and is not required.
"""

from __future__ import annotations

import hashlib
import json
import platform
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy
from Bio import __version__ as biopython_version
from Bio.PDB import MMCIFParser, PDBParser

from backend.app.services.structure.ccd import component_table
from backend.app.services.structure.geometry import bounding_box, distance, radius_of_gyration
from backend.app.services.structure.header import (
    read_author_metadata,
    read_missing_residues_mmcif,
    read_missing_residues_pdb,
    read_sequences,
)
from backend.app.services.structure.residues import ResidueRecord, residue_records

_LIMITATIONS = [
    (
        "This is a geometric and header summary of a coordinate file. "
        "It is not evidence of biological activity, binding, stability, or safety."
    ),
    ("Radius of gyration is the unweighted geometric Rg of C-alpha atoms, not a mass-weighted or hydrodynamic radius."),
    "Only the first model is analyzed when the file contains more than one.",
    (
        "Alternate locations are reduced to the highest-occupancy conformer before geometry and atom counts. "
        "Equal occupancies keep the alphabetically first altloc id."
    ),
    (
        "Side-chain completeness uses bundled wwPDB chemical component heavy atoms, "
        "excluding atoms flagged as leaving atoms (including OXT). "
        "Residue types outside that set are not judged."
    ),
    "Chain breaks are C-alpha distances above the configured threshold, not crystallographic annotations.",
    (
        "Author-reported title, method, resolution, R-free, and deposition date are copied from the file "
        "and are not checked against another database."
    ),
    (
        "Sequence agreement that is explained by missing residues compares residue-name multisets. "
        "It is not a residue-by-residue alignment."
    ),
    "This overview does not compute secondary structure, solvent-accessible surface, energies, or hydrogen bonds.",
]


def build_structure_overview(
    path: Path,
    structure_format: str,
    *,
    analysis_id: str,
    created_at: str,
    source_id: str,
    display_filename: str,
    sha256: str,
    ca_break_threshold_angstrom: float,
) -> dict[str, Any]:
    """Return an AnalysisResult dict for ``structure_overview``."""

    components = component_table()
    if structure_format == "pdb":
        structure = PDBParser(QUIET=True).get_structure(analysis_id, str(path))
        missing, missing_warnings = read_missing_residues_pdb(structure.header)
        has_model_records = any(line.startswith("MODEL") for line in path.read_text(encoding="latin-1").splitlines())
    elif structure_format == "mmcif":
        structure = MMCIFParser(QUIET=True).get_structure(analysis_id, str(path))
        missing, missing_warnings = read_missing_residues_mmcif(path)
        has_model_records = True
    else:
        raise ValueError(f"unsupported format {structure_format}")

    models = list(structure.get_models())
    if not models:
        raise ValueError("the structure has no models")
    model = models[0]
    residues, residue_warnings = residue_records(model, components)
    metadata = read_author_metadata(path, structure_format)
    sequences = read_sequences(path, structure_format)
    warnings = [*metadata.warnings, *missing_warnings, *residue_warnings]
    if len(models) > 1:
        warnings.append(f"{len(models)} models are present. Measurements use model index 0 only.")

    author_serial = getattr(model, "serial_num", None)
    if structure_format == "pdb" and not has_model_records:
        reported_serial = None
        warnings.append("The PDB file has no MODEL record. The only coordinate set was analyzed.")
    else:
        reported_serial = int(author_serial) if isinstance(author_serial, int) else None

    by_chain: dict[str, list[ResidueRecord]] = defaultdict(list)
    for residue in residues:
        by_chain[residue.chain_id].append(residue)
    sequence_by_chain = {item.chain_id: item for item in sequences}
    chain_ids = list(dict.fromkeys([*by_chain.keys(), *sequence_by_chain.keys()]))

    chain_rows: list[dict[str, Any]] = []
    sequence_rows: list[dict[str, Any]] = []
    composition: Counter[str] = Counter()
    unclassified: list[dict[str, Any]] = []
    incomplete: list[dict[str, Any]] = []
    ca_distances: list[dict[str, Any]] = []
    b_factors: list[dict[str, Any]] = []
    occupancies: list[dict[str, Any]] = []
    polymer_ca: list[tuple[float, float, float]] = []
    per_chain_rg: list[dict[str, Any]] = []

    for chain_id in chain_ids:
        chain_residues = by_chain.get(chain_id, [])
        polymer = [item for item in chain_residues if item.kind == "polymer"]
        waters = [item for item in chain_residues if item.kind == "water"]
        ligands = [item for item in chain_residues if item.kind == "ligand"]
        polymer.sort(key=lambda item: (item.resseq, item.icode))
        sequence = sequence_by_chain.get(chain_id)
        if sequence and sequence.declared_count not in {None, len(sequence.residue_names)}:
            warnings.append(
                f"Chain {chain_id} SEQRES declares {sequence.declared_count} residues "
                f"but {len(sequence.residue_names)} names were parsed."
            )
        observed_names = [item.name for item in polymer]
        unobserved_names = [
            item["resname"] for item in missing if item["chain_id"] == chain_id and item["reason"] == "unobserved"
        ]
        for residue in polymer:
            component = components.get(residue.name)
            if component is None:
                unclassified.append(
                    {
                        "chain_id": chain_id,
                        "resname": residue.name,
                        "resseq": residue.resseq,
                        "icode": residue.icode,
                    }
                )
                continue
            composition[residue.name] += 1
            heavy_present = {name for name in residue.present_atom_names if name not in _hydrogens(residue)}
            absent = sorted(component.heavy_atoms - heavy_present)
            if absent:
                incomplete.append(
                    {
                        "chain_id": chain_id,
                        "resname": residue.name,
                        "resseq": residue.resseq,
                        "icode": residue.icode,
                        "missing_atoms": absent,
                    }
                )
        chain_ca = [_ca(item) for item in polymer]
        chain_ca = [point for point in chain_ca if point is not None]
        missing_ca = [item for item in polymer if _ca(item) is None]
        for item in missing_ca:
            warnings.append(
                f"Residue {chain_id}:{item.resseq}{item.icode} {item.name} has no C-alpha atom "
                "and is omitted from C-alpha distances and the radius of gyration."
            )
        polymer_ca.extend(chain_ca)
        rg_value = radius_of_gyration(chain_ca)
        per_chain_rg.append(
            {
                "chain_id": chain_id,
                "radius_of_gyration_angstrom": rg_value,
                "ca_count": len(chain_ca),
            }
        )
        observed_with_ca = [item for item in polymer if _ca(item) is not None]
        for left, right in zip(observed_with_ca, observed_with_ca[1:], strict=False):
            left_ca = _ca(left)
            right_ca = _ca(right)
            assert left_ca is not None and right_ca is not None
            separation = None
            if left.icode == "" and right.icode == "":
                separation = right.resseq - left.resseq
            gap = separation != 1
            span = distance(left_ca, right_ca)
            ca_distances.append(
                {
                    "chain_id": chain_id,
                    "from_residue": _residue_label(left),
                    "to_residue": _residue_label(right),
                    "distance_angstrom": span,
                    "sequence_separation": separation,
                    "numbering_gap": gap,
                    "chain_break": span > ca_break_threshold_angstrom,
                }
            )
        atoms = [atom for residue in chain_residues for atom in residue.atoms]
        if atoms:
            b_factors.append({"chain_id": chain_id, **_stats([atom.bfactor for atom in atoms])})
            occupancies.append(
                {
                    "chain_id": chain_id,
                    **_stats([atom.occupancy for atom in atoms]),
                    "count_below_one": sum(1 for atom in atoms if atom.occupancy < 1),
                }
            )
        polymer_type = "nonpolymer"
        if polymer and any(components.get(item.name) for item in polymer):
            polymer_type = "polypeptide"
        elif polymer:
            polymer_type = "other"
        elif sequence and any(components.get(name) for name in sequence.residue_names):
            polymer_type = "polypeptide"
        chain_rows.append(
            {
                "chain_id": chain_id,
                "polymer": polymer_type != "nonpolymer",
                "polymer_type": polymer_type,
                "observed_polymer_residue_count": len(polymer),
                "seqres_residue_count": len(sequence.residue_names) if sequence else None,
                "water_residue_count": len(waters),
                "hetero_residue_count": len(ligands),
            }
        )
        sequence_rows.append(
            {
                "chain_id": chain_id,
                "source": sequence.source if sequence else None,
                "seqres_residue_names": sequence.residue_names if sequence else None,
                "observed_residue_names": observed_names,
                "seqres_sequence": _one_letter(sequence.residue_names, components) if sequence else None,
                "observed_sequence": _one_letter(observed_names, components),
                "seqres_residue_count": len(sequence.residue_names) if sequence else None,
                "observed_polymer_residue_count": len(polymer),
                "agreement": _agreement(
                    sequence.residue_names if sequence else None,
                    observed_names,
                    unobserved_names,
                ),
            }
        )

    if unclassified:
        shown = ", ".join(
            f"{item['chain_id']}:{item['resseq']}{item['icode']} {item['resname']}" for item in unclassified[:8]
        )
        extra = "" if len(unclassified) <= 8 else f" and {len(unclassified) - 8} more"
        warnings.append(
            "Completeness was not assessed for polymer residues outside the bundled "
            f"chemical component set: {shown}{extra}."
        )
    selected_atoms = [atom for residue in residues for atom in residue.atoms]
    hydrogen_count = sum(1 for atom in selected_atoms if atom.hydrogen)
    hetatm_count = sum(len(residue.atoms) for residue in residues if residue.kind != "polymer")
    water_atoms = sum(len(residue.atoms) for residue in residues if residue.kind == "water")
    if hydrogen_count == 0:
        warnings.append("No hydrogen atoms were found in the analyzed model.")
    altloc_rows = [
        {
            "chain_id": residue.chain_id,
            "resname": residue.name,
            "resseq": residue.resseq,
            "icode": residue.icode,
            **detail,
        }
        for residue in residues
        for detail in residue.altlocs
    ]
    if altloc_rows:
        warnings.append(f"{len(altloc_rows)} atoms have alternate locations. The highest-occupancy conformer was kept.")
    break_count = sum(1 for item in ca_distances if item["chain_break"])
    if break_count:
        warnings.append(f"{break_count} consecutive C-alpha pairs exceed {ca_break_threshold_angstrom} angstroms.")
    if missing:
        warnings.append(f"{len(missing)} missing or zero-occupancy residue rows were read from the file.")
    if incomplete:
        warnings.append(f"{len(incomplete)} residues are missing one or more expected heavy atoms.")

    ligand_groups: dict[str, dict[str, Any]] = {}
    for residue in residues:
        if residue.kind != "ligand":
            continue
        group = ligand_groups.setdefault(
            residue.name,
            {"resname": residue.name, "residue_count": 0, "chains": []},
        )
        group["residue_count"] += 1
        if residue.chain_id not in group["chains"]:
            group["chains"].append(residue.chain_id)
    ligands = [ligand_groups[key] for key in sorted(ligand_groups)]

    overall_rg = radius_of_gyration(polymer_ca)
    skipped: list[dict[str, str]] = []
    if overall_rg is None:
        skipped.append(
            {
                "stage": "radius_of_gyration",
                "reason": "Fewer than 2 C-alpha atoms are in the analyzed model.",
            }
        )
    box = bounding_box([atom.coord for atom in selected_atoms])
    observed_total = sum(row["observed_polymer_residue_count"] for row in chain_rows)
    seqres_values = [row["seqres_residue_count"] for row in chain_rows if row["polymer"]]
    if seqres_values and all(value is not None for value in seqres_values):
        seqres_total: int | None = sum(value for value in seqres_values if value is not None)
    else:
        seqres_total = None
        if any(row["polymer"] for row in chain_rows):
            warnings.append("At least one polymer chain has no SEQRES or mmCIF polymer sequence.")

    parameters = {
        "model_index": 0,
        "ca_break_threshold_angstrom": ca_break_threshold_angstrom,
        "altloc_selection": "highest occupancy, then alphabetically first altloc id",
        "radius_of_gyration": "unweighted C-alpha arithmetic mean",
        "completeness": "wwPDB CCD heavy atoms excluding leaving atoms",
        "ccd_table_sha256": components.table_sha256,
    }
    config_hash = hashlib.sha256(json.dumps(parameters, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    method_name = "structure_overview"
    calculated = "Calculated from the uploaded coordinate file by structure_overview."

    def experimental(name: str, value: Any, unit: str | None, source: str) -> dict[str, Any]:
        return {
            "name": name,
            "value": value,
            "unit": unit,
            "origin": "experimental_record",
            "method": source,
            "uncertainty": None,
            "source": "coordinate file header",
        }

    def calc(name: str, value: Any, unit: str | None, method: str) -> dict[str, Any]:
        return {
            "name": name,
            "value": value,
            "unit": unit,
            "origin": "calculated",
            "method": method,
            "uncertainty": None,
            "source": None,
        }

    measurements = [
        experimental("title", metadata.title, None, metadata.title_source),
        experimental(
            "experimental_method",
            metadata.experimental_method,
            None,
            metadata.method_source,
        ),
        experimental(
            "resolution",
            metadata.resolution_angstrom,
            "angstrom",
            metadata.resolution_source,
        ),
        experimental("r_free", metadata.r_free, "1", metadata.r_free_source),
        experimental(
            "deposition_date",
            metadata.deposition_date,
            None,
            metadata.deposition_source,
        ),
        calc("model_count", len(models), "1", calculated),
        calc("analyzed_model_index", 0, "1", "Zero-based index of the model passed to the parsers."),
        calc(
            "analyzed_model_serial",
            reported_serial,
            "1",
            "Author model number. Null for a PDB file with no MODEL record.",
        ),
        calc("chain_count", len(chain_rows), "1", calculated),
        calc("chains", chain_rows, "1", calculated),
        calc("residue_count_observed_polymer", observed_total, "1", calculated),
        calc(
            "residue_count_seqres",
            seqres_total,
            "1",
            "Count of residue names in SEQRES or the mmCIF polymer sequence.",
        ),
        calc(
            "amino_acid_composition",
            dict(sorted(composition.items())),
            "1",
            "Observed polymer residues whose names are in the bundled chemical component set.",
        ),
        calc("sequence_comparison", sequence_rows, None, calculated),
        calc(
            "atom_count_total",
            len(selected_atoms),
            "1",
            "Atoms after highest-occupancy altloc selection.",
        ),
        calc(
            "atom_count_heavy",
            sum(1 for atom in selected_atoms if not atom.hydrogen),
            "1",
            "Selected atoms whose element is not H or D.",
        ),
        calc("atom_count_hydrogen", hydrogen_count, "1", "Selected atoms with element H or D."),
        calc(
            "atom_count_hetatm",
            hetatm_count,
            "1",
            "Selected atoms in water and ligand residues. This count overlaps atom_count_water.",
        ),
        calc("atom_count_water", water_atoms, "1", "Selected atoms in water residues."),
        calc(
            "water_residue_count",
            sum(1 for residue in residues if residue.kind == "water"),
            "1",
            "Water residues (Biopython hetflag W, or residue names HOH and WAT). "
            "Not included in polymer residue counts.",
        ),
        calc(
            "ligand_inventory",
            ligands,
            "1",
            "HETATM residues that are not waters and not chemical-component polymer residues.",
        ),
        calc("alternate_locations", altloc_rows, "1", calculated),
        calc("missing_residues", missing, "1", "REMARK 465 or mmCIF _pdbx_unobs_or_zero_occ_residues."),
        calc(
            "incomplete_residues",
            incomplete,
            "1",
            "Expected heavy atoms absent from every altloc. OXT is not required.",
        ),
        calc(
            "radius_of_gyration_ca",
            {
                "overall_angstrom": overall_rg,
                "ca_count": len(polymer_ca),
                "per_chain": per_chain_rg,
            },
            "angstrom",
            "Unweighted geometric radius of gyration of C-alpha atoms. "
            "Center is the arithmetic mean. Rg is the root mean square distance from that center.",
        ),
        calc(
            "bounding_box",
            box,
            "angstrom",
            "Axis-aligned box of all selected atoms in the analyzed model.",
        ),
        calc(
            "ca_distances",
            ca_distances,
            "angstrom",
            f"Consecutive C-alpha distances. chain_break is true above {ca_break_threshold_angstrom} angstroms.",
        ),
        calc(
            "b_factor_by_chain",
            b_factors,
            "angstrom^2",
            "Minimum, maximum, and arithmetic mean of B-factors for selected atoms on each chain, "
            "including ligands and waters on that chain.",
        ),
        calc(
            "occupancy_by_chain",
            occupancies,
            "1",
            "Minimum, maximum, and arithmetic mean occupancy of selected atoms on each chain.",
        ),
    ]
    return {
        "analysis_id": analysis_id,
        "kind": "structure_overview",
        "created_at": created_at,
        "status": "succeeded",
        "inputs": [
            {
                "role": "structure",
                "filename": display_filename,
                "source_id": source_id,
                "sha256": sha256,
                "validation_status": "valid",
                "validation_messages": [],
            }
        ],
        "methods": [
            {
                "name": method_name,
                "software": "Biopython",
                "version": biopython_version,
                "parameters": parameters,
            }
        ],
        "measurements": measurements,
        "evidence": [],
        "limitations": list(_LIMITATIONS),
        "warnings": warnings,
        "skipped_stages": skipped,
        "errors": [],
        "reproducibility": {
            "software_versions": {
                "python": platform.python_version(),
                "biopython": biopython_version,
                "numpy": numpy.__version__,
            },
            "random_seed": None,
            "config_hash": config_hash,
            "platform": platform.platform(),
        },
    }


def _ca(residue: ResidueRecord) -> tuple[float, float, float] | None:
    for atom in residue.atoms:
        if atom.name == "CA" and not atom.hydrogen:
            return atom.coord
    return None


def _hydrogens(residue: ResidueRecord) -> set[str]:
    return {atom.name for atom in residue.atoms if atom.hydrogen}


def _residue_label(residue: ResidueRecord) -> dict[str, Any]:
    return {
        "resname": residue.name,
        "resseq": residue.resseq,
        "icode": residue.icode,
    }


def _one_letter(names: list[str], components) -> str:
    letters: list[str] = []
    for name in names:
        component = components.get(name)
        letters.append(component.one_letter if component and component.one_letter else "X")
    return "".join(letters)


def _agreement(seqres: list[str] | None, observed: list[str], unobserved: list[str]) -> str:
    if seqres is None:
        return "seqres_absent"
    if observed == seqres:
        return "identical"
    combined = Counter(observed)
    combined.update(unobserved)
    if combined == Counter(seqres) and len(observed) + len(unobserved) == len(seqres):
        return "explained_by_missing_residues"
    return "mismatch"


def _stats(values: list[float]) -> dict[str, float | int]:
    return {
        "atom_count": len(values),
        "minimum": min(values),
        "maximum": max(values),
        "mean": sum(values) / len(values),
    }


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
