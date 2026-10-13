"""Cosine similarity and a pre-registered Spearman bootstrap.

The bootstrap seed is 20261013 and the resample count is 1000. The interval
is the 2.5 and 97.5 percentiles of the finite resampled coefficients. These
choices were written down before the ESM-2 run.
"""

from __future__ import annotations

from typing import Any

import numpy

BOOTSTRAP_SEED = 20261013
BOOTSTRAP_RESAMPLES = 1000


def cosine(left: list[float], right: list[float]) -> float | None:
    """Return cosine similarity, or null when either vector has zero length."""

    a = numpy.asarray(left, dtype=float)
    b = numpy.asarray(right, dtype=float)
    if a.shape != b.shape or a.size == 0:
        return None
    left_norm = float(numpy.linalg.norm(a))
    right_norm = float(numpy.linalg.norm(b))
    if left_norm == 0.0 or right_norm == 0.0:
        return None
    return float(numpy.dot(a, b) / (left_norm * right_norm))


def spearman_with_bootstrap(xs: list[float], ys: list[float]) -> dict[str, Any]:
    """Spearman rank correlation of two equal-length series, with a percentile interval."""

    from scipy.stats import spearmanr

    if len(xs) != len(ys) or len(xs) < 3:
        return {
            "spearman": None,
            "interval_low": None,
            "interval_high": None,
            "resamples": BOOTSTRAP_RESAMPLES,
            "seed": BOOTSTRAP_SEED,
            "pair_count": len(xs),
            "finite_resamples": 0,
            "reason": "Spearman needs at least 3 pairs.",
        }
    x = numpy.asarray(xs, dtype=float)
    y = numpy.asarray(ys, dtype=float)
    point = _finite(float(spearmanr(x, y).statistic))
    rng = numpy.random.default_rng(BOOTSTRAP_SEED)
    samples: list[float] = []
    for _ in range(BOOTSTRAP_RESAMPLES):
        index = rng.integers(0, len(x), size=len(x))
        samples_value = _finite(float(spearmanr(x[index], y[index]).statistic))
        if samples_value is not None:
            samples.append(samples_value)
    low = float(numpy.percentile(samples, 2.5)) if samples else None
    high = float(numpy.percentile(samples, 97.5)) if samples else None
    return {
        "spearman": point,
        "interval_low": low,
        "interval_high": high,
        "resamples": BOOTSTRAP_RESAMPLES,
        "seed": BOOTSTRAP_SEED,
        "pair_count": len(xs),
        "finite_resamples": len(samples),
        "reason": None,
    }


def _finite(value: float) -> float | None:
    if value != value or value in {float("inf"), float("-inf")}:
        return None
    return value
