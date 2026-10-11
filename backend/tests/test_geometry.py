"""Analytic geometry. Expected values come from the coordinates, not from the service output."""

import math

import pytest

from backend.app.services.structure.geometry import (
    angle_degrees,
    dihedral_degrees,
    distance,
    radius_of_gyration,
)


def test_distance_of_three_angstroms() -> None:
    assert distance((0.0, 0.0, 0.0), (3.0, 0.0, 0.0)) == pytest.approx(3.0, abs=1e-6)


def test_right_angle() -> None:
    # Vectors from the origin along +x and +y are perpendicular.
    assert angle_degrees((3.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 4.0, 0.0)) == pytest.approx(90.0, abs=1e-6)


def test_straight_angle() -> None:
    assert angle_degrees((1.0, 0.0, 0.0), (0.0, 0.0, 0.0), (-2.0, 0.0, 0.0)) == pytest.approx(180.0, abs=1e-6)


def test_dihedral_cis_and_trans() -> None:
    # Bond axis is the z axis from (0,0,-1) to (0,0,1). Both substituents in +x are cis.
    first = (1.0, 0.0, -1.0)
    second = (0.0, 0.0, -1.0)
    third = (0.0, 0.0, 1.0)
    cis = (1.0, 0.0, 1.0)
    trans = (-1.0, 0.0, 1.0)
    assert dihedral_degrees(first, second, third, cis) == pytest.approx(0.0, abs=1e-6)
    torsion = dihedral_degrees(first, second, third, trans)
    assert abs(abs(torsion) - 180.0) < 1e-6


def test_radius_of_gyration_of_two_points_three_angstroms_apart() -> None:
    # Center is the midpoint. Each point is 1.5 angstroms from it, so Rg is 1.5.
    value = radius_of_gyration([(0.0, 0.0, 0.0), (3.0, 0.0, 0.0)])
    assert value == pytest.approx(1.5, abs=1e-6)


def test_radius_of_gyration_needs_two_points() -> None:
    assert radius_of_gyration([(0.0, 0.0, 0.0)]) is None


def test_degenerate_angle_is_rejected() -> None:
    with pytest.raises(ValueError):
        angle_degrees((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (1.0, 0.0, 0.0))


def test_three_colinear_calpha_radius_matches_hand_calculation() -> None:
    # Points 0, 3, and 8 on x. Center is 11/3.
    # Squared distances 121/9, 4/9, and 169/9. Mean square is 98/9.
    points = [(0.0, 0.0, 0.0), (3.0, 0.0, 0.0), (8.0, 0.0, 0.0)]
    assert radius_of_gyration(points) == pytest.approx(math.sqrt(98 / 9), abs=1e-6)
