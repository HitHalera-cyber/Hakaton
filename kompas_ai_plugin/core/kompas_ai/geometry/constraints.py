"""Geometric relations between recognised entities.

Detected relations become parametric constraints in KOMPAS later (where the
API allows it) and are already useful for snapping and for review.
"""

from __future__ import annotations

import math

from ..ir import Arc, Circle, Constraint, Line
from .fitting import angle_diff, direction_deg, point_line_distance

COINCIDENT = 0.1  # mm
AXIS_ANGLE = 0.3  # deg
PARALLEL_ANGLE = 0.3  # deg
CONCENTRIC = 0.1  # mm
TANGENT = 0.1  # mm


def find_constraints(entities) -> list[Constraint]:
    lines = [e for e in entities if isinstance(e, Line)]
    curves = [e for e in entities if isinstance(e, (Circle, Arc))]
    out: list[Constraint] = []

    for line in lines:
        ang = direction_deg(line.p1, line.p2)
        if angle_diff(ang, 0.0) <= AXIS_ANGLE:
            out.append(Constraint("horizontal", line.id))
        elif angle_diff(ang, 90.0) <= AXIS_ANGLE:
            out.append(Constraint("vertical", line.id))

    for i, a in enumerate(lines):
        for b in lines[i + 1:]:
            if not _share_endpoint(a, b):
                continue
            out.append(Constraint("coincident", a.id, b.id))
            diff = angle_diff(direction_deg(a.p1, a.p2), direction_deg(b.p1, b.p2))
            if abs(diff - 90.0) <= PARALLEL_ANGLE and not _both_axis(a, b):
                out.append(Constraint("perpendicular", a.id, b.id))

    # Parallel pairs among inclined lines (horizontal/vertical are covered above).
    inclined = [l for l in lines if min(angle_diff(direction_deg(l.p1, l.p2), 0.0),
                                        angle_diff(direction_deg(l.p1, l.p2), 90.0)) > AXIS_ANGLE]
    for i, a in enumerate(inclined):
        for b in inclined[i + 1:]:
            if angle_diff(direction_deg(a.p1, a.p2), direction_deg(b.p1, b.p2)) <= PARALLEL_ANGLE:
                out.append(Constraint("parallel", a.id, b.id))

    for i, a in enumerate(curves):
        for b in curves[i + 1:]:
            if math.dist(a.center, b.center) <= CONCENTRIC:
                out.append(Constraint("concentric", a.id, b.id))

    for line in lines:
        for c in curves:
            if abs(point_line_distance(c.center, line.p1, line.p2) - c.radius) > TANGENT:
                continue
            if any(abs(math.dist(p, c.center) - c.radius) <= TANGENT for p in (line.p1, line.p2)):
                out.append(Constraint("tangent", line.id, c.id))
    return out


def _share_endpoint(a: Line, b: Line) -> bool:
    return any(math.dist(p, q) <= COINCIDENT for p in (a.p1, a.p2) for q in (b.p1, b.p2))


def _both_axis(a: Line, b: Line) -> bool:
    def axis(l):
        ang = direction_deg(l.p1, l.p2)
        return min(angle_diff(ang, 0.0), angle_diff(ang, 90.0)) <= AXIS_ANGLE
    return axis(a) and axis(b)
