"""Vector geometry used by structure_overview.

Distances and the radius of gyration are in angstroms. Angles and dihedral
angles are in degrees. No masses are applied: every point has weight 1.
"""

from __future__ import annotations

import math

Point = tuple[float, float, float]


def _sub(left: Point, right: Point) -> Point:
    return (left[0] - right[0], left[1] - right[1], left[2] - right[2])


def _dot(left: Point, right: Point) -> float:
    return left[0] * right[0] + left[1] * right[1] + left[2] * right[2]


def _cross(left: Point, right: Point) -> Point:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _norm(vector: Point) -> float:
    return math.sqrt(_dot(vector, vector))


def distance(start: Point, end: Point) -> float:
    """Euclidean distance between two points, in angstroms."""

    return _norm(_sub(start, end))


def angle_degrees(start: Point, vertex: Point, end: Point) -> float:
    """Angle at ``vertex`` in degrees, in the range 0 to 180.

    Algorithm: atan2 of the cross-product magnitude and the dot product of the
    vectors from the vertex to the other two points. A zero-length vector
    raises ``ValueError``.
    """

    left = _sub(start, vertex)
    right = _sub(end, vertex)
    left_norm = _norm(left)
    right_norm = _norm(right)
    if left_norm == 0 or right_norm == 0:
        raise ValueError("angle is undefined for a zero-length vector")
    return math.degrees(math.atan2(_norm(_cross(left, right)), _dot(left, right)))


def dihedral_degrees(first: Point, second: Point, third: Point, fourth: Point) -> float:
    """Signed torsion angle along second→third, in degrees, range (-180, 180].

    Algorithm: project the incoming and outgoing bond vectors onto the plane
    normal to second→third, then take atan2 of their cross and dot products.
    Eclipsed substituents give 0 degrees. A zero-length second→third bond
    raises ``ValueError``.
    """

    bond_in = _sub(first, second)
    axis = _sub(third, second)
    bond_out = _sub(fourth, third)
    axis_norm = _norm(axis)
    if axis_norm == 0:
        raise ValueError("dihedral is undefined for a zero-length axis")
    axis_unit = (axis[0] / axis_norm, axis[1] / axis_norm, axis[2] / axis_norm)
    projected_in = tuple(bond_in[index] - _dot(bond_in, axis_unit) * axis_unit[index] for index in range(3))
    projected_out = tuple(bond_out[index] - _dot(bond_out, axis_unit) * axis_unit[index] for index in range(3))
    if _norm(projected_in) == 0 or _norm(projected_out) == 0:
        raise ValueError("dihedral is undefined when a substituent lies on the axis")
    sine_term = _dot(_cross(axis_unit, projected_in), projected_out)
    cosine_term = _dot(projected_in, projected_out)
    return math.degrees(math.atan2(sine_term, cosine_term))


def radius_of_gyration(points: list[Point]) -> float | None:
    """Unweighted geometric radius of gyration, in angstroms.

    The center is the arithmetic mean of the points (equal weights, not atomic
    masses). Rg is the square root of the mean squared distance from that
    center. Returns null when fewer than two points are supplied.
    """

    count = len(points)
    if count < 2:
        return None
    center = (
        sum(point[0] for point in points) / count,
        sum(point[1] for point in points) / count,
        sum(point[2] for point in points) / count,
    )
    mean_square = sum(distance(point, center) ** 2 for point in points) / count
    return math.sqrt(mean_square)


def bounding_box(points: list[Point]) -> dict[str, list[float]] | None:
    """Axis-aligned bounding box. Coordinates and sizes are in angstroms."""

    if not points:
        return None
    minimum = [min(point[axis] for point in points) for axis in range(3)]
    maximum = [max(point[axis] for point in points) for axis in range(3)]
    size = [maximum[axis] - minimum[axis] for axis in range(3)]
    return {"min_angstrom": minimum, "max_angstrom": maximum, "size_angstrom": size}
