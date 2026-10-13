"""Run a validated workflow. A missing capability skips that step and its dependents."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.core.errors import CapabilityUnavailable, InvalidInput, NotFound
from backend.app.services.compounds.chemistry import parse_molecule
from backend.app.services.structure.analyses import run_structure_overview

CITATION = re.compile(r"\[([^\[\]]+)\]")


def execute_workflow(
    definition: dict[str, Any],
    session: Session,
    settings: Settings,
    *,
    prior: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run steps in listed order. Already succeeded steps in ``prior`` are not repeated."""

    steps = list(definition.get("steps") or [])
    if not steps:
        raise InvalidInput("A workflow needs at least one step.")
    known = {str(step["id"]) for step in steps}
    results: dict[str, dict[str, Any]] = dict(prior or {})
    for step in steps:
        step_id = str(step["id"])
        depends = [str(item) for item in step.get("depends_on") or []]
        for dependency in depends:
            if dependency not in known:
                raise InvalidInput(f"Step {step_id} depends on unknown step {dependency}.")
        previous = results.get(step_id)
        if previous and previous.get("status") == "succeeded":
            continue
        blocked = [
            dependency
            for dependency in depends
            if results.get(dependency, {}).get("status") != "succeeded"
        ]
        if blocked:
            reason = results.get(blocked[0], {}).get("reason") or "A dependency did not succeed."
            results[step_id] = {
                "status": "skipped",
                "reason": f"Skipped because {blocked[0]} did not succeed. {reason}",
            }
            continue
        try:
            output = _run_step(str(step["service"]), dict(step.get("parameters") or {}), session, settings)
        except CapabilityUnavailable as exc:
            results[step_id] = {"status": "skipped", "reason": exc.message}
            continue
        except InvalidInput as exc:
            results[step_id] = {"status": "failed", "reason": exc.message}
            continue
        results[step_id] = {"status": "succeeded", "output": output, "service": step["service"]}
    return _envelope(definition, results)


def check_citations(summary: str, retrieved_ids: set[str]) -> None:
    """Reject a summary whose bracketed citations are not all in the retrieved set."""

    for citation in CITATION.findall(summary):
        if citation not in retrieved_ids:
            raise InvalidInput(f"Citation not in the retrieved set: {citation}")


def _run_step(service: str, parameters: dict[str, Any], session: Session, settings: Settings) -> dict[str, Any]:
    if service == "structure_overview":
        analysis = run_structure_overview(session, settings, str(parameters["structure_id"]))
        result = analysis.result_json or {}
        measurements = [
            {"name": item["name"], "value": item["value"], "unit": item.get("unit"), "origin": item.get("origin")}
            for item in result.get("measurements") or []
        ]
        return {"analysis_id": analysis.id, "measurements": measurements}
    if service == "compound_descriptors":
        parsed = parse_molecule(
            str(parameters["smiles"]),
            keep_largest_fragment=False,
            max_heavy_atoms=settings.max_heavy_atoms,
        )
        return {
            "canonical_smiles": parsed["canonical_smiles"],
            "formula": parsed["formula"],
            "MolWt": parsed["descriptors"]["MolWt"],
            "origin": "calculated",
        }
    if service == "docking":
        if shutil.which("vina") is None:
            raise CapabilityUnavailable("Vina is not on PATH.")
        from backend.app.services.docking.job import dock_payload

        try:
            docked = dock_payload(session, settings, parameters, None)
        except NotFound as exc:
            raise InvalidInput(exc.message) from exc
        return {
            "modes": docked["modes"],
            "output_pdbqt": docked["output_pdbqt"],
            "vina_version": docked["vina_version"],
            "seed": docked["seed"],
            "parameters": docked["parameters"],
        }
    raise InvalidInput(f"Unknown workflow service: {service}.")


def _envelope(definition: dict[str, Any], results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    failed = [key for key, value in results.items() if value.get("status") == "failed"]
    status = "failed" if failed else "succeeded"
    return {
        "analysis_id": str(uuid.uuid4()),
        "kind": "workflow",
        "created_at": now,
        "status": status,
        "inputs": [],
        "methods": [
            {
                "name": "workflow",
                "software": "BEAI",
                "version": None,
                "parameters": {"name": definition.get("name"), "definition_hash": _hash(definition)},
            }
        ],
        "measurements": [],
        "evidence": [],
        "limitations": [
            "A workflow does not draw a scientific conclusion. Each step keeps its own provenance.",
        ],
        "warnings": [],
        "skipped_stages": [
            {"stage": key, "reason": value.get("reason") or "skipped"}
            for key, value in results.items()
            if value.get("status") == "skipped"
        ],
        "errors": [
            {"code": "step_failed", "message": f"{key}: {value.get('reason')}"}
            for key, value in results.items()
            if value.get("status") == "failed"
        ],
        "reproducibility": {
            "software_versions": {},
            "random_seed": None,
            "config_hash": _hash(definition),
            "platform": "local",
        },
        "details": {"steps": results, "definition": definition},
    }


def _hash(definition: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(definition, sort_keys=True, default=str).encode()).hexdigest()
