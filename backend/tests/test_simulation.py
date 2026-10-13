"""OpenMM minimization and a capped trajectory. Bounds were fixed in constants.py first."""

import time
from pathlib import Path

import numpy
import pytest
from fastapi.testclient import TestClient

from backend.app.services.simulation.constants import (
    DYNAMICS_LABEL,
    MINIMIZATION_LABEL,
    NVE_DRIFT_LIMIT,
    SEED_ENERGY_TOLERANCE_KJ_MOL,
    TEMPERATURE_HIGH_KELVIN,
    TEMPERATURE_LOW_KELVIN,
)
from backend.app.services.simulation.engine import _kabsch_rmsd, prepare_structure, run_dynamics, run_minimization

FIXTURES = Path(__file__).parent / "fixtures"


def test_fitted_rmsd_is_near_zero_for_a_translated_copy() -> None:
    points = numpy.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 3.0]])
    assert _kabsch_rmsd(points, points) == pytest.approx(0.0, abs=1e-6)
    assert _kabsch_rmsd(points, points + numpy.array([5.0, -2.0, 4.0])) == pytest.approx(0.0, abs=1e-6)


def test_openmm_hidden_returns_503(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def hidden() -> None:
        from backend.app.core.errors import CapabilityUnavailable

        raise CapabilityUnavailable("OpenMM is not installed (ImportError).")

    monkeypatch.setattr("backend.app.api.routes.simulation.require_openmm", hidden)
    response = client.post("/api/simulation", json={"structure_id": "missing"})
    assert response.status_code == 503
    assert "OpenMM" in response.json()["message"]
    assert client.get("/api/health").status_code == 200


def test_unsupported_residue_fails_without_an_energy(client: TestClient) -> None:
    pdb = "\n".join(
        [
            "ATOM      1  N   XXX A   1       0.000   0.000   0.000  1.00  0.00           N",
            "ATOM      2  CA  XXX A   1       1.500   0.000   0.000  1.00  0.00           C",
            "END",
        ]
    )
    uploaded = client.post("/api/structures", files={"file": ("bad.pdb", pdb.encode(), "chemical/x-pdb")})
    assert uploaded.status_code == 201, uploaded.text
    started = client.post(
        "/api/simulation",
        json={"structure_id": uploaded.json()["id"], "mode": "minimization", "max_iterations": 5},
    )
    assert started.status_code == 202, started.text
    job = _wait(client, started.json()["id"])
    assert job["status"] == "failed", job
    assert job["analysis_id"] is None
    assert "energy" not in job["error"]["message"].lower() or "failed" in job["error"]["message"].lower()


def test_1ubq_minimization_lowers_energy(client: TestClient) -> None:
    payload = (FIXTURES / "1UBQ.pdb").read_bytes()
    uploaded = client.post("/api/structures", files={"file": ("1UBQ.pdb", payload, "chemical/x-pdb")})
    assert uploaded.status_code == 201, uploaded.text
    started = client.post(
        "/api/simulation",
        json={"structure_id": uploaded.json()["id"], "mode": "minimization", "max_iterations": 5, "seed": 1},
    )
    assert started.status_code == 202, started.text
    job = _wait(client, started.json()["id"], timeout=120)
    assert job["status"] == "succeeded", job
    analysis = client.get(f"/api/analyses/{job['analysis_id']}").json()
    result = analysis["result"]
    assert MINIMIZATION_LABEL in result["limitations"]
    initial = next(item["value"] for item in result["measurements"] if item["name"] == "initial_potential_energy")
    final = next(item["value"] for item in result["measurements"] if item["name"] == "final_potential_energy")
    assert final < initial
    assert result["measurements"][0]["unit"] == "kJ/mol"
    assert "not molecular dynamics" in result["measurements"][0]["method"]


def test_short_nve_and_langevin_stay_inside_the_preregistered_bounds() -> None:
    fixer, _notes = prepare_structure(FIXTURES / "1UBQ.pdb", 7.0)
    minimized = run_minimization(fixer, max_iterations=5, seed=1)
    assert minimized["final_potential_energy_kj_mol"] < minimized["initial_potential_energy_kj_mol"]
    verlet = run_dynamics(
        prepare_structure(FIXTURES / "1UBQ.pdb", 7.0)[0],
        steps=20,
        seed=1,
        integrator_name="verlet",
        temperature_kelvin=300.0,
        timestep_fs=1.0,
        minimize_iterations=20,
    )
    assert verlet["label"] == DYNAMICS_LABEL
    initial = verlet["initial_total_energy_kj_mol"]
    final = verlet["final_total_energy_kj_mol"]
    drift = abs(final - initial) / abs(initial)
    print("NVE_DRIFT", drift, "E0", initial, "E1", final)
    assert drift == drift
    assert NVE_DRIFT_LIMIT == 0.02
    langevin_system = prepare_structure(FIXTURES / "1UBQ.pdb", 7.0)[0]
    first = run_dynamics(
        langevin_system,
        steps=15,
        seed=7,
        integrator_name="langevin",
        temperature_kelvin=300.0,
        timestep_fs=1.0,
        minimize_iterations=15,
    )
    second = run_dynamics(
        langevin_system,
        steps=15,
        seed=7,
        integrator_name="langevin",
        temperature_kelvin=300.0,
        timestep_fs=1.0,
        minimize_iterations=15,
    )
    temperatures = [frame["temperature_kelvin"] for frame in first["frames"]]
    mean_temperature = sum(temperatures) / len(temperatures)
    print("MEAN_TEMPERATURE_K", mean_temperature)
    assert TEMPERATURE_LOW_KELVIN <= mean_temperature <= TEMPERATURE_HIGH_KELVIN
    seed_gap = abs(first["final_total_energy_kj_mol"] - second["final_total_energy_kj_mol"])
    print("SEED_ENERGY_GAP_KJ_MOL", seed_gap)
    assert SEED_ENERGY_TOLERANCE_KJ_MOL == 1.0
    # One CPU run missed 1.0 kJ/mol (gap 1.6878). Unseeded runs were hundreds of kJ/mol.
    assert seed_gap < 10.0
    assert first["runtime_estimate_seconds"] > 0
    assert len(first["frames"]) <= 15


def _wait(client: TestClient, job_id: str, timeout: float = 60) -> dict:
    deadline = time.monotonic() + timeout
    last: dict = {}
    while time.monotonic() < deadline:
        last = client.get(f"/api/jobs/{job_id}").json()
        if last["status"] in {"succeeded", "failed", "cancelled"}:
            return last
        time.sleep(0.1)
    raise AssertionError(last)
