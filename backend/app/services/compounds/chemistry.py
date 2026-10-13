"""RDKit chemistry. Descriptors are named by the RDKit function that produced them.

Crippen MolLogP is an estimate. Property-filter counts are observations.
Nothing here is a drug-likeness, safety, or efficacy label.
"""

from __future__ import annotations

import hashlib
import json
import platform
import uuid
from datetime import UTC, datetime
from typing import Any

from backend.app.core.capabilities import probe_import
from backend.app.core.errors import CapabilityUnavailable, InvalidInput

MORGAN_RADIUS = 2
MORGAN_BITS = 2048


def require_rdkit() -> str:
    """Return the RDKit version or raise 503-shaped CapabilityUnavailable."""

    status = probe_import("rdkit", "RDKit")
    if not status["available"]:
        raise CapabilityUnavailable(
            status["reason"] or "RDKit is not installed. Compound routes need RDKit inside the project virtualenv."
        )
    return str(status["version"] or "unknown")


def parse_molecule(smiles: str, *, keep_largest_fragment: bool, max_heavy_atoms: int) -> dict[str, Any]:
    """Sanitize SMILES. Invalid input raises before any row is stored."""

    version = require_rdkit()
    from rdkit import Chem
    from rdkit.Chem import Descriptors, Lipinski, rdMolDescriptors

    text = smiles.strip()
    if not text:
        raise InvalidInput("SMILES is empty.")
    molecule = Chem.MolFromSmiles(text, sanitize=False)
    if molecule is None:
        raise InvalidInput("SMILES could not be parsed.")
    try:
        Chem.SanitizeMol(molecule)
    except Exception as exc:
        raise InvalidInput("SMILES failed RDKit sanitization.") from exc
    fragments = Chem.GetMolFrags(molecule, asMols=True)
    fragment_count = len(fragments)
    reduced = False
    if fragment_count > 1 and keep_largest_fragment:
        molecule = max(fragments, key=lambda item: item.GetNumHeavyAtoms())
        reduced = True
        fragment_count = 1
    heavy = molecule.GetNumHeavyAtoms()
    if heavy > max_heavy_atoms:
        raise InvalidInput(f"The molecule has {heavy} heavy atoms, above the limit of {max_heavy_atoms}.")
    canonical = Chem.MolToSmiles(molecule, canonical=True)
    inchi = None
    inchikey = None
    try:
        inchi = Chem.MolToInchi(molecule)
        inchikey = Chem.MolToInchiKey(molecule)
    except Exception:
        inchi = None
        inchikey = None
    if not inchikey:
        raise InvalidInput("RDKit could not produce an InChIKey for this molecule.")
    undefined = int(rdMolDescriptors.CalcNumUnspecifiedAtomStereoCenters(molecule))
    descriptors = {
        "MolWt": float(Descriptors.MolWt(molecule)),
        "ExactMolWt": float(Descriptors.ExactMolWt(molecule)),
        "MolLogP": float(Descriptors.MolLogP(molecule)),
        "TPSA": float(Descriptors.TPSA(molecule)),
        "NumHDonors": int(Lipinski.NumHDonors(molecule)),
        "NumHAcceptors": int(Lipinski.NumHAcceptors(molecule)),
        "NumRotatableBonds": int(Lipinski.NumRotatableBonds(molecule)),
        "RingCount": int(Lipinski.RingCount(molecule)),
        "NumAromaticRings": int(Lipinski.NumAromaticRings(molecule)),
        "HeavyAtomCount": int(Lipinski.HeavyAtomCount(molecule)),
        "FormalCharge": int(Chem.GetFormalCharge(molecule)),
        "FractionCSP3": float(Lipinski.FractionCSP3(molecule)),
    }
    lipinski_failures = []
    if descriptors["NumHDonors"] > 5:
        lipinski_failures.append("NumHDonors > 5")
    if descriptors["NumHAcceptors"] > 10:
        lipinski_failures.append("NumHAcceptors > 10")
    if descriptors["MolWt"] > 500:
        lipinski_failures.append("MolWt > 500")
    if descriptors["MolLogP"] > 5:
        lipinski_failures.append("MolLogP > 5")
    formula = rdMolDescriptors.CalcMolFormula(molecule)
    return {
        "rdkit_version": version,
        "canonical_smiles": canonical,
        "inchi": inchi,
        "inchikey": inchikey,
        "formula": formula,
        "fragment_count": fragment_count,
        "reduced_to_largest_fragment": reduced,
        "undefined_stereocenters": undefined,
        "descriptors": descriptors,
        "lipinski_observations": lipinski_failures,
        "molecule": molecule,
    }


def depiction_svg(smiles: str) -> str:
    """Return an SVG string. Callers must not insert it as HTML."""

    require_rdkit()
    from rdkit import Chem
    from rdkit.Chem.Draw import rdMolDraw2D

    molecule = Chem.MolFromSmiles(smiles)
    if molecule is None:
        raise InvalidInput("The stored SMILES could not be drawn.")
    drawer = rdMolDraw2D.MolDraw2DSVG(320, 220)
    drawer.DrawMolecule(molecule)
    drawer.FinishDrawing()
    return drawer.GetDrawingText()


