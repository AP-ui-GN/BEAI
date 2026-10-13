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
    resume_from = payload.get("resume_from")
    resume_state: Path | None = None
    completed_steps = 0
    if resume_from:
        if mode != "dynamics":
            raise InvalidInput("Only a dynamics job can resume from a checkpoint.")
        prior = _read_checkpoint(context.settings, str(resume_from))
        _require_same_run(payload, prior, structure_id)
        ph = float(prior["ph"])
        seed = int(prior["seed"])
        resume_state = Path(prior["state_path"])
        completed_steps = int(prior["step"])
    if context.cancelled():
        return None
    if resume_from and mode == "dynamics":
        fixer = _load_prepared(Path(prior["prepared_path"]))
        notes = list(prior.get("preparation_notes") or [])
    else:
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
    if resume_from:
        steps = int(prior["steps"])
        integrator = str(prior["integrator"])
    timestep = 1.0 if integrator == "verlet" else 2.0
    temperature = float(payload.get("temperature_kelvin") or 300.0)
    if resume_from:
        temperature = float(prior["temperature_kelvin"])
    config["timestep_femtoseconds"] = timestep
    config["temperature_kelvin"] = temperature
    directory = _checkpoint_dir(context.settings, context.job_id)
    state_path = directory / "state.xml"
    if not resume_from:
        _write_prepared(fixer, directory / "prepared.pdb")
        (directory / "preparation_notes.json").write_text(json.dumps(notes), encoding="utf-8")
        fixer = _load_prepared(directory / "prepared.pdb")
    else:
        prepared_path = directory / "prepared.pdb"
        if not prepared_path.is_file():
            prepared_path.write_bytes(Path(prior["prepared_path"]).read_bytes())
        notes_path = directory / "preparation_notes.json"
        if not notes_path.is_file():
            notes_path.write_text(json.dumps(notes), encoding="utf-8")

    def on_checkpoint(step: int) -> None:
        _write_sidecar(
            directory,
            {
                "step": step,
                "steps": steps,
                "structure_id": structure_id,
                "seed": seed,
                "integrator": integrator,
                "temperature_kelvin": temperature,
                "ph": ph,
                "timestep_fs": timestep,
            },
        )
        context.set_progress(step / steps)

    outcome = run_dynamics(
        fixer,
        steps=steps,
        seed=seed,
        integrator_name=integrator,
        temperature_kelvin=temperature,
        timestep_fs=timestep,
        cancelled=context.cancelled,
        checkpoint_path=state_path,
        on_checkpoint=on_checkpoint,
        resume_checkpoint=resume_state,
        completed_steps=completed_steps,
    )
    if outcome.get("cancelled") or context.cancelled():
        return None
    context.set_progress(1.0)
    result = _result(mode, config, notes, outcome, DYNAMICS_LABEL)
    result["details"]["checkpoint_step"] = outcome.get("checkpoint_step")
    result["details"]["resumed_from"] = resume_from
    result["details"]["resumed_from_step"] = completed_steps if resume_from else None
    if resume_from:
        result["limitations"].append(
            "Frames after a resume report RMSD from the checkpoint coordinates, not from the first dynamics step."
        )
    return result


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
            "outcome": {
                key: value
                for key, value in outcome.items()
                if key not in {"frames", "final_positions_angstrom"}
            },
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


def _checkpoint_dir(settings: Any, job_id: str) -> Path:
    directory = settings.resolved_storage_dir() / "simulation-checkpoints" / _job_id(job_id)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _read_checkpoint(settings: Any, job_id: str) -> dict[str, Any]:
    directory = settings.resolved_storage_dir() / "simulation-checkpoints" / _job_id(job_id)
    sidecar = directory / "checkpoint.json"
    state = directory / "state.xml"
    prepared = directory / "prepared.pdb"
    notes_path = directory / "preparation_notes.json"
    if not sidecar.is_file() or not state.is_file() or not prepared.is_file():
        raise InvalidInput("No simulation checkpoint was found for that job.")
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise InvalidInput("The simulation checkpoint record was not usable.")
    data["state_path"] = str(state)
    data["prepared_path"] = str(prepared)
    if notes_path.is_file():
        loaded_notes = json.loads(notes_path.read_text(encoding="utf-8"))
        data["preparation_notes"] = loaded_notes if isinstance(loaded_notes, list) else []
    return data


def _write_sidecar(directory: Path, payload: dict[str, Any]) -> None:
    temporary = directory / "checkpoint.json.tmp"
    temporary.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    temporary.replace(directory / "checkpoint.json")


def _require_same_run(payload: dict[str, Any], prior: dict[str, Any], structure_id: str) -> None:
    if prior.get("structure_id") != structure_id:
        raise InvalidInput("The checkpoint is for a different structure.")
    if str(payload.get("integrator") or "langevin") != str(prior.get("integrator")):
        raise InvalidInput("Resume must use the checkpoint integrator.")
    if int(payload.get("seed") or 1) != int(prior["seed"]):
        raise InvalidInput("Resume must use the checkpoint seed.")
    if int(payload.get("steps") or prior["steps"]) != int(prior["steps"]):
        raise InvalidInput("Resume keeps the original step count.")
    if float(payload.get("temperature_kelvin") or 300.0) != float(prior["temperature_kelvin"]):
        raise InvalidInput("Resume must use the checkpoint temperature.")
    if float(payload.get("ph") or 7.0) != float(prior["ph"]):
        raise InvalidInput("Resume must use the checkpoint pH.")
    if int(prior["step"]) >= int(prior["steps"]):
        raise InvalidInput("The checkpoint is already at the requested step count.")


def _write_prepared(fixer: Any, path: Path) -> None:
    from openmm.app import PDBFile

    with path.open("w", encoding="utf-8") as handle:
        PDBFile.writeFile(fixer.topology, fixer.positions, handle)


def _load_prepared(path: Path) -> Any:
    from types import SimpleNamespace

    from openmm.app import PDBFile

    pdb = PDBFile(str(path))
    return SimpleNamespace(topology=pdb.topology, positions=pdb.positions)


def _job_id(job_id: str) -> str:
    import re

    if not re.fullmatch(r"[0-9a-fA-F-]{36}", job_id):
        raise InvalidInput("The checkpoint job id is not usable.")
    return job_id
