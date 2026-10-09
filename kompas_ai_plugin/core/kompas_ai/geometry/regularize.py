"""Make the geometry exact: the values written on the drawing are the truth.

Coordinates read from a PDF carry its rounding (KOMPAS: 1/300", ≈0.085 mm),
so a Ø10 hole comes out Ø9.99 and a 45° side 45.2°. A designer's drawing is
defined by its dimensions, so the geometry is corrected to them:

1. nearly horizontal/vertical lines become exactly horizontal/vertical;
2. X and Y coordinates of all points are clustered (points on one vertical
   line, concentric centres … share one X); horizontal dimensions fix the
   distances between X clusters, vertical ones between Y clusters, and the
   cluster positions are solved by least squares — measured positions are a
   weak pull, dimensions a strong one;
3. circles and arcs with a diameter/radius dimension get exactly that radius.

Corrections are small by construction (only dimensions that already agree
with the geometry within rounding are used); the report lists the largest.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .. import ir

AXIS_SNAP_DEG = 0.35
CLUSTER_TOL = 0.12  # mm on the sheet: one PDF rounding step and a bit
DIM_WEIGHT = 1e10  # dimensions are effectively hard constraints
MAX_CORRECTION = 0.5  # mm on the sheet; larger means a dimension conflicts


@dataclass
class RegularizeReport:
    lines_straightened: int = 0
    dimensions_used: int = 0
    radii_set: int = 0
    max_shift: float = 0.0
    skipped: list[str] = field(default_factory=list)

    def text(self) -> str:
        out = (f"Геометрия выровнена по размерам: размеров использовано {self.dimensions_used}, "
               f"радиусов задано {self.radii_set}, линий выпрямлено {self.lines_straightened}, "
               f"наибольший сдвиг точки {self.max_shift:.3f} мм")
        if self.skipped:
            out += "\n  не использованы (противоречат геометрии): " + ", ".join(self.skipped)
        return out


def regularize(drawing: ir.Drawing) -> RegularizeReport:
    report = RegularizeReport()
    scale = drawing.scale.value or 1.0
    _straighten(drawing, report)

    dims = [d for d in drawing.of_type(ir.Dimension)
            if d.dim_type == "linear" and d.p1 and d.p2 and d.nominal
            and d.orientation in ("horizontal", "vertical") and d.confidence >= ir.REVIEW_THRESHOLD]
    for axis in (0, 1):
        orientation = "horizontal" if axis == 0 else "vertical"
        _solve_axis(drawing, [d for d in dims if d.orientation == orientation], axis, scale, report)

    _set_radii(drawing, scale, report)
    return report


# --- 1. horizontal / vertical -------------------------------------------------------


def _straighten(drawing: ir.Drawing, report: RegularizeReport) -> None:
    for line in drawing.of_type(ir.Line):
        (x1, y1), (x2, y2) = line.p1, line.p2
        ang = math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180.0
        if min(ang, 180.0 - ang) <= AXIS_SNAP_DEG and y1 != y2:
            y = (y1 + y2) / 2
            line.p1, line.p2 = (x1, y), (x2, y)
            report.lines_straightened += 1
        elif abs(ang - 90.0) <= AXIS_SNAP_DEG and x1 != x2:
            x = (x1 + x2) / 2
            line.p1, line.p2 = (x, y1), (x, y2)
            report.lines_straightened += 1


# --- 2. coordinates from dimensions ---------------------------------------------------


def _points(drawing: ir.Drawing):
    """(getter, setter) pairs for every point the correction may move."""
    def attr(obj, name):
        return (lambda: getattr(obj, name)), (lambda v: setattr(obj, name, v))

    for e in drawing.entities:
        if isinstance(e, ir.Line):
            yield attr(e, "p1")
            yield attr(e, "p2")
        elif isinstance(e, (ir.Circle, ir.Arc)):
            yield attr(e, "center")
        elif isinstance(e, ir.PointMark):
            yield attr(e, "position")
        elif isinstance(e, ir.Dimension):
            for name in ("p1", "p2", "line_point", "center"):
                if getattr(e, name) is not None:
                    yield attr(e, name)
        elif isinstance(e, ir.Hatch):
            for ring in e.contours:
                for i in range(len(ring)):
                    yield (lambda r=ring, i=i: r[i]), (lambda v, r=ring, i=i: r.__setitem__(i, v))


def _clusters(values: list[float]) -> list[list[float]]:
    out: list[list[float]] = []
    for v in sorted(values):
        if out and v - out[-1][-1] <= CLUSTER_TOL and v - out[-1][0] <= 2 * CLUSTER_TOL:
            out[-1].append(v)
        else:
            out.append([v])
    return out


def _solve_axis(drawing, dims, axis: int, scale: float, report: RegularizeReport) -> None:
    if not dims:
        return
    points = list(_points(drawing))
    values = [get()[axis] for get, _ in points]
    clusters = _clusters(values)
    centers = [sum(c) / len(c) for c in clusters]

    def index(v: float) -> int:
        return min(range(len(centers)), key=lambda k: abs(centers[k] - v))

    rows, rhs, weights, used = [], [], [], []
    pinned: set[int] = set()  # clusters a dimension refers to
    n = len(centers)
    for k, c in enumerate(centers):  # weak pull to the measured position
        row = np.zeros(n)
        row[k] = 1.0
        rows.append(row), rhs.append(c), weights.append(1.0)
    for d in dims:
        a, b = index(d.p1[axis]), index(d.p2[axis])
        if a == b:
            continue
        target = d.nominal * scale * math.copysign(1.0, centers[b] - centers[a])
        if abs((centers[b] - centers[a]) - target) > MAX_CORRECTION:
            report.skipped.append(d.id)
            continue
        row = np.zeros(n)
        row[b], row[a] = 1.0, -1.0
        rows.append(row), rhs.append(target), weights.append(DIM_WEIGHT)
        used.append(d)
        pinned.update((a, b))
    if not used:
        return
    w = np.sqrt(np.asarray(weights))
    solved, *_ = np.linalg.lstsq(np.asarray(rows) * w[:, None], np.asarray(rhs) * w, rcond=None)
    shift = solved - np.asarray(centers)
    if np.abs(shift).max() > MAX_CORRECTION:  # dimensions contradict each other
        report.skipped.extend(d.id for d in used)
        return
    report.dimensions_used += len(used)
    report.max_shift = max(report.max_shift, float(np.abs(shift).max()))
    for (get, set_), v in zip(points, values):
        k = index(v)
        if abs(centers[k] - v) > 2 * CLUSTER_TOL:
            continue
        p = list(get())
        if k in pinned:
            # a dimensioned coordinate is one value of the design: unify its points
            p[axis] = round(float(solved[k]), 6)
        else:
            p[axis] = v + float(shift[k])
        set_((p[0], p[1]))
    for d in used:
        d.measured = round(d.nominal * scale, 6)


# --- 3. radii -------------------------------------------------------------------------


def _set_radii(drawing: ir.Drawing, scale: float, report: RegularizeReport) -> None:
    curves = {e.id: e for e in drawing.entities if isinstance(e, (ir.Circle, ir.Arc))}
    for d in drawing.of_type(ir.Dimension):
        if d.dim_type not in ("diameter", "radius") or not d.ref or not d.nominal:
            continue
        curve = curves.get(d.ref)
        if curve is None or d.confidence < ir.REVIEW_THRESHOLD:
            continue
        radius = d.nominal * scale / (2 if d.dim_type == "diameter" else 1)
        if abs(radius - curve.radius) > MAX_CORRECTION:
            report.skipped.append(d.id)
            continue
        curve.radius = round(radius, 6)
        d.radius = curve.radius
        d.measured = round(d.nominal * scale, 6)
        if d.center:
            d.center = curve.center
        report.radii_set += 1


SNAP_ANNOTATION = 0.15  # sheet mm


def snap_annotations(drawing: ir.Drawing, tol: float = SNAP_ANNOTATION) -> int:
    """Measured points of dimensions and hatch outlines back onto the geometry.

    The geometry is straightened and set to the dimensions after the hatches
    and dimensions were read, so their points may be a tenth of a millimetre
    off the lines they belong to: the hatch then pokes out of its outline and
    an arrow stops short of the line. Each such point goes to the nearest end
    of a line or arc, or else onto the nearest line. Returns how many moved."""
    ends, lines = [], []
    for e in drawing.entities:
        if isinstance(e, ir.Line) and e.style != ir.STYLE_AXIAL:
            ends += [tuple(e.p1), tuple(e.p2)]
            lines.append((tuple(e.p1), tuple(e.p2)))
        elif isinstance(e, ir.Arc):
            for a in (e.start_angle, e.end_angle):
                t = math.radians(a)
                ends.append((e.center[0] + e.radius * math.cos(t),
                             e.center[1] + e.radius * math.sin(t)))

    def snap(p):
        best = min(ends, key=lambda q: math.dist(p, q), default=None)
        if best is not None and math.dist(p, best) <= tol:
            return best
        near, gap = None, tol
        for a, b in lines:
            dx, dy = b[0] - a[0], b[1] - a[1]
            n2 = dx * dx + dy * dy
            if n2 < 1e-12:
                continue
            k = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / n2
            if 0.0 <= k <= 1.0:
                q = (a[0] + k * dx, a[1] + k * dy)
                if math.dist(p, q) < gap:
                    near, gap = q, math.dist(p, q)
        return near or p

    moved = 0
    for d in drawing.of_type(ir.Dimension):
        if d.dim_type != "linear":
            continue
        for name in ("p1", "p2"):
            p = getattr(d, name)
            if p is not None:
                q = snap(tuple(p))
                if q != tuple(p):
                    setattr(d, name, (round(q[0], 6), round(q[1], 6)))
                    moved += 1
    for h in drawing.of_type(ir.Hatch):
        for ring in h.contours:
            for i, p in enumerate(ring):
                q = snap(tuple(p))
                if q != tuple(p):
                    ring[i] = (round(q[0], 6), round(q[1], 6))
                    moved += 1
    return moved


STRAIGHT_DEG = 2.0  # a line this close to horizontal/vertical is meant to be so
JOIN = 0.25  # sheet mm: ends this close are one point of the contour
CROSS_MOVE = 0.08  # sheet mm a joint may move to the crossing of its curves


def close_contour(drawing: ir.Drawing) -> tuple[int, int]:
    """Make the contour exact, so a hatch fills it and KOMPAS constraints
    hold without moving anything:
      * lines within STRAIGHT_DEG of horizontal/vertical become exactly so
        (a slant that small is never meant; real slopes carry an angle);
      * ends that nearly meet are put on one point — where the lines (and
        circles) of the meeting objects cross;
      * an end that stops at another line is put onto that line.
    Returns (lines straightened, ends joined)."""
    from ..model3d.endview import _meet

    straightened = 0
    for line in drawing.of_type(ir.Line):
        (x1, y1), (x2, y2) = line.p1, line.p2
        ang = math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180.0
        if 0 < min(ang, 180.0 - ang) <= STRAIGHT_DEG and y1 != y2:
            y = (y1 + y2) / 2
            line.p1, line.p2 = (x1, y), (x2, y)
            straightened += 1
        elif 0 < abs(ang - 90.0) <= STRAIGHT_DEG and x1 != x2:
            x = (x1 + x2) / 2
            line.p1, line.p2 = (x, y1), (x, y2)
            straightened += 1

    # the contour only: thin lines (thread roots, hatch-free marks) meet the
    # contour where they please
    pieces = [e for e in drawing.entities if isinstance(e, (ir.Line, ir.Arc))
              and e.style == ir.STYLE_MAIN]

    def seg(e):
        if isinstance(e, ir.Line):
            return ("line", tuple(e.p1), tuple(e.p2))
        return ("arc", tuple(e.center), e.radius, e.start_angle, e.end_angle)

    def end(e, k):
        if isinstance(e, ir.Line):
            return tuple(e.p1 if k == 0 else e.p2)
        a = math.radians(e.start_angle if k == 0 else e.end_angle)
        return (e.center[0] + e.radius * math.cos(a), e.center[1] + e.radius * math.sin(a))

    def put(e, k, p):
        if isinstance(e, ir.Line):
            if k == 0:
                e.p1 = (round(p[0], 6), round(p[1], 6))
            else:
                e.p2 = (round(p[0], 6), round(p[1], 6))
        else:
            a = round(math.degrees(math.atan2(p[1] - e.center[1], p[0] - e.center[0])) % 360.0, 6)
            if k == 0:
                e.start_angle = a
            else:
                e.end_angle = a

    # clusters of ends
    nodes: list[list[tuple]] = []
    for e in pieces:
        for k in (0, 1):
            p = end(e, k)
            for node in nodes:
                if math.dist(node[0][2], p) <= JOIN:
                    node.append((e, k, p))
                    break
            else:
                nodes.append([(e, k, p)])
    joined = 0
    for node in nodes:
        if len(node) < 2:
            continue
        if all(math.dist(node[0][2], m[2]) < 1e-9 for m in node):
            continue
        # lines first (horizontals/verticals fix a coordinate), then arcs
        order = sorted(node, key=lambda m: 0 if isinstance(m[0], ir.Line) else 1)
        a, b = order[0], order[1]
        near = tuple(sum(m[2][i] for m in node) / len(node) for i in (0, 1))
        target = _meet(seg(a[0]), seg(b[0]), near) if a[0] is not b[0] else near
        if math.dist(target, near) > CROSS_MOVE:
            # a line nearly tangent to the arc crosses its circle far off:
            # the joint stays where it is, on the arc when there is one
            arcs = [m[0] for m in node if isinstance(m[0], ir.Arc)]
            target = near
            if arcs:
                c, r = arcs[0].center, arcs[0].radius
                d = math.dist(c, near) or 1.0
                target = (c[0] + (near[0] - c[0]) * r / d, c[1] + (near[1] - c[1]) * r / d)
        for e, k, _ in node:
            put(e, k, target)
        joined += 1

    # an end resting on another line (a T joint) goes onto it
    lines = [e for e in pieces if isinstance(e, ir.Line)]
    for node in nodes:
        if len(node) != 1:
            continue
        e, k, p = node[0]
        for other in lines:
            if other is e:
                continue
            (ax, ay), (bx, by) = other.p1, other.p2
            dx, dy = bx - ax, by - ay
            n2 = dx * dx + dy * dy
            if n2 < 1e-12:
                continue
            t = ((p[0] - ax) * dx + (p[1] - ay) * dy) / n2
            if not 0.0 < t < 1.0:
                continue
            q = (ax + t * dx, ay + t * dy)
            gap = math.dist(p, q)
            if 1e-9 < gap <= JOIN:
                target = _meet(seg(e), seg(other), q)
                if math.dist(target, q) <= JOIN:
                    put(e, k, target)
                    joined += 1
                break
    return straightened, joined
