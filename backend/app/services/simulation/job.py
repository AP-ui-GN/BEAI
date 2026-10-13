"""Simulation jobs. A failed preparation stores no energies."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.app.core.errors import InvalidInput
from backend.app.jobs.runner import JobContext
from backend.app.services.simulation.constants import (
    DYNAMICS_LABEL,
    FORCE_FIELD_FILES,
    MAX_MIN_ITERATIONS,
    MAX_STEPS,
    MINIMIZATION_LABEL,
)
from backend.app.services.simulation.engine import prepare_structure, require_openmm, run_dynamics, run_minimization


def run_simulation_job(context: JobContext, payload: dict[str, Any]) -> dict[str, Any] | None:
    require_openmm()
    structure_id = str(payload.get("structure_id") or "")
    path = _structure_path(context, structure_id)
    mode = str(payload.get("mode") or "minimization")
    ph = float(payload.get("ph") or 7.0)
    seed = int(payload.get("seed") or 1)
    if context.cancelled():
        return None
    fixer, notes = prepare_structure(path, ph)
    if context.cancelled():
        return None
    context.set_progress(0.1)
    config = {
        "force_field_files": list(FORCE_FIELD_FILES),
        "solvent": "implicit GBn2",
        "nonbonded_method": "NoCutoff",
        "constraints": "HBonds",
        "temperature_kelvin": payload.get("temperature_kelvin"),
        "pressure_atmosphere": None,
        "thermostat": "LangevinMiddleIntegrator" if payload.get("integrator") == "langevin" else None,
        "friction_per_picosecond": 1.0 if payload.get("integrator") == "langevin" else None,
        "barostat": None,
        "seed": seed,
        "ph": ph,
        "platform": "CPU",
        "max_steps": MAX_STEPS,
        "max_minimization_iterations": MAX_MIN_ITERATIONS,
    }
    if mode == "minimization":
        outcome = run_minimization(fixer, max_iterations=int(payload.get("max_iterations") or 20), seed=seed)
        config["timestep_femtoseconds"] = 2.0
        return _result(mode, config, notes, outcome, MINIMIZATION_LABEL)
    steps = int(payload.get("steps") or 20)
    integrator = str(payload.get("integrator") or "langevin")
    timestep = 1.0 if integrator == "verlet" else 2.0
    config["timestep_femtoseconds"] = timestep
    outcome = run_dynamics(
        fixer,
        steps=steps,
        seed=seed,
        integrator_name=integrator,
        temperature_kelvin=float(payload.get("temperature_kelvin") or 300.0),
        timestep_fs=timestep,
        cancelled=context.cancelled,
    )
    if outcome.get("cancelled") or context.cancelled():
        return None
    context.set_progress(1.0)
    return _result(mode, config, notes, outcome, DYNAMICS_LABEL)


def _structure_path(context: JobContext, structure_id: str) -> Path:
    from backend.app.db.models import Structure

    session = context.runner.factory()
    try:
        row = session.get(Structure, structure_id)
        if row is None:
            raise InvalidInput("Structure not found.")
        root = context.settings.resolved_storage_dir()
        return root / row.stored_path
    finally:
        session.close()


def _result(mode: str, config: dict[str, Any], notes: list[str], outcome: dict[str, Any], label: str) -> dict[str, Any]:
    from datetime import UTC, datetime

    measurements = []
    if mode == "minimization":
        measurements = [
            _energy("initial_potential_energy", outcome["initial_potential_energy_kj_mol"]),
            _energy("final_potential_energy", outcome["final_potential_energy_kj_mol"]),
        ]
    frames = outcome.get("frames") or []
    if frames:
        temperatures = [frame["temperature_kelvin"] for frame in frames if frame.get("temperature_kelvin") is not None]
        mean_temperature = sum(temperatures) / len(temperatures) if temperatures else None
        measurements.append(
            {
                "name": "mean_temperature",
                "value": mean_temperature,
                "unit": "kelvin",
                "origin": "calculated",
                "method": "2 * kinetic energy / (degrees of freedom * gas constant). Not an experimental temperature.",
                "uncertainty": None,
                "source": None,
            }
        )
    now = datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    return {
        "kind": "simulation",
        "status": "succeeded",
        "created_at": now,
        "inputs": [],
        "methods": [
            {
                "name": mode,
                "software": "OpenMM",
                "version": _openmm_version(),
                "parameters": config,
            }
        ],
        "measurements": measurements,
        "evidence": [],
        "limitations": [label, "PDBFixer changes the input structure. The notes list those changes."],
        "warnings": notes,
        "skipped_stages": [],
        "errors": [],
        "reproducibility": {
            "software_versions": {"openmm": _openmm_version()},
            "random_seed": config["seed"],
            "config_hash": _hash(config),
            "platform": str(outcome.get("platform") or config["platform"]),
        },
        "details": {
            "label": label,
            "preparation_notes": notes,
            "config_json": json.dumps(config, sort_keys=True),
            "outcome": {key: value for key, value in outcome.items() if key != "frames"},
            "frames": frames,
        },
    }


def _energy(name: str, value: float) -> dict[str, Any]:
    return {
        "name": name,
        "value": value,
        "unit": "kJ/mol",
        "origin": "calculated",
        "method": MINIMIZATION_LABEL,
        "uncertainty": None,
        "source": None,
    }


def _openmm_version() -> str:
    import openmm

    return str(openmm.__version__)


def _hash(config: dict[str, Any]) -> str:
    import hashlib

    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
