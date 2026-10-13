"""Run Vina as a subprocess. Cancellation kills the process group.

A docking score is in kcal/mol and is not an experimental binding affinity.
"""

from __future__ import annotations

import os
import signal
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from backend.app.core.errors import InvalidInput
from backend.app.jobs.runner import JobContext
from backend.app.services.docking.parse import parse_vina_pdbqt
from backend.app.services.docking.prepare import ligand_pdbqt, receptor_pdbqt


def vina_argv(
    receptor: Path,
    ligand: Path,
    output: Path,
    center: tuple[float, float, float],
    size: tuple[float, float, float],
    *,
    exhaustiveness: int,
    num_modes: int,
    seed: int,
) -> list[str]:
    return [
        "vina",
        "--receptor",
        str(receptor),
        "--ligand",
        str(ligand),
        "--out",
        str(output),
        "--center_x",
        str(center[0]),
        "--center_y",
        str(center[1]),
        "--center_z",
        str(center[2]),
        "--size_x",
        str(size[0]),
        "--size_y",
        str(size[1]),
        "--size_z",
        str(size[2]),
        "--exhaustiveness",
        str(exhaustiveness),
        "--num_modes",
        str(num_modes),
        "--seed",
        str(seed),
    ]


def run_argv(argv: list[str], context: JobContext | None, timeout: float) -> subprocess.CompletedProcess[str]:
    """Run ``argv`` without a shell. Cancel or timeout kills the process group."""

    process = subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        while True:
            try:
                stdout, stderr = process.communicate(timeout=0.2)
                return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)
            except subprocess.TimeoutExpired:
                if context is not None and context.cancelled():
                    _kill(process)
                    raise InvalidInput("The docking process was cancelled.") from None
                timeout -= 0.2
                if timeout <= 0:
                    _kill(process)
                    raise InvalidInput("Vina exceeded the time limit.") from None
    except Exception:
        if process.poll() is None:
            _kill(process)
        raise


def _kill(process: subprocess.Popen[str]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=2)


def dock_smiles(
    *,
    receptor_pdb: str,
    ligand_smiles: str,
    center: tuple[float, float, float],
    size: tuple[float, float, float],
    exhaustiveness: int,
    num_modes: int,
    seed: int,
    drop_resnames: set[str],
    context: JobContext | None,
    timeout: float,
    argv_builder=None,
) -> dict[str, Any]:
    if not all(1.0 <= edge <= 40.0 for edge in size):
        raise InvalidInput("Each box edge must be between 1 and 40 angstroms.")
    ligand = ligand_pdbqt(ligand_smiles, seed)
    receptor = receptor_pdbqt(receptor_pdb, drop_resnames)
    if context is not None:
        context.set_progress(0.3)
    with tempfile.TemporaryDirectory(prefix="beai-vina-") as directory:
        folder = Path(directory)
        receptor_path = folder / "receptor.pdbqt"
        ligand_path = folder / "ligand.pdbqt"
        output_path = folder / "out.pdbqt"
        receptor_path.write_text(receptor, encoding="utf-8")
        ligand_path.write_text(ligand, encoding="utf-8")
        builder = argv_builder or vina_argv
        argv = builder(
            receptor_path,
            ligand_path,
            output_path,
            center,
            size,
            exhaustiveness=exhaustiveness,
            num_modes=num_modes,
            seed=seed,
        )
        completed = run_argv(argv, context, timeout)
        if completed.returncode != 0 or not output_path.is_file():
            stderr = (completed.stderr or completed.stdout or "").strip().splitlines()
            summary = stderr[-1][:300] if stderr else "Vina exited without an output file."
            raise InvalidInput(f"Vina failed: {summary}")
        text = output_path.read_text(encoding="utf-8")
    modes = parse_vina_pdbqt(text)
    if not modes:
        raise InvalidInput("Vina finished but the output had no scored modes.")
    return {"modes": modes, "output_pdbqt": text, "seed": seed, "exhaustiveness": exhaustiveness}
