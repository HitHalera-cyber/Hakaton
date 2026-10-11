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
    """The relations, found among neighbours only (a grid over the sheet):
    an assembly drawing has thousands of lines, and every pair of them was
    millions of comparisons."""
    lines = [e for e in entities if isinstance(e, Line)]
    curves = [e for e in entities if isinstance(e, (Circle, Arc))]
    out: list[Constraint] = []
    angle = {id(l): direction_deg(l.p1, l.p2) for l in lines}

    for line in lines:
        ang = angle[id(line)]
        if angle_diff(ang, 0.0) <= AXIS_ANGLE:
            out.append(Constraint("horizontal", line.id))
        elif angle_diff(ang, 90.0) <= AXIS_ANGLE:
            out.append(Constraint("vertical", line.id))

    # lines sharing an end: their ends in cells of the grid
    ends = Grid(1.0)
    for k, l in enumerate(lines):
        for p in (l.p1, l.p2):
            ends.add(p, k)
    pairs = set()
    for k, l in enumerate(lines):
        for p in (l.p1, l.p2):
            for m in ends.near(p, COINCIDENT):
                if m > k:
                    pairs.add((k, m))
    for k, m in sorted(pairs):
        a, b = lines[k], lines[m]
        if not _share_endpoint(a, b):
            continue
        out.append(Constraint("coincident", a.id, b.id))
        diff = angle_diff(angle[id(a)], angle[id(b)])
        if abs(diff - 90.0) <= PARALLEL_ANGLE and not _both_axis(a, b):
            out.append(Constraint("perpendicular", a.id, b.id))

    # parallel pairs among inclined lines (horizontal/vertical are covered
    # above): only lines of nearly one direction are compared
    inclined = [l for l in lines if min(angle_diff(angle[id(l)], 0.0),
                                        angle_diff(angle[id(l)], 90.0)) > AXIS_ANGLE]
    by_angle: dict[int, list] = {}
    for l in inclined:
        by_angle.setdefault(int(angle[id(l)] % 180.0 // PARALLEL_ANGLE), []).append(l)
    buckets = int(180.0 // PARALLEL_ANGLE) + 1
    seen = set()
    for key, group in by_angle.items():
        near = group + by_angle.get((key + 1) % buckets, [])
        for x, a in enumerate(near):
            for b in near[x + 1:]:
                pair = (min(id(a), id(b)), max(id(a), id(b)))
                if pair in seen or a is b:
                    continue
                seen.add(pair)
                if angle_diff(angle[id(a)], angle[id(b)]) <= PARALLEL_ANGLE:
                    out.append(Constraint("parallel", a.id, b.id))

    centres = Grid(1.0)
    for k, c in enumerate(curves):
        centres.add(c.center, k)
    for k, a in enumerate(curves):
        for m in sorted(centres.near(a.center, CONCENTRIC)):
            if m > k and math.dist(a.center, curves[m].center) <= CONCENTRIC:
                out.append(Constraint("concentric", a.id, curves[m].id))

    # tangent: a line one of whose ends lies on the curve
    on_curve = Grid(5.0)
    for k, c in enumerate(curves):
        on_curve.add_box(c.center, c.radius + TANGENT, k)
    for line in lines:
        cand = set()
        for p in (line.p1, line.p2):
            cand |= on_curve.at(p)
        for k in sorted(cand):
            c = curves[k]
            if abs(point_line_distance(c.center, line.p1, line.p2) - c.radius) > TANGENT:
                continue
            if any(abs(math.dist(p, c.center) - c.radius) <= TANGENT for p in (line.p1, line.p2)):
                out.append(Constraint("tangent", line.id, c.id))
    return out


class Grid:
    """Points (or boxes) in square cells, to find what is near quickly. A box
    over too many cells (an arc of a huge radius) is kept aside and offered
    to every query instead."""

    MAX_CELLS = 2000

    def __init__(self, cell: float):
        self.cell = cell
        self.cells: dict[tuple, set] = {}
        self.big: set = set()

    def _key(self, p):
        return (int(math.floor(p[0] / self.cell)), int(math.floor(p[1] / self.cell)))

    def add(self, p, item):
        self.cells.setdefault(self._key(p), set()).add(item)

    def add_box(self, c, r, item):
        self.add_rect(c[0] - r, c[1] - r, c[0] + r, c[1] + r, item)

    def add_rect(self, x0, y0, x1, y1, item):
        (a0, b0) = self._key((min(x0, x1), min(y0, y1)))
        (a1, b1) = self._key((max(x0, x1), max(y0, y1)))
        if (a1 - a0 + 1) * (b1 - b0 + 1) > self.MAX_CELLS:
            self.big.add(item)
            return
        for x in range(a0, a1 + 1):
            for y in range(b0, b1 + 1):
                self.cells.setdefault((x, y), set()).add(item)

    def at(self, p) -> set:
        return self.cells.get(self._key(p), set()) | self.big

    def near(self, p, r) -> set:
        (x0, y0), (x1, y1) = self._key((p[0] - r, p[1] - r)), self._key((p[0] + r, p[1] + r))
        out = set(self.big)
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                out |= self.cells.get((x, y), set())
        return out


def _share_endpoint(a: Line, b: Line) -> bool:
    return any(math.dist(p, q) <= COINCIDENT for p in (a.p1, a.p2) for q in (b.p1, b.p2))


def _both_axis(a: Line, b: Line) -> bool:
    def axis(l):
        ang = direction_deg(l.p1, l.p2)
        return min(angle_diff(ang, 0.0), angle_diff(ang, 90.0)) <= AXIS_ANGLE
    return axis(a) and axis(b)
