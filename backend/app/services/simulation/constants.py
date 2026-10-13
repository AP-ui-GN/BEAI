"""Simulation limits and labels. Step caps were chosen before any production run.

NVE acceptance is a relative total-energy drift of 0.02 over 20 steps of 1 fs
after 20 minimization iterations. The Langevin mean-temperature window is
150 K to 450 K for a short run. Same-seed final potential energies must agree
within 1.0 kJ/mol. These bounds are the acceptance tests, not fitted results.
"""

from __future__ import annotations

MINIMIZATION_LABEL = "energy minimization, not molecular dynamics"
DYNAMICS_LABEL = "short simulation: no evidence of long-term stability, binding or efficacy"
MAX_STEPS = 500
MAX_MIN_ITERATIONS = 100
NVE_DRIFT_LIMIT = 0.02
TEMPERATURE_LOW_KELVIN = 150.0
TEMPERATURE_HIGH_KELVIN = 450.0
SEED_ENERGY_TOLERANCE_KJ_MOL = 1.0
FORCE_FIELD_FILES = ("amber14-all.xml", "implicit/gbn2.xml")
