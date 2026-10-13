"""BRICS recombination. Liability filters cannot be turned off.

Every displayed SMILES has passed RDKit sanitization. The hypothesis label is
fixed. Objectives may only be similarity to a reference or a property range.
"""

from __future__ import annotations

import hashlib
import json
import platform
import uuid
from datetime import UTC, datetime
from typing import Any

import numpy
from rdkit import Chem
from rdkit import __version__ as rdkit_version
from rdkit.Chem import BRICS, Descriptors
from rdkit.Chem.FilterCatalog import FilterCatalog, FilterCatalogParams
from rdkit.Chem.rdMolDescriptors import GetMorganFingerprintAsBitVect
from rdkit.DataStructs import TanimotoSimilarity

from backend.app.core.errors import InvalidInput

HYPOTHESIS = "computational hypothesis: unsynthesized, unvalidated"
FORBIDDEN = ("toxic", "toxicity", "hazard", "poison", "lethal")
ALLOWED_PROPERTIES = {
    "MolWt": Descriptors.MolWt,
    "MolLogP": Descriptors.MolLogP,
    "TPSA": Descriptors.TPSA,
}
MAX_COUNT = 20
BUILD_CAP = 200


def assert_therapeutic(payload: dict[str, Any]) -> None:
    """Reject any request that mentions toxicity or hazard as an objective."""

    blob = json.dumps(payload).lower()
    for token in FORBIDDEN:
        if token in blob:
            raise InvalidInput("Generation cannot reward toxicity or hazard.")
    if payload.get("filters_off") is True or payload.get("disable_filters") is True:
        raise InvalidInput("PAINS, Brenk, and NIH filters cannot be switched off.")


def _catalog() -> FilterCatalog:
    params = FilterCatalogParams()
    params.AddCatalog(FilterCatalogParams.FilterCatalogs.PAINS)
    params.AddCatalog(FilterCatalogParams.FilterCatalogs.BRENK)
    params.AddCatalog(FilterCatalogParams.FilterCatalogs.NIH)
    return FilterCatalog(params)


def filter_hits(mol: Chem.Mol) -> list[str]:
    """Return catalog descriptions. An empty list means the three catalogs did not match."""

    catalog = _catalog()
    hits = []
    matches = catalog.GetMatches(mol)
    for match in matches:
        hits.append(str(match.GetDescription()))
    return hits


def generate(payload: dict[str, Any]) -> dict[str, Any]:
    """Recombine reference molecules. Filters run even if the caller asks otherwise."""

    assert_therapeutic(payload)
    references = [str(item) for item in payload.get("references") or []]
    objectives = list(payload.get("objectives") or [])
    if not references:
        raise InvalidInput("Provide reference molecules to recombine.")
    if not objectives:
        raise InvalidInput("Provide a therapeutic objective: similarity or a property range.")
    _validate_objectives(objectives)
    seed = int(payload.get("seed") or 1)
    count = int(payload.get("count") or 5)
    if count < 1 or count > MAX_COUNT:
        raise InvalidInput(f"count must be from 1 to {MAX_COUNT}.")
    reference_mols = []
    reference_smiles = set()
    for smiles in references:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            raise InvalidInput("A reference SMILES did not pass RDKit sanitization. Nothing was generated.")
        canonical = Chem.MolToSmiles(mol)
        reference_mols.append(mol)
        reference_smiles.add(canonical)
    fragments: set[str] = set()
    for mol in reference_mols:
        fragments |= set(BRICS.BRICSDecompose(mol))
    fragment_mols = [Chem.MolFromSmiles(smiles) for smiles in sorted(fragments)]
    fragment_mols = [mol for mol in fragment_mols if mol is not None]
    if len(fragment_mols) < 2:
        raise InvalidInput("BRICS did not find enough fragments to recombine.")
    pool = []
    for index, product in enumerate(BRICS.BRICSBuild(fragment_mols)):
        pool.append(product)
        if index + 1 >= BUILD_CAP:
            break
    rng = numpy.random.default_rng(seed)
    order = rng.permutation(len(pool)) if pool else []
    attempted = 0
    sanitized = 0
    passed_filters = 0
    outputs = []
    rejected_filters = []
    seen = set()
    for position in order:
        if len(outputs) >= count:
            break
        attempted += 1
        product = pool[int(position)]
        try:
            Chem.SanitizeMol(product)
            canonical = Chem.MolToSmiles(product)
        except Exception:
            continue
        sanitized += 1
        hits = filter_hits(product)
        if hits:
            rejected_filters.append({"smiles": canonical, "hits": hits})
            continue
        passed_filters += 1
        if not _meets_objectives(product, objectives):
            continue
        if canonical in seen:
            continue
        seen.add(canonical)
        outputs.append(
            {
                "smiles": canonical,
                "label": HYPOTHESIS,
                "filter_hits": [],
                "properties": {name: float(function(product)) for name, function in ALLOWED_PROPERTIES.items()},
            }
        )
    unique = list(seen)
    metrics = {
        "attempted": attempted,
        "sanitized": sanitized,
        "validity": (sanitized / attempted) if attempted else None,
        "uniqueness": (len(unique) / sanitized) if sanitized else None,
        "novelty": (sum(1 for smiles in unique if smiles not in reference_smiles) / len(unique)) if unique else None,
        "diversity": _diversity(unique),
        "filter_pass_rate": (passed_filters / sanitized) if sanitized else None,
        "seed": seed,
    }
    return _result(payload, outputs, rejected_filters, metrics, seed)


