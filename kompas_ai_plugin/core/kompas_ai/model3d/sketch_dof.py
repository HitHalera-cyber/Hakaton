"""Constraints that make a revolve sketch fully defined, and nothing more.

KOMPAS shows a sketch as fully defined only when no point or curve of it can
move. Joints, horizontals, verticals and tangencies leave the size and place
of the profile free; fixing lengths, angles and points removes the rest. A
constraint that repeats what the others already say makes the sketch
over-defined, so each candidate is kept only if it removes degrees of
freedom the kept ones leave: the rank of the Jacobian of the constraint
equations (taken numerically at the current geometry) has to grow by the
number of its equations.

Segments are those of :func:`kompas_ai.model3d.revolve.profile_segments`:
("line", p1, p2) or ("arc", center, r, a1, a2), arcs counter-clockwise from
a1 to a2 in degrees. Point index 0 is the start of a segment, 1 its end.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

STEP = 1e-6
STRAIGHT = 1e-9


@dataclass(frozen=True)
class Job:
    """One constraint: ``kind`` on object ``a`` (and ``b``), ``ia``/``ib`` point indices."""

    kind: str
    a: int
    b: int | None = None
    ia: int | None = None
    ib: int | None = None


def _vars(seg) -> list[float]:
    if seg[0] == "line":
        return [seg[1][0], seg[1][1], seg[2][0], seg[2][1]]
    return [seg[1][0], seg[1][1], seg[2], math.radians(seg[3]), math.radians(seg[4])]


class SketchSystem:
    def __init__(self, segments):
        self.segments = list(segments)
        self.offset = []
        x0 = []
        for seg in self.segments:
            self.offset.append(len(x0))
            x0 += _vars(seg)
        self.x0 = np.array(x0, dtype=float)

    @property
    def size(self) -> int:
        return len(self.x0)

    def _point(self, x, i, idx):
        o, seg = self.offset[i], self.segments[i]
        if seg[0] == "line":
            return x[o + 2 * idx], x[o + 2 * idx + 1]
        a = x[o + 3 + idx]
        return x[o] + x[o + 2] * math.cos(a), x[o + 1] + x[o + 2] * math.sin(a)

    def _touching_end(self, arc: int, line: int) -> int:
        """Which end of the arc (0/1) lies on the line, at the starting geometry."""
        ends = [self._point(self.x0, line, 0), self._point(self.x0, line, 1)]
        return min((0, 1), key=lambda k: min(math.dist(self._point(self.x0, arc, k), q)
                                             for q in ends))

    def equations(self, job: Job, x) -> list[float]:
        o = self.offset[job.a]
        if job.kind == "coincident":
            p, q = self._point(x, job.a, job.ia), self._point(x, job.b, job.ib)
            return [p[0] - q[0], p[1] - q[1]]
        if job.kind == "horizontal":
            return [x[o + 3] - x[o + 1]]
        if job.kind == "vertical":
            return [x[o + 2] - x[o]]
        if job.kind == "tangent":
            # at the joint the radius is square to the line (the distance form
            # |centre–line| = r is degenerate there: its gradient repeats the joint's)
            li, ai = (job.a, job.b) if self.segments[job.a][0] == "line" else (job.b, job.a)
            lo, ao = self.offset[li], self.offset[ai]
            x1, y1, x2, y2 = x[lo:lo + 4]
            k = self._touching_end(ai, li)
            a = x[ao + 3 + k]
            n = math.hypot(x2 - x1, y2 - y1)
            return [(math.cos(a) * (x2 - x1) + math.sin(a) * (y2 - y1)) / n]
        if job.kind == "fixed_point":
            p, p0 = self._point(x, job.a, job.ia), self._point(self.x0, job.a, job.ia)
            return [p[0] - p0[0], p[1] - p0[1]]
        if job.kind == "fixed_length":
            x1, y1, x2, y2 = x[o:o + 4]
            a1, b1, a2, b2 = self.x0[o:o + 4]
            return [math.hypot(x2 - x1, y2 - y1) - math.hypot(a2 - a1, b2 - b1)]
        if job.kind == "fixed_angle":
            x1, y1, x2, y2 = x[o:o + 4]
            a1, b1, a2, b2 = self.x0[o:o + 4]
            t = math.atan2(b2 - b1, a2 - a1)
            return [(x2 - x1) * math.sin(t) - (y2 - y1) * math.cos(t)]
        raise ValueError(job.kind)

    def rows(self, job: Job) -> np.ndarray:
        """Jacobian rows of a constraint at the current geometry."""
        base = self.x0
        cols = []
        for k in range(self.size):
            d = np.zeros(self.size)
            d[k] = STEP
            hi = np.array(self.equations(job, base + d))
            lo = np.array(self.equations(job, base - d))
            cols.append((hi - lo) / (2 * STEP))
        return np.array(cols).T


def _rank(m: np.ndarray) -> int:
    if m.size == 0:
        return 0
    return int(np.linalg.matrix_rank(m, tol=1e-6 * max(1.0, float(np.abs(m).max()))))


def _is_line(seg, kind) -> bool:
    (x1, y1), (x2, y2) = seg[1], seg[2]
    n = math.hypot(x2 - x1, y2 - y1)
    if kind == "horizontal":
        return abs(y2 - y1) <= STRAIGHT * max(1.0, n)
    return abs(x2 - x1) <= STRAIGHT * max(1.0, n)


def _ends_meet(a, b):
    from ..kompas.api5 import _joint_indices  # pure geometry, no COM

    return _joint_indices(a, b)


def _tangent(a, b) -> bool:
    from ..kompas.api5 import _tangent as tangent

    return tangent(a, b)


def candidates(loops, axis_index: int | None = None) -> tuple[list, list[Job], list[Job]]:
    """(segments, structural jobs, fixing jobs) for the loops; segment indices
    run over the loops in order, the axis (if given) is ``axis_index``."""
    segments = [seg for loop in loops for seg in loop]
    structural, fixing = [], []
    start = 0
    for loop in loops:
        n = len(loop)
        for k in range(n):
            i, j = start + k, start + (k + 1) % n
            a, b = segments[i], segments[j]
            ia, ib = _ends_meet(a, b)
            structural.append(Job("coincident", i, j, ia, ib))
            if {a[0], b[0]} == {"line", "arc"} and _tangent(a, b):
                structural.append(Job("tangent", i, j))
        for k in range(n):
            i = start + k
            if segments[i][0] == "line":
                for kind in ("horizontal", "vertical"):
                    if _is_line(segments[i], kind):
                        structural.append(Job(kind, i))
                        break
        start += n
    if axis_index is not None:
        fixing += [Job("fixed_point", axis_index, ia=0), Job("fixed_point", axis_index, ia=1)]
    # Points first where they take two degrees of freedom at once: the start
    # of the profile and the ends of the fillets (a fillet's radius is free
    # otherwise — lengths alone left the radii of arc–line–arc chains loose).
    # Then lengths and angles of lines, then any point still free.
    fixing.append(Job("fixed_point", 0, ia=0))
    arcs = [i for i, s in enumerate(segments) if s[0] == "arc"]
    fixing += [Job("fixed_point", i, ia=k) for i in arcs for k in (0, 1)]
    lines = [i for i, s in enumerate(segments) if s[0] == "line"]
    fixing += [Job("fixed_length", i) for i in lines]
    fixing += [Job("fixed_angle", i) for i in lines
               if not _is_line(segments[i], "horizontal") and not _is_line(segments[i], "vertical")]
    fixing += [Job("fixed_point", i, ia=k) for i in lines for k in (0, 1)]
    return segments, structural, fixing


def select(segments, jobs) -> tuple[list[Job], int]:
    """The jobs that are independent of those before them, and the degrees of
    freedom left after them."""
    system = SketchSystem(segments)
    kept, m, rank = [], np.zeros((0, system.size)), 0
    for job in jobs:
        rows = system.rows(job)
        trial = np.vstack([m, rows])
        r = _rank(trial)
        if r == rank + len(rows):
            kept.append(job)
            m, rank = trial, r
    return kept, system.size - rank


def full_definition(loops, axis=None) -> tuple[list, list[Job], int]:
    """Segments (the loops, then the axis line if given), the constraints to
    set in order, and the degrees of freedom left (0 = fully defined)."""
    extra = [("line", axis[0], axis[1])] if axis else []
    segs = [seg for loop in loops for seg in loop]
    axis_index = len(segs) if axis else None
    segments, structural, fixing = candidates(loops, axis_index)
    segments = segments + extra
    kept, left = select(segments, structural + fixing)
    return segments, kept, left