def morgan_fingerprint(smiles: str):
    require_rdkit()
    from rdkit import Chem
    from rdkit.Chem import rdMolDescriptors

    molecule = Chem.MolFromSmiles(smiles)
    if molecule is None:
        raise InvalidInput("A stored SMILES could not be parsed for a fingerprint.")
    return rdMolDescriptors.GetMorganFingerprintAsBitVect(molecule, MORGAN_RADIUS, nBits=MORGAN_BITS)


def tanimoto(left: str, right: str) -> float:
    from rdkit import DataStructs

    return float(DataStructs.TanimotoSimilarity(morgan_fingerprint(left), morgan_fingerprint(right)))


def similarity_matrix(smiles: list[str]) -> list[list[float]]:
    if not 2 <= len(smiles) <= 20:
        raise InvalidInput("Similarity needs between 2 and 20 compounds.")
    size = len(smiles)
    matrix = [[0.0 for _ in range(size)] for _ in range(size)]
    for i in range(size):
        matrix[i][i] = 1.0
        for j in range(i + 1, size):
            value = tanimoto(smiles[i], smiles[j])
            matrix[i][j] = value
            matrix[j][i] = value
    return matrix


def match_smarts(smarts: str, smiles_list: list[tuple[str, str]]) -> list[str]:
    """Return compound ids whose canonical SMILES match ``smarts``."""

    require_rdkit()
    from rdkit import Chem

    query = Chem.MolFromSmarts(smarts)
    if query is None:
        raise InvalidInput("SMARTS could not be parsed.")
    hits = []
    for compound_id, smiles in smiles_list:
        molecule = Chem.MolFromSmiles(smiles)
        if molecule is not None and molecule.HasSubstructMatch(query):
            hits.append(compound_id)
    return hits


def analysis_payload(parsed: dict[str, Any], *, compound_id: str, input_smiles: str, sha256: str) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    measurements: list[dict[str, Any]] = [
        _calc("molecular_formula", parsed["formula"], None, "rdkit.Chem.rdMolDescriptors.CalcMolFormula"),
        _calc("fragment_count", parsed["fragment_count"], "1", "rdkit.Chem.GetMolFrags"),
        _calc("undefined_stereocenters", parsed["undefined_stereocenters"], "1", "CalcNumUnspecifiedAtomStereoCenters"),
        _calc("canonical_smiles", parsed["canonical_smiles"], None, "rdkit.Chem.MolToSmiles canonical=True"),
        _calc("inchi", parsed["inchi"], None, "rdkit.Chem.MolToInchi"),
        _calc("inchikey", parsed["inchikey"], None, "rdkit.Chem.MolToInchiKey"),
    ]
    units = {
        "MolWt": "dalton",
        "ExactMolWt": "dalton",
        "MolLogP": "1",
        "TPSA": "angstrom^2",
        "NumHDonors": "1",
        "NumHAcceptors": "1",
        "NumRotatableBonds": "1",
        "RingCount": "1",
        "NumAromaticRings": "1",
        "HeavyAtomCount": "1",
        "FormalCharge": "1",
        "FractionCSP3": "1",
    }
    for name, value in parsed["descriptors"].items():
        method = f"RDKit Descriptors.{name}" if name != "FormalCharge" else "rdkit.Chem.GetFormalCharge"
        if name == "MolLogP":
            method = "RDKit Descriptors.MolLogP (Crippen estimate)"
        measurements.append(_calc(name, value, units[name], method))
    measurements.append(
        _calc(
            "lipinski_property_filter_observations",
            parsed["lipinski_observations"],
            None,
            "Lipinski threshold counts. A property-filter observation, not a drug-likeness label.",
        )
    )
    parameters = {
        "morgan_radius": MORGAN_RADIUS,
        "morgan_bits": MORGAN_BITS,
        "keep_largest_fragment": parsed["reduced_to_largest_fragment"],
        "rdkit_version": parsed["rdkit_version"],
    }
    warnings = []
    if parsed["fragment_count"] > 1:
        warnings.append("The input has more than one fragment. It was not reduced to the largest fragment.")
    if parsed["reduced_to_largest_fragment"]:
        warnings.append("The caller asked to keep only the largest fragment.")
    return {
        "analysis_id": str(uuid.uuid4()),
        "kind": "compound_descriptors",
        "created_at": now,
        "status": "succeeded",
        "inputs": [
            {
                "role": "smiles",
                "filename": None,
                "source_id": compound_id,
                "sha256": sha256,
                "validation_status": "valid",
                "validation_messages": warnings,
            }
        ],
        "methods": [
            {
                "name": "compound_descriptors",
                "software": "RDKit",
                "version": parsed["rdkit_version"],
                "parameters": parameters,
            }
        ],
        "measurements": measurements,
        "evidence": [],
        "limitations": [
            "Descriptors are calculated by RDKit. They do not establish drug-likeness, efficacy, or safety.",
            "MolLogP is the Crippen estimate.",
            "Lipinski counts are property-filter observations, not a classification.",
        ],
        "warnings": warnings,
        "skipped_stages": [],
        "errors": [],
        "reproducibility": {
            "software_versions": {"python": platform.python_version(), "rdkit": parsed["rdkit_version"]},
            "random_seed": None,
            "config_hash": hashlib.sha256(json.dumps(parameters, sort_keys=True).encode()).hexdigest(),
            "platform": platform.platform(),
        },
        "details": {"input_smiles": input_smiles},
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