def _validate_objectives(objectives: list[dict[str, Any]]) -> None:
    for objective in objectives:
        kind = objective.get("kind")
        if kind == "similarity":
            if not objective.get("reference_smiles"):
                raise InvalidInput("A similarity objective needs reference_smiles.")
            if Chem.MolFromSmiles(str(objective["reference_smiles"])) is None:
                raise InvalidInput("The similarity reference did not sanitize.")
        elif kind == "property_range":
            if objective.get("property") not in ALLOWED_PROPERTIES:
                raise InvalidInput("Property ranges are limited to MolWt, MolLogP, and TPSA.")
        else:
            raise InvalidInput("Objectives must be similarity or property_range.")


def _meets_objectives(mol: Chem.Mol, objectives: list[dict[str, Any]]) -> bool:
    for objective in objectives:
        if objective["kind"] == "similarity":
            reference = Chem.MolFromSmiles(str(objective["reference_smiles"]))
            left = GetMorganFingerprintAsBitVect(mol, 2, nBits=2048)
            right = GetMorganFingerprintAsBitVect(reference, 2, nBits=2048)
            minimum = float(objective.get("minimum_tanimoto") or 0.0)
            if TanimotoSimilarity(left, right) < minimum:
                return False
        else:
            value = float(ALLOWED_PROPERTIES[objective["property"]](mol))
            if objective.get("minimum") is not None and value < float(objective["minimum"]):
                return False
            if objective.get("maximum") is not None and value > float(objective["maximum"]):
                return False
    return True


def _diversity(smiles_list: list[str]) -> float | None:
    if len(smiles_list) < 2:
        return None
    fps = [GetMorganFingerprintAsBitVect(Chem.MolFromSmiles(smiles), 2, nBits=2048) for smiles in smiles_list]
    distances = []
    for left in range(len(fps)):
        for right in range(left + 1, len(fps)):
            distances.append(1.0 - float(TanimotoSimilarity(fps[left], fps[right])))
    return float(sum(distances) / len(distances)) if distances else None


def _result(payload, outputs, rejected, metrics, seed: int) -> dict[str, Any]:
    parameters = {"seed": seed, "filters": ["PAINS", "BRENK", "NIH"], "generator": "RDKit BRICSBuild"}
    now = datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    return {
        "analysis_id": str(uuid.uuid4()),
        "kind": "molecular_generation",
        "status": "succeeded",
        "created_at": now,
        "inputs": [],
        "methods": [
            {
                "name": "brics_recombination",
                "software": "RDKit",
                "version": rdkit_version,
                "parameters": parameters,
            }
        ],
        "measurements": [
            {
                "name": "validity",
                "value": metrics["validity"],
                "unit": "1",
                "origin": "calculated",
                "method": "Sanitized products divided by products drawn. Not an experimental measurement.",
                "uncertainty": None,
                "source": None,
            },
            {
                "name": "filter_pass_rate",
                "value": metrics["filter_pass_rate"],
                "unit": "1",
                "origin": "calculated",
                "method": "Products with no PAINS, Brenk, or NIH hit divided by sanitized products.",
                "uncertainty": None,
                "source": None,
            },
        ],
        "evidence": [],
        "limitations": [
            HYPOTHESIS,
            "Filters are PAINS, Brenk, and NIH. They cannot be switched off.",
            "This is not a design of a medicine and not evidence of activity or safety.",
        ],
        "warnings": [],
        "skipped_stages": [],
        "errors": [],
        "reproducibility": {
            "software_versions": {"rdkit": rdkit_version, "python": platform.python_version()},
            "random_seed": seed,
            "config_hash": hashlib.sha256(json.dumps(parameters, sort_keys=True).encode()).hexdigest(),
            "platform": platform.platform(),
        },
        "details": {
            "label": HYPOTHESIS,
            "outputs": outputs,
            "filter_hits": rejected,
            "metrics": metrics,
            "request": payload,
        },
    }
