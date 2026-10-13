"""PDBFixer preparation and short OpenMM runs. OpenMM is imported inside functions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy

from backend.app.core.errors import CapabilityUnavailable, InvalidInput
from backend.app.services.simulation.constants import (
    DYNAMICS_LABEL,
    FORCE_FIELD_FILES,
    MAX_MIN_ITERATIONS,
    MAX_STEPS,
    MINIMIZATION_LABEL,
)
from backend.app.services.structure.geometry import radius_of_gyration


def require_openmm() -> None:
    import os

    # One CPU thread keeps a repeated seed from depending on reduction order.
    os.environ["OPENMM_CPU_THREADS"] = "1"
    try:
        import openmm  # noqa: F401
        import pdbfixer  # noqa: F401
    except Exception as exc:
        raise CapabilityUnavailable(f"OpenMM is not installed ({exc.__class__.__name__}).") from exc


def prepare_structure(path: Path, ph: float) -> tuple[Any, list[str]]:
    """Add missing atoms and hydrogens. The returned notes are the changes PDBFixer made."""

    require_openmm()
    from pdbfixer import PDBFixer

    fixer = PDBFixer(filename=str(path))
    notes: list[str] = []
    before = _atom_count(fixer)
    fixer.findMissingResidues()
    notes.append(f"findMissingResidues reported {len(fixer.missingResidues)} gaps.")
    fixer.findNonstandardResidues()
    notes.append(f"findNonstandardResidues reported {len(fixer.nonstandardResidues)} residues.")
    fixer.replaceNonstandardResidues()
    notes.append("replaceNonstandardResidues was called.")
    heterogens_before = _atom_count(fixer)
    fixer.removeHeterogens(keepWater=False)
    removed = heterogens_before - _atom_count(fixer)
    notes.append(f"removeHeterogens(keepWater=False) removed {removed} atoms.")
    fixer.findMissingAtoms()
    missing_sites = sum(len(atoms) for atoms in fixer.missingAtoms.values())
    notes.append(f"findMissingAtoms reported {missing_sites} missing atoms.")
    try:
        fixer.addMissingAtoms()
    except Exception as exc:
        raise InvalidInput(_public_failure(exc)) from exc
    notes.append(f"addMissingAtoms changed the atom count from {before} to {_atom_count(fixer)}.")
    before_h = _atom_count(fixer)
    try:
        fixer.addMissingHydrogens(ph)
    except Exception as exc:
        raise InvalidInput(_public_failure(exc)) from exc
    notes.append(f"addMissingHydrogens at pH {ph} changed the atom count from {before_h} to {_atom_count(fixer)}.")
    return fixer, notes


def run_minimization(fixer: Any, *, max_iterations: int, seed: int) -> dict[str, Any]:
    """Minimize and return energies in kJ/mol. This is not dynamics."""

    if max_iterations < 1 or max_iterations > MAX_MIN_ITERATIONS:
        raise InvalidInput(f"Minimization iterations must be from 1 to {MAX_MIN_ITERATIONS}.")
    simulation, platform_name = _simulation(fixer, integrator_name="langevin", seed=seed, timestep_fs=2.0)
    initial = _potential(simulation)
    simulation.minimizeEnergy(maxIterations=max_iterations)
    final = _potential(simulation)
    return {
        "label": MINIMIZATION_LABEL,
        "initial_potential_energy_kj_mol": initial,
        "final_potential_energy_kj_mol": final,
        "max_iterations": max_iterations,
        "platform": platform_name,
        "seed": seed,
    }


def run_dynamics(
    fixer: Any,
    *,
    steps: int,
    seed: int,
    integrator_name: str,
    temperature_kelvin: float,
    timestep_fs: float,
    minimize_iterations: int = 0,
    cancelled=None,
) -> dict[str, Any]:
    """Run a capped trajectory. ``cancelled`` is checked between steps."""

    if steps < 1 or steps > MAX_STEPS:
        raise InvalidInput(f"Dynamics steps must be from 1 to {MAX_STEPS}.")
    simulation, platform_name = _simulation(
        fixer,
        integrator_name=integrator_name,
        seed=seed,
        timestep_fs=timestep_fs,
        temperature_kelvin=temperature_kelvin,
    )
    if minimize_iterations:
        simulation.minimizeEnergy(maxIterations=minimize_iterations)
    if integrator_name == "langevin":
        simulation.context.setVelocitiesToTemperature(temperature_kelvin, int(seed))
    estimate = _estimate_seconds(simulation, steps)
    start = _positions_angstrom(simulation)
    initial_total = _potential(simulation) + _kinetic(simulation)
    series: list[dict[str, Any]] = []
    stored: list[numpy.ndarray] = []
    stride = max(1, steps // 10)
    for step in range(1, steps + 1):
        if cancelled and cancelled():
            return {"cancelled": True, "frames": series, "runtime_estimate_seconds": estimate}
        simulation.step(1)
        positions = _positions_angstrom(simulation)
        stored.append(positions)
        if step == steps or step % stride == 0:
            series.append(
                {
                    "step": step,
                    "potential_energy_kj_mol": _potential(simulation),
                    "kinetic_energy_kj_mol": _kinetic(simulation),
                    "temperature_kelvin": _temperature(simulation),
                    "rmsd_angstrom": _kabsch_rmsd(start, positions),
                    "radius_of_gyration_angstrom": radius_of_gyration([tuple(row) for row in positions]),
                    "pdb": _pdb_text(simulation),
                }
            )
    return {
        "cancelled": False,
        "label": DYNAMICS_LABEL,
        "platform": platform_name,
        "seed": seed,
        "integrator": integrator_name,
        "timestep_fs": timestep_fs,
        "temperature_kelvin": temperature_kelvin,
        "runtime_estimate_seconds": estimate,
        "frames": series,
        "rmsf_angstrom": _rmsf(stored),
        "final_total_energy_kj_mol": _potential(simulation) + _kinetic(simulation),
        "initial_total_energy_kj_mol": initial_total,
    }


def _simulation(fixer, *, integrator_name: str, seed: int, timestep_fs: float, temperature_kelvin: float = 300.0):
    from openmm import LangevinMiddleIntegrator, Platform, VerletIntegrator
    from openmm.app import ForceField, HBonds, NoCutoff, Simulation
    from openmm.unit import femtoseconds, kelvin, picoseconds

    forcefield = ForceField(*FORCE_FIELD_FILES)
    try:
        system = forcefield.createSystem(fixer.topology, nonbondedMethod=NoCutoff, constraints=HBonds)
    except Exception as exc:
        raise InvalidInput(_public_failure(exc)) from exc
    if integrator_name == "verlet":
        integrator = VerletIntegrator(timestep_fs * femtoseconds)
        integrator.setConstraintTolerance(1e-5)
    elif integrator_name == "langevin":
        integrator = LangevinMiddleIntegrator(
            temperature_kelvin * kelvin,
            1.0 / picoseconds,
            timestep_fs * femtoseconds,
        )
        integrator.setRandomNumberSeed(int(seed))
    else:
        raise InvalidInput("Integrator must be verlet or langevin.")
    platform = Platform.getPlatformByName("CPU")
    simulation = Simulation(fixer.topology, system, integrator, platform)
    simulation.context.setPositions(fixer.positions)
    return simulation, platform.getName()


def _estimate_seconds(simulation: Any, steps: int) -> float:
    """Time one step, then restore that state so the timed step is not part of the trajectory."""

    import time

    state = simulation.context.getState(getPositions=True, getVelocities=True)
    started = time.perf_counter()
    simulation.step(1)
    elapsed = time.perf_counter() - started
    simulation.context.setState(state)
    return float(elapsed * max(steps, 1))


def _potential(simulation: Any) -> float:
    from openmm.unit import kilojoule_per_mole

    state = simulation.context.getState(getEnergy=True)
    return float(state.getPotentialEnergy().value_in_unit(kilojoule_per_mole))


def _kinetic(simulation: Any) -> float:
    from openmm.unit import kilojoule_per_mole

    state = simulation.context.getState(getEnergy=True)
    return float(state.getKineticEnergy().value_in_unit(kilojoule_per_mole))


def _temperature(simulation: Any) -> float | None:
    """Kinetic temperature from 2*KE/(dof*R). Degrees of freedom subtract constraints."""

    from openmm.unit import MOLAR_GAS_CONSTANT_R, kelvin, kilojoule_per_mole

    system = simulation.system
    dof = 3 * system.getNumParticles() - system.getNumConstraints()
    if dof <= 0:
        return None
    kinetic = _kinetic(simulation)
    gas_constant = MOLAR_GAS_CONSTANT_R.value_in_unit(kilojoule_per_mole / kelvin)
    return float(2.0 * kinetic / (dof * gas_constant))


def _positions_angstrom(simulation: Any) -> numpy.ndarray:
    from openmm.unit import nanometer

    state = simulation.context.getState(getPositions=True)
    values = state.getPositions(asNumpy=True).value_in_unit(nanometer)
    return numpy.asarray(values, dtype=float) * 10.0


def _pdb_text(simulation: Any) -> str:
    from io import StringIO

    from openmm.app import PDBFile

    state = simulation.context.getState(getPositions=True)
    buffer = StringIO()
    try:
        PDBFile.writeFile(simulation.topology, state.getPositions(), buffer)
    except Exception:
        return ""
    return buffer.getvalue()


def _kabsch_rmsd(reference: numpy.ndarray, mobile: numpy.ndarray) -> float | None:
    """Fitted RMSD in angstroms. A translated copy of the same points is near zero."""

    if reference.shape != mobile.shape or reference.shape[0] < 3:
        return None
    left = reference - reference.mean(axis=0)
    right = mobile - mobile.mean(axis=0)
    cross = right.T @ left
    rotation_u, _singular, rotation_vt = numpy.linalg.svd(cross)
    determinant = numpy.linalg.det(rotation_u @ rotation_vt)
    sign = numpy.diag([1.0, 1.0, float(numpy.sign(determinant))])
    rotation = rotation_u @ sign @ rotation_vt
    fitted = right @ rotation
    delta = left - fitted
    return float(numpy.sqrt(numpy.mean(numpy.sum(delta * delta, axis=1))))


def _rmsf(positions: list[numpy.ndarray]) -> list[float]:
    if len(positions) < 2:
        return []
    stack = numpy.stack(positions, axis=0)
    mean = stack.mean(axis=0)
    variance = numpy.mean(numpy.sum((stack - mean) ** 2, axis=2), axis=0)
    return [float(numpy.sqrt(value)) for value in variance]


def _atom_count(fixer: Any) -> int:
    return sum(1 for _ in fixer.topology.atoms())


def _public_failure(exc: Exception) -> str:
    text = str(exc).splitlines()[0][:240]
    return f"Structure preparation failed: {text}"
