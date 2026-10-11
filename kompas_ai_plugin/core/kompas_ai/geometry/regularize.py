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
DIM_NODE = 0.6  # sheet mm: a dimension point this near a contour node measures from it


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

    # neighbours only, through grids: an assembly has thousands of points
    from .constraints import Grid

    end_grid = Grid(1.0)
    for q in ends:
        end_grid.add(q, q)
    line_grid = Grid(5.0)
    for k, (a, b) in enumerate(lines):
        line_grid.add_rect(min(a[0], b[0]) - tol, min(a[1], b[1]) - tol,
                           max(a[0], b[0]) + tol, max(a[1], b[1]) + tol, k)

    def snap(p):
        best = min(end_grid.near(p, tol), key=lambda q: math.dist(p, q), default=None)
        if best is not None and math.dist(p, best) <= tol:
            return best
        near, gap = None, tol
        for a, b in (lines[k] for k in sorted(line_grid.at(p))):
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

    # dimensions measure from the contour's own points: an end of the main
    # contour within DIM_NODE is the point, exactly
    nodes = []
    for e in drawing.entities:
        if isinstance(e, ir.Line) and e.style == ir.STYLE_MAIN:
            nodes += [tuple(e.p1), tuple(e.p2)]
        elif isinstance(e, ir.Arc) and e.style == ir.STYLE_MAIN:
            for a in (e.start_angle, e.end_angle):
                t = math.radians(a)
                nodes.append((e.center[0] + e.radius * math.cos(t),
                              e.center[1] + e.radius * math.sin(t)))

    curves = [e for e in drawing.entities if isinstance(e, (ir.Arc, ir.Circle))
              and e.style == ir.STYLE_MAIN]
    centres = [tuple(e.center) for e in drawing.entities
               if isinstance(e, (ir.Arc, ir.Circle, ir.Ellipse))]

    node_grid, centre_grid, curve_grid = Grid(1.0), Grid(1.0), Grid(5.0)
    for q in nodes:
        node_grid.add(q, q)
    for q in centres:
        centre_grid.add(q, q)
    for k, e in enumerate(curves):
        curve_grid.add_box(e.center, e.radius + tol, k)

    def snap_dim(p):
        best = min(node_grid.near(p, DIM_NODE), key=lambda q: math.dist(p, q), default=None)
        if best is not None and math.dist(p, best) <= DIM_NODE:
            return best
        c = min(centre_grid.near(p, tol), key=lambda q: math.dist(p, q), default=None)
        if c is not None and math.dist(p, c) <= tol:
            return c  # from the centre of a hole or an arc
        for e in (curves[k] for k in sorted(curve_grid.at(p))):  # a point of an arc
            d = math.dist(p, e.center)
            if d > 0 and abs(d - e.radius) <= tol:
                return (e.center[0] + (p[0] - e.center[0]) * e.radius / d,
                        e.center[1] + (p[1] - e.center[1]) * e.radius / d)
        return snap(p)

    def on_contour(q):
        if any(math.dist(q, n) <= 1e-6 for n in node_grid.near(q, 0.01)) \
                or q in centre_grid.near(q, 0.01):
            return True
        return any(_line_gap(q, a, b) <= 1e-4 and _between(q, a, b)
                   for a, b in (lines[k] for k in line_grid.at(q)))

    def slide(p, orientation):
        """A point that lies on nothing: along its extension line (vertical
        for a horizontal size, horizontal for a vertical one) to the nearest
        corner of the contour on that line — the point the size measures."""
        k = 0 if orientation == "horizontal" else 1 if orientation == "vertical" else None
        if k is None:
            return p
        on_line = [n for n in nodes if abs(n[k] - p[k]) <= 0.05]
        best = min(on_line, key=lambda n: abs(n[1 - k] - p[1 - k]), default=None)
        return best if best is not None and abs(best[1 - k] - p[1 - k]) <= SLIDE else p

    moved = 0
    for d in drawing.of_type(ir.Dimension):
        if d.dim_type != "linear":
            continue
        for name in ("p1", "p2"):
            p = getattr(d, name)
            if p is not None:
                q = snap_dim(tuple(p))
                if not on_contour(q):
                    q = slide(q, d.orientation)
                if q != tuple(p):
                    setattr(d, name, (round(q[0], 6), round(q[1], 6)))
                    moved += 1
    moved += _snap_angles(drawing)
    for h in drawing.of_type(ir.Hatch):
        for ring in h.contours:
            for i, p in enumerate(ring):
                q = snap(tuple(p))
                if q != tuple(p):
                    ring[i] = (round(q[0], 6), round(q[1], 6))
                    moved += 1
    return moved


SLIDE = 120.0  # sheet mm a dimension point may slide along its extension line
ANGLE_ON_LINE = "стороны угла на контуре"  # a note: the writer keeps the sides as they are
SIDE_DEG = 2.0  # a side of an angle this close in direction to a line lies on it
SIDE_GAP = 1.2  # sheet mm the vertex may be off a line its side lies on


def _snap_angles(drawing: ir.Drawing) -> int:
    """The sides of an angle lie on the lines of the contour (or on an axis)
    and its vertex where they cross — exactly, so the dimension's extension
    lines run on the part's own lines."""
    lines = [l for l in drawing.of_type(ir.Line)
             if l.style in (ir.STYLE_MAIN, ir.STYLE_AXIAL) and math.dist(l.p1, l.p2) > 1e-6]

    def side_line(c, p):
        a = math.atan2(p[1] - c[1], p[0] - c[0])
        best = None
        for l in lines:
            b = math.atan2(l.p2[1] - l.p1[1], l.p2[0] - l.p1[0])
            diff = abs((math.degrees(a - b) + 90.0) % 180.0 - 90.0)
            if diff > SIDE_DEG:
                continue
            gap = _line_gap(c, l.p1, l.p2)
            if gap <= SIDE_GAP and (best is None or (gap, diff) < best[0]):
                best = ((gap, diff), l)
        return best[1] if best else None

    moved = 0
    for d in drawing.of_type(ir.Dimension):
        if d.dim_type != "angular" or not (d.center and d.p1 and d.p2):
            continue
        c = tuple(d.center)
        l1, l2 = side_line(c, d.p1), side_line(c, d.p2)
        if l1 is None and l2 is None:
            continue
        if l1 is not None and l2 is not None and l1 is not l2:
            x = _crossing(l1.p1, l1.p2, l2.p1, l2.p2)
            if x is None or math.dist(x, c) > SIDE_GAP:
                continue
            new_c = x
            p1, p2 = _foot(d.p1, l1.p1, l1.p2), _foot(d.p2, l2.p1, l2.p2)
        else:
            l = l1 if l1 is not None else l2
            new_c = _foot(c, l.p1, l.p2)
            shift = (new_c[0] - c[0], new_c[1] - c[1])
            p1 = _foot(d.p1, l.p1, l.p2) if l1 is not None else \
                (d.p1[0] + shift[0], d.p1[1] + shift[1])
            p2 = _foot(d.p2, l.p1, l.p2) if l2 is not None else \
                (d.p2[0] + shift[0], d.p2[1] + shift[1])
        d.center = (round(new_c[0], 6), round(new_c[1], 6))
        d.p1 = (round(p1[0], 6), round(p1[1], 6))
        d.p2 = (round(p2[0], 6), round(p2[1], 6))
        if l1 is not None and l2 is not None:
            d.notes.append(ANGLE_ON_LINE)
        moved += 1
    return moved


def _between(p, a, b) -> bool:
    dx, dy = b[0] - a[0], b[1] - a[1]
    k = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / ((dx * dx + dy * dy) or 1.0)
    return -1e-6 <= k <= 1 + 1e-6


def _line_gap(p, a, b) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    return abs((p[0] - a[0]) * dy - (p[1] - a[1]) * dx) / math.hypot(dx, dy)


def _foot(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    k = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)
    return (a[0] + k * dx, a[1] + k * dy)


def _crossing(a1, a2, b1, b2):
    d = (a2[0] - a1[0]) * (b2[1] - b1[1]) - (a2[1] - a1[1]) * (b2[0] - b1[0])
    if abs(d) < 1e-12:
        return None
    t = ((b1[0] - a1[0]) * (b2[1] - b1[1]) - (b1[1] - a1[1]) * (b2[0] - b1[0])) / d
    return (a1[0] + t * (a2[0] - a1[0]), a1[1] + t * (a2[1] - a1[1]))


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
        near = tuple(sum(m[2][i] for m in node) / len(node) for i in (0, 1))
        # a horizontal fixes y, a vertical x: they stay exact whatever meets them
        hy = [m[0].p1[1] for m in node if isinstance(m[0], ir.Line) and m[0].p1[1] == m[0].p2[1]]
        vx = [m[0].p1[0] for m in node if isinstance(m[0], ir.Line) and m[0].p1[0] == m[0].p2[0]]
        arcs = [m[0] for m in node if isinstance(m[0], ir.Arc)]
        if hy and vx:
            target = (vx[0], hy[0])
        elif (hy or vx) and arcs:
            # the circle crossed by the horizontal (vertical) line
            line = next(m[0] for m in node if isinstance(m[0], ir.Line)
                        and (m[0].p1[1] == m[0].p2[1] if hy else m[0].p1[0] == m[0].p2[0]))
            target = _meet(seg(line), seg(arcs[0]), near)
        elif hy or vx:
            target = (vx[0] if vx else near[0], hy[0] if hy else near[1])
            others = [m[0] for m in node if isinstance(m[0], ir.Line)
                      and m[0].p1[1] != m[0].p2[1] and m[0].p1[0] != m[0].p2[0]]
            if others:  # a slanted line ends on the horizontal/vertical one
                axis_line = next(m[0] for m in node if isinstance(m[0], ir.Line)
                                 and (m[0].p1[1] == m[0].p2[1] or m[0].p1[0] == m[0].p2[0]))
                target = _meet(seg(axis_line), seg(others[0]), near)
        else:
            order = sorted(node, key=lambda m: 0 if isinstance(m[0], ir.Line) else 1)
            a, b = order[0], order[1]
            target = _meet(seg(a[0]), seg(b[0]), near) if a[0] is not b[0] else near
        if math.dist(target, near) > CROSS_MOVE and not (hy and vx):
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


ANGLE_SNAP = 2.0  # degrees: a line this close to a standard angle runs at it
STANDARD_ANGLES = (0.0, 15.0, 30.0, 45.0, 60.0, 75.0, 90.0, 105.0, 120.0, 135.0, 150.0, 165.0)


def _dimensioned_angles(drawing: ir.Drawing) -> tuple:
    """Directions (degrees, mod 180) the written angles ask for: a cone of
    45° about an axis wants its sides at the axis ± 22.5°; an angle from a
    horizontal or vertical side wants the other side that far from it. The
    number wins over the lines, for angles too."""
    out = []
    for d in drawing.of_type(ir.Dimension):
        if d.dim_type != "angular" or not (d.nominal and d.center and d.p1 and d.p2):
            continue
        a1 = math.degrees(math.atan2(d.p1[1] - d.center[1], d.p1[0] - d.center[0]))
        a2 = math.degrees(math.atan2(d.p2[1] - d.center[1], d.p2[0] - d.center[0]))
        if (a2 - a1) % 360.0 > 180.0:
            a1, a2 = a2, a1
        sweep = (a2 - a1) % 360.0
        if abs(sweep - d.nominal) > 2.0:
            continue
        mid = a1 + sweep / 2
        for ref, others in ((mid, (mid - d.nominal / 2, mid + d.nominal / 2)),
                            (a1, (a1 + d.nominal,)), (a2, (a2 - d.nominal,))):
            near = min(STANDARD_ANGLES + (180.0,), key=lambda v: abs(ref % 180.0 - v))
            if abs(ref % 180.0 - near) <= 1.0:  # measured from an axis-true direction
                shift = near - ref % 180.0
                out += [round((o + shift) % 180.0, 6) for o in others]
                break
    return tuple(out)


def solve_contour(drawing: ir.Drawing) -> dict:
    """The contour as one system of conditions, solved together (a sketch
    solver in small). Unknowns: the nodes where ends meet and the centres of
    the arcs and circles. Conditions:
      * the ends of a node coincide exactly (they are one unknown);
      * a line near horizontal, vertical or a standard angle (chamfer 45°,
        cone 30°) runs exactly so;
      * a node of an arc lies on its circle; a fillet that meets a line
        nearly tangentially meets it exactly tangentially;
      * an end resting on another line (or on an axis) lies on it;
      * every written size holds exactly: the number wins over the lines; a
        diameter across an axis is symmetric about it;
      * a size nobody wrote, that the written ones leave free, takes the
        nearest round value (5.001 → 5).
    Of all positions keeping these, the one nearest the drawing is taken
    (least squares, Gauss–Newton). One rule at a time undid the others:
    joining two ends tilted the horizontal that had just been made exact."""
    from .constraints import Grid

    _SKIPPED.clear()
    _REJECTED.clear()
    scale = drawing.scale.value or 1.0
    pieces = [e for e in drawing.entities if isinstance(e, (ir.Line, ir.Arc))
              and e.style == ir.STYLE_MAIN]
    axes = [e for e in drawing.of_type(ir.Line) if e.style == ir.STYLE_AXIAL]
    # holes: circles, and ellipses (a hole seen at a slant); sizes go to their centres
    circles = [e for e in drawing.entities if isinstance(e, (ir.Circle, ir.Ellipse))
               and e.style == ir.STYLE_MAIN]
    rounded, fixed_radius = _round_radii(drawing, scale)

    def end(e, k):
        if isinstance(e, ir.Line):
            return tuple(e.p1 if k == 0 else e.p2)
        a = math.radians(e.start_angle if k == 0 else e.end_angle)
        return (e.center[0] + e.radius * math.cos(a), e.center[1] + e.radius * math.sin(a))

    nodes: list[list] = []
    member_node = {}
    grid = Grid(1.0)
    for e in pieces:
        for k in (0, 1):
            p = end(e, k)
            near = [i for i in grid.near(p, JOIN) if math.dist(nodes[i][0], p) <= JOIN]
            if near:
                i = min(near)
                nodes[i][1].append((e, k))
                member_node[(id(e), k)] = i
            else:
                member_node[(id(e), k)] = len(nodes)
                grid.add(p, len(nodes))
                nodes.append([p, [(e, k)]])
    n = len(nodes)
    if n == 0:
        return {"nodes": 0}
    arcs = [e for e in pieces if isinstance(e, ir.Arc)]
    arc_var = {id(a): n + j for j, a in enumerate(arcs)}  # unknown index of the centre
    circle_var = {id(c): n + len(arcs) + j for j, c in enumerate(circles)}
    points = [node[0] for node in nodes] + [tuple(a.center) for a in arcs] \
        + [tuple(c.center) for c in circles]

    lines = [e for e in pieces if isinstance(e, ir.Line)]
    angles = _dimensioned_angles(drawing)
    direction = {}
    conds = []
    for line in lines:
        a, b = member_node[(id(line), 0)], member_node[(id(line), 1)]
        if a == b:
            continue
        (x1, y1), (x2, y2) = line.p1, line.p2
        ang = math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180.0
        best = min(STANDARD_ANGLES + (180.0,) + angles, key=lambda v: abs(ang - v))
        if abs(ang - best) <= ANGLE_SNAP:
            th = math.radians(best % 180.0)
            conds.append(("dir", a, b, th))
            direction[id(line)] = th
    # the written sizes first: a size across a circle sets its radius
    curves = [(arc_var[id(a)], a.radius, a) for a in arcs] \
        + [(circle_var[id(e)], e.radius, e) for e in circles if isinstance(e, ir.Circle)]
    segments = [(member_node[(id(e), 0)], member_node[(id(e), 1)]) for e in lines]
    dim_conds, used, skipped, correction = _dimension_conds(drawing, points, axes, scale, curves,
                                                            segments)
    anchored = list(used)  # every size held on points, kept or not in the end
    # an arc nobody sized (nor measured from) has its radius as an unknown
    held = {u[k][1] for u in used for k in (2, 3) if u[k] and u[k][0] == "pt" and u[k][2]}
    radius_var = {}
    for arc in arcs:
        if id(arc) not in fixed_radius and arc_var[id(arc)] not in held:
            radius_var[id(arc)] = len(points)
            points.append((arc.radius, 0.0))
    size = 2 * len(points)
    x0 = np.array([c for p in points for c in p], dtype=float)
    for arc in arcs:
        for k in (0, 1):
            i = member_node[(id(arc), k)]
            if id(arc) in radius_var:
                conds.append(("circleR", i, arc_var[id(arc)], radius_var[id(arc)]))
            else:
                conds.append(("circle", i, arc_var[id(arc)], arc.radius))
            # a line leaving this node nearly along the arc's tangent: tangent
            p = end(arc, k)
            for e, kk in nodes[i][1]:
                if not isinstance(e, ir.Line) or id(e) not in direction:
                    continue
                th = direction[id(e)]
                rx, ry = p[0] - arc.center[0], p[1] - arc.center[1]
                cosang = abs(rx * math.cos(th) + ry * math.sin(th)) / (math.hypot(rx, ry) or 1.0)
                if cosang < math.sin(math.radians(5.0)):
                    conds.append(("tangent", i, arc_var[id(arc)], th))
    line_grid = Grid(5.0)
    for j, line in enumerate(lines + axes):
        (ax, ay), (bx, by) = line.p1, line.p2
        line_grid.add_rect(min(ax, bx) - JOIN, min(ay, by) - JOIN,
                           max(ax, bx) + JOIN, max(ay, by) + JOIN, j)
    near_line = lines + axes
    for i, (p, members) in enumerate(nodes):
        if len(members) != 1:
            continue
        own = members[0][0]
        for line in (near_line[j] for j in sorted(line_grid.at(p))):
            if line is own:
                continue
            (ax, ay), (bx, by) = line.p1, line.p2
            dx, dy = bx - ax, by - ay
            n2 = dx * dx + dy * dy
            if n2 < 1e-12:
                continue
            t = ((p[0] - ax) * dx + (p[1] - ay) * dy) / n2
            q = (ax + t * dx, ay + t * dy)
            if -0.02 < t < 1.02 and math.dist(p, q) <= JOIN:
                if line.style == ir.STYLE_AXIAL:
                    conds.append(("onfixed", i, (ax, ay), (bx, by)))
                else:
                    a, b = member_node[(id(line), 0)], member_node[(id(line), 1)]
                    if i not in (a, b):
                        conds.append(("online", i, a, b))
                break
    for c in circles:  # a hole touching a straight wall touches it exactly (a drilled
        if not isinstance(c, ir.Circle):  # channel at the cavity's end)
            continue
        for line in lines:
            a, b = member_node[(id(line), 0)], member_node[(id(line), 1)]
            if direction.get(id(line)) not in (0.0, math.pi / 2):
                continue
            k = 1 if direction[id(line)] == 0.0 else 0  # across the line
            level = line.p1[k]
            gap = c.center[k] - level
            if abs(abs(gap) - c.radius) <= 0.1 and _between(c.center, line.p1, line.p2):
                conds.append(("dx", a, circle_var[id(c)], k, math.copysign(c.radius, gap)))
    conds += _symmetric_holes(circles, circle_var, arcs, arc_var, points)
    for c in circles:  # a hole on an axis stays on it (its own centre mark goes with it)
        for axis in axes:
            if not _centre_mark(c, axis) and _line_gap(c.center, axis.p1, axis.p2) <= JOIN and _between(c.center, axis.p1, axis.p2):
                conds.append(("onfixed", circle_var[id(c)], tuple(axis.p1), tuple(axis.p2)))
                break

    conds += dim_conds
    conds += _same_levels(points, conds, set(radius_var.values()))
    levels = [(0 if abs(a.p1[0] - a.p2[0]) < 1e-9 else 1, a.p1[0] if abs(a.p1[0] - a.p2[0]) < 1e-9
               else a.p1[1]) for a in axes
              if abs(a.p1[0] - a.p2[0]) < 1e-9 or abs(a.p1[1] - a.p2[1]) < 1e-9]

    x, dropped = x0.copy(), 0
    allow = MAX_NODE_SHIFT + correction
    cache: dict = {}  # outlines whose conditions a round left alone are not solved again
    for round_ in range(5):
        x, plain = _solve_parts(conds, x0, size, nice=(scale, levels, set(radius_var.values())),
                                cache=cache)
        # the round values move points a little more, by design: judged without them
        shift = np.hypot((plain - x0)[0::2], (plain - x0)[1::2])
        far = {i for i in range(len(shift)) if shift[i] > allow}
        if not far:
            break
        # conditions that drag a point this far contradict the drawing (a
        # slope that is not a standard one, a wrong contact): left out there;
        # the written sizes go last
        keep = [c for c in conds if not far & _cond_vars(c)
                or (c[0][0] == "D" and round_ < 3)]
        if len(keep) == len(conds):
            keep = [c for c in conds if not far & _cond_vars(c)]
        lost = {id(c) for c in conds} - {id(c) for c in keep}
        skipped += [u[1].id for u in used if id(u[0]) in lost]
        used = [u for u in used if id(u[0]) not in lost]
        dropped += len(conds) - len(keep)
        conds = keep
    else:
        x = x0.copy()  # no consistent set found: the drawing stays as it is
        used = []

    if _REJECTED:
        skipped += sorted(set(_REJECTED))
        used = [u for u in used if u[1].id not in set(_REJECTED)]
    moved = float(np.abs(x - x0).max())
    for arc in arcs:
        if id(arc) in radius_var:
            arc.radius = float(x[2 * radius_var[id(arc)]])
    for c in circles:
        j = circle_var[id(c)]
        _move_centre(c, (float(x[2 * j]), float(x[2 * j + 1])), axes)
    result = _write_back(drawing, nodes, arcs, arc_var, x, end, moved, n, len(direction), dropped)
    kept = {id(u[1]) for u in used}
    for _, d, a, b in anchored:
        # the size measures exactly the points it was held on (also one that
        # gave way: its points follow the geometry, its number stays written)
        k = 0 if d.orientation == "horizontal" else 1
        for name, anc in (("p1", a), ("p2", b)):
            if anc is not None and anc[0] == "pt":
                q = [float(x[2 * anc[1]]), float(x[2 * anc[1] + 1])]
                q[k] += anc[2]
                setattr(d, name, tuple(q))
        if id(d) in kept:
            d.measured = round(d.nominal * _view_scale(d, scale), 6)
        elif d.p1 and d.p2 and d.orientation in ("horizontal", "vertical"):
            d.measured = round(abs(d.p2[k] - d.p1[k]), 6)
    result["dims"] = len({u[1].id for u in used})
    result["dims_skipped"] = sorted(set(skipped))
    result["rounded"] = rounded + _NICE[0]
    result["left_as_drawn"] = list(_SKIPPED)
    return result


def _same_hole(a, b) -> bool:
    if type(a) is not type(b):
        return False
    if isinstance(a, ir.Circle):
        return abs(a.radius - b.radius) <= 0.02 * max(a.radius, b.radius)
    return abs(a.a - b.a) <= 0.03 * a.a and abs(a.b - b.b) <= 0.03 * a.b \
        and abs((a.angle - b.angle + 90.0) % 180.0 - 90.0) <= 2.0


def _symmetric_holes(holes, hole_var, arcs, arc_var, points) -> list:
    """Two equal holes on either side of a centre (of a circle or an arc of
    the view) stay symmetric about it: a size given to one of them holds for
    the other (15 from the centre on one side is 15 on the other)."""
    if len(holes) > 200:
        return []
    centres = [hole_var[id(h)] for h in holes if isinstance(h, ir.Circle)] \
        + [arc_var[id(a)] for a in arcs]
    out = []
    for i, a in enumerate(holes):
        for b in holes[i + 1:]:
            if not _same_hole(a, b) or math.dist(a.center, b.center) < 1.0:
                continue
            mid = ((a.center[0] + b.center[0]) / 2, (a.center[1] + b.center[1]) / 2)
            m = min((j for j in centres if j not in (hole_var[id(a)], hole_var[id(b)])),
                    key=lambda j: math.dist(points[j], mid), default=None)
            if m is not None and math.dist(points[m], mid) <= 0.3:
                out += [("mid", hole_var[id(a)], hole_var[id(b)], m, k) for k in (0, 1)]
    return out


def _centre_mark(c, axis) -> bool:
    """A short centre line of this hole, through its centre."""
    reach = 4 * (getattr(c, "radius", 0.0) or max(getattr(c, "a", 0.0), 1.0))
    return math.dist(axis.p1, axis.p2) <= 2 * reach \
        and _line_gap(c.center, axis.p1, axis.p2) <= JOIN and _between(c.center, axis.p1, axis.p2)


def _move_centre(c, new, axes) -> None:
    """A hole moved by its sizes: its centre lines go with it."""
    dx, dy = new[0] - c.center[0], new[1] - c.center[1]
    if abs(dx) < 1e-12 and abs(dy) < 1e-12:
        return
    for a in axes:
        if _centre_mark(c, a):
            a.p1 = (a.p1[0] + dx, a.p1[1] + dy)
            a.p2 = (a.p2[0] + dx, a.p2[1] + dy)
    if isinstance(c, ir.Ellipse):
        def shift(q):
            return [q[0] + dx, q[1] + dy]

        c.arcs = [[a[0], shift(a[1]), shift(a[2])] if a[0] == "line"
                  else [a[0], shift(a[1])] + list(a[2:]) for a in c.arcs]
    c.center = new


MAX_NODE_SHIFT = 0.15  # sheet mm
DIM_SLIDE = 0.6  # sheet mm a dimension's point may be off the coordinate it measures
DIM_LIMIT = 1.5  # sheet mm: a size asking more of the lines measures something else
NICE_STEPS = (1.0, 0.5, 0.1, 0.05)  # model mm: round values, the roundest first
NICE_TOL = 0.15  # sheet mm an unwritten size may be off a round value (PDF rounding)
_NICE = [0]  # sizes made round by the last solve (read by solve_contour)


LEVEL = 0.01  # sheet mm: points this close in X (or Y) are on one level of the design


def _same_levels(points, conds, skip=()) -> list:
    """Points of one X (Y) in one outline stay of one X (Y): the shoulders a
    size measures and the ones it does not are one level of the design, also
    when no line joins them."""
    group = _components(conds, len(points))
    out = []
    for k in (0, 1):
        idx = sorted(range(len(points)), key=lambda i: (group[i], points[i][k]))
        for a, b in zip(idx, idx[1:]):
            if group[a] == group[b] and points[b][k] - points[a][k] <= LEVEL \
                    and a not in skip and b not in skip:
                out.append(("dx", a, b, k, 0.0))
    return out


def _components(conds, count) -> list[int]:
    """The group (a representative point) of every point under the conditions."""
    parent = list(range(count))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for c in conds:
        pts = [c[k] for k in _point_slots(c)]
        for p in pts[1:]:
            a, b = find(pts[0]), find(p)
            if a != b:
                parent[a] = b
    return [find(i) for i in range(count)]


def _view_scale(d, scale: float) -> float:
    """The scale a dimension is drawn in: the sheet's, or its view's own
    (a note «… масштабу 2:1 …» put by the recognition)."""
    import re

    for note in d.notes:
        m = re.search(r"масштабу (\d+(?:[.,]\d+)?):(\d+(?:[.,]\d+)?)", note)
        if m:
            a, b = (float(v.replace(",", ".")) for v in m.groups())
            return a / b if b else scale
    return scale


def _nice(value: float, scale: float, factor: float = 1.0):
    """The roundest value near ``value`` (model mm), or None."""
    tol = max(NICE_TOL * factor / scale, 0.01 * abs(value))
    for step in NICE_STEPS:
        v = round(value / step) * step
        if abs(v - value) <= tol and v > 0:
            return v
    return None


def _round_radii(drawing, scale: float) -> int:
    """Arcs and circles nobody dimensioned: the written radius of one like
    them (R1 on one of two fillets), else the nearest round value."""
    written = {d.ref for d in drawing.of_type(ir.Dimension)
               if d.dim_type in ("radius", "diameter") and d.ref}
    values = [d.nominal / (2 if d.dim_type == "diameter" else 1)
              for d in drawing.of_type(ir.Dimension)
              if d.dim_type in ("radius", "diameter") and d.nominal]
    count, fixed = 0, set()
    for e in drawing.entities:
        if not isinstance(e, (ir.Arc, ir.Circle)) or e.style != ir.STYLE_MAIN:
            continue
        if e.id in written:
            fixed.add(id(e))
            continue
        r = e.radius / scale
        tol = max(NICE_TOL / scale, 0.01 * r)
        same = [v for v in values if abs(v - r) <= tol]
        if same:
            v = min(same, key=lambda v: abs(v - r))
            fixed.add(id(e))
        elif isinstance(e, ir.Arc):
            continue  # its radius is an unknown of the solve, made round there
        else:
            v = _nice(r, scale)
        if v is not None and abs(v * scale - e.radius) > 1e-9:
            e.radius = round(v * scale, 9)
            count += 1
    return count, fixed


def _dimension_conds(drawing, points, axes, scale, curves=(), segments=()):
    """Conditions of the written linear sizes on the solver's points: each
    end of a size is a contour point within DIM_NODE, or the outermost point
    of an arc or circle (its centre ± radius), else a point on its extension
    line, else an axis. An anchor is ("pt", point, offset along the size) or
    ("fix", coordinate). Returns (conditions, [(cond, dim, anchor1,
    anchor2)], skipped ids, largest correction in sheet mm)."""
    import bisect

    order = [sorted(range(len(points)), key=lambda i: points[i][k]) for k in (0, 1)]
    keys = [[points[i][k] for i in order[k]] for k in (0, 1)]

    def along(p, k, tol):
        lo = bisect.bisect_left(keys[k], p[k] - tol)
        hi = bisect.bisect_right(keys[k], p[k] + tol)
        return order[k][lo:hi]

    def extreme(p, k):
        """(gap, centre point, offset) of the arc whose outermost point in
        the size's direction is p."""
        best = None
        for j, r, arc in curves:
            c = points[j]
            for sgn in (1.0, -1.0):
                q = (c[0] + sgn * r, c[1]) if k == 0 else (c[0], c[1] + sgn * r)
                gap = math.dist(p, q)
                if gap > DIM_NODE or (best and gap >= best[0]):
                    continue
                if isinstance(arc, ir.Arc):
                    ang = (0.0 if sgn > 0 else 180.0) if k == 0 else (90.0 if sgn > 0 else 270.0)
                    if (ang - arc.start_angle) % 360.0 > (arc.end_angle - arc.start_angle) % 360.0:
                        continue
                best = (gap, j, sgn * r)
        return best

    def anchor(p, k):
        near = along(p, 0, DIM_NODE)
        near = [i for i in near if math.dist(points[i], p) <= DIM_NODE]
        node = min(near, key=lambda i: math.dist(points[i], p)) if near else None
        ext = extreme(p, k) if k is not None else None
        if node is not None and not (ext and ext[0] < math.dist(points[node], p) - 1e-6):
            return ("pt", node, 0.0)
        if k is None:
            return None
        for i, j in segments:  # on a line across the size: its level
            a, b = points[i], points[j]
            if abs(a[k] - b[k]) <= LEVEL and abs(a[k] - p[k]) <= 0.1 \
                    and min(a[1 - k], b[1 - k]) - 0.1 <= p[1 - k] <= max(a[1 - k], b[1 - k]) + 0.1:
                return ("pt", i, 0.0)
        if ext:  # the outermost point of an arc or circle
            return ("pt", ext[1], ext[2])
        for tol in (0.05, DIM_SLIDE):  # along the extension line to a corner
            on = [i for i in along(p, k, tol) if abs(points[i][1 - k] - p[1 - k]) <= SLIDE]
            if on:
                return ("pt", min(on, key=lambda i: (abs(points[i][k] - p[k]) > 0.05,
                                                      abs(points[i][1 - k] - p[1 - k]))), 0.0)
        for a in axes:  # from an axis
            if abs(a.p1[k] - a.p2[k]) < 1e-9 and abs(a.p1[k] - p[k]) <= DIM_SLIDE:
                return ("fix", a.p1[k])
        return None

    def axis_between(p1, p2, k):
        mid = (p1[k] + p2[k]) / 2
        for a in axes:
            if abs(a.p1[k] - a.p2[k]) < 1e-9 and abs(a.p1[k] - mid) <= DIM_SLIDE:
                lo, hi = sorted((a.p1[1 - k], a.p2[1 - k]))
                if lo - 5.0 <= p1[1 - k] <= hi + 5.0 or lo - 5.0 <= p2[1 - k] <= hi + 5.0:
                    return a.p1[k]
        return None

    def value(anc, k):
        return points[anc[1]][k] + anc[2] if anc[0] == "pt" else anc[1]

    conds, used, skipped, worst = [], [], [], 0.0
    for d in drawing.of_type(ir.Dimension):
        if d.dim_type != "linear" or not d.p1 or not d.p2 or not d.nominal \
                or d.confidence < ir.REVIEW_THRESHOLD:
            continue
        k = 0 if d.orientation == "horizontal" else 1 if d.orientation == "vertical" else None
        target = d.nominal * _view_scale(d, scale)
        a, b = anchor(d.p1, k), anchor(d.p2, k)
        diameter = (d.text or "").lstrip().startswith("Ø") or any("Ø" in n for n in d.notes)
        axis = axis_between(d.p1, d.p2, k) if diameter and k is not None else None
        if k is not None and axis is not None and (a is None) != (b is None):
            # a diameter in a half view: one side drawn, the axis in the middle
            anc = a or b
            if anc[0] == "pt":
                side = value(anc, k) - axis
                miss = abs(abs(side) * 2 - target)
                if miss <= max(DIM_LIMIT, 0.03 * target):
                    cond = ("fix", anc[1], k, axis + math.copysign(target / 2, side) - anc[2])
                    worst = max(worst, miss)
                    conds.append(cond)
                    used.append((cond, d, a, b))
            continue
        if a and b and a[0] == b[0] == "pt" and a[1] == b[1] and k is not None:
            # across one circle (or from its centre): the size is its radius
            span = abs(a[2] - b[2])
            curve = next((e for j, _, e in curves if j == a[1]), None)
            if curve is not None and span > 1e-9:
                r = target * curve.radius / span
                if abs(r - curve.radius) <= max(DIM_LIMIT, 0.03 * r):
                    worst = max(worst, abs(r - curve.radius))
                    curve.radius = r
                    used.append((None, d, a, b))
                else:
                    skipped.append(d.id)
            continue
        if a is None or b is None or a[:2] == b[:2] or (a[0] == "fix" and b[0] == "fix"):
            continue
        if k is None:
            if a[0] != "pt" or b[0] != "pt" or a[2] or b[2]:
                continue
            cur = math.dist(points[a[1]], points[b[1]])
            cond = ("dist", a[1], b[1], target)
        else:
            cur = value(b, k) - value(a, k)
            if abs(cur) < 1e-9:
                continue
            t = math.copysign(target, cur)
            if a[0] == "fix":
                cond = ("fix", b[1], k, a[1] + t - b[2])
            elif b[0] == "fix":
                cond = ("fix", a[1], k, b[1] - t - a[2])
            else:
                cond = ("dx", a[1], b[1], k, t - b[2] + a[2])
        miss = abs(abs(cur) - target)
        if miss > max(DIM_LIMIT, 0.03 * target):
            skipped.append(d.id)
            continue
        worst = max(worst, miss)
        conds.append(cond)
        used.append((cond, d, a, b))
        if axis is not None and cond[0] == "dx":  # Ø across the axis: about it
            conds.append(("sym", cond[1], cond[2], k, axis - (a[2] + b[2]) / 2))
    # tagged as written sizes ("D…", the size's id last), the biggest first:
    # where sizes contradict each other the overall ones win
    nominal = {d.id: d.nominal for d in drawing.of_type(ir.Dimension)}
    owner = {id(u[0]): u[1].id for u in used if u[0] is not None}
    tagged, last = {}, None
    for cond in conds:
        last = owner.get(id(cond), last)
        tagged[id(cond)] = ("D" + cond[0],) + cond[1:] + (last,)
    used = [(tagged.get(id(u[0])), u[1], u[2], u[3]) for u in used]
    conds = sorted(tagged.values(), key=lambda t: -nominal.get(t[-1], 0.0))
    return conds, used, skipped, worst


def _plain(cond):
    """A written size's condition as the plain one (tag and id off)."""
    return (cond[0][1:],) + cond[1:-1] if cond[0][0] == "D" else cond


def _cond_vars(cond) -> set:
    return {cond[k] for k in _point_slots(cond)}


MAX_GROUP = 400  # points of one connected outline the fitting takes on
_SKIPPED: list = []  # sizes of the outlines left as drawn (read by solve_contour)


def _point_slots(cond) -> list[int]:
    """Positions in the condition tuple that hold point indices."""
    kind = cond[0].lstrip("D")
    if kind in ("dir", "circle", "tangent", "dx", "sym", "dist"):
        return [1, 2]
    if kind in ("online", "circleR", "mid"):
        return [1, 2, 3]
    return [1]


def _solve_parts(conds, x0, size, nice=None, cache=None):
    """The contour's conditions fall apart into groups that share no point
    (the parts of an assembly, the views of a sheet): each group is solved on
    its own — the same answer, without one huge system for the whole sheet.
    ``nice`` = (scale, axis levels): sizes left free get round values."""
    parent = list(range(size // 2))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for c in conds:
        pts = [c[k] for k in _point_slots(c)]
        for p in pts[1:]:
            a, b = find(pts[0]), find(p)
            if a != b:
                parent[a] = b
    groups: dict[int, list] = {}
    for c in conds:
        groups.setdefault(find(c[_point_slots(c)[0]]), []).append(c)
    _NICE[0] = 0
    _REJECTED.clear()
    _SKIPPED.clear()
    x = x0.copy()
    plain = x0.copy()
    cache = {} if cache is None else cache
    for group in groups.values():
        points = sorted({c[k] for c in group for k in _point_slots(c)})
        key = tuple(group)
        if key in cache:
            idx, xs, xp, rejected, rounded = cache[key]
            x[idx], plain[idx] = xs, xp
            _REJECTED.extend(rejected)
            _NICE[0] += rounded
            continue
        if len(points) > MAX_GROUP:
            # an assembly's tangle of lines: too big to fit as one part, it
            # stays as drawn (the fitting is for the drawings of parts)
            _SKIPPED.append(len(points))
            continue
        local = {p: j for j, p in enumerate(points)}
        sub = []
        for c in group:
            c = list(c)
            for k in _point_slots(c):
                c[k] = local[c[k]]
            sub.append(tuple(c))
        idx = np.array([v for p in points for v in (2 * p, 2 * p + 1)])
        before, nice_before = len(_REJECTED), _NICE[0]
        sub, xs = _with_sizes(sub, x0[idx])
        plain[idx] = xs
        if nice is not None:
            scale_, levels_, radii_ = nice
            extra = _nice_conds(sub, xs, scale_, levels_, {local[r] for r in radii_ if r in local})
            for _ in range(4):
                if not extra:
                    break
                xn = _gauss_newton(sub + extra, x0[idx], len(idx), start=xs)
                # a round value is a small touch: one that drags the outline
                # (a joint near a tangent) is not taken
                moved = np.hypot((xn - xs)[0::2], (xn - xs)[1::2])
                far = {j for j in range(len(moved)) if moved[j] > 2 * NICE_TOL}
                if not far:
                    xs = xn
                    _NICE[0] += len(extra)
                    break
                extra = [e for e in extra if not far & _cond_vars(e)]
        x[idx] = xs
        cache[key] = (idx, xs, plain[idx], _REJECTED[before:], _NICE[0] - nice_before)
    return x, plain


_REJECTED: list = []  # ids of written sizes that contradict the others (read by solve_contour)
SIZE_TOL = 1e-4  # sheet mm: a size the others already decide must agree this well


def _with_sizes(conds, x0):
    """The outline's own conditions, then the written sizes (biggest first):
    a size the others leave free is taken; one they already decide is kept
    only if it agrees — two sizes saying different things (15 + 3 where the
    flats make 17,86) cannot both hold, and the outline must not bend to a
    compromise of them."""
    size = len(x0)
    base = [c for c in conds if c[0][0] != "D"]
    sizes = [c for c in conds if c[0][0] == "D"]
    x = _gauss_newton(base, x0, size)
    if not sizes:
        return base, x
    J, _ = _rows(base, x)
    if J.shape[0]:
        _, s, vt = np.linalg.svd(J, full_matrices=False)
        basis = vt[s > 1e-9 * (s[0] if len(s) else 1.0)]
    else:
        basis = np.zeros((0, size))
    free, decided = [], []
    for cond in sizes:
        row = _rows([cond], x)[0][0]
        r = row - basis.T @ (basis @ row) if len(basis) else row.copy()
        norm = np.linalg.norm(r)
        if norm > 1e-6:
            basis = np.vstack([basis, r / norm])
            free.append(cond)
        else:
            decided.append(cond)
    x = _gauss_newton(base + free, x0, size, start=x)
    kept = []
    for cond in decided:
        if abs(_rows([cond], x)[1][0]) <= SIZE_TOL:
            kept.append(cond)
        else:
            _REJECTED.append(cond[-1])
    return base + free + kept, x


def _nice_conds(conds, x, scale, levels, radii=()):
    """Round values for the sizes the conditions leave free: the distance of
    a level from an axis (a diameter), the gap between neighbouring levels.
    A size is free when its row is independent of the conditions' rows."""
    size = len(x)
    J, _ = _rows(conds, x)
    basis = np.zeros((size, size))  # orthonormal rows; the first ``used`` taken
    used = 0
    if J.shape[0]:
        _, s, vt = np.linalg.svd(J, full_matrices=False)
        kept = vt[s > 1e-9 * (s[0] if len(s) else 1.0)]
        used = len(kept)
        basis[:used] = kept
    out = []

    def free(row):
        nonlocal used
        if used >= size:
            return False
        nz = np.flatnonzero(row)  # a row of one or two entries: cheap to project
        r = row - basis[:used].T @ (basis[:used, nz] @ row[nz]) if used else row.copy()
        norm = np.linalg.norm(r)
        if norm < 1e-6:
            return False
        basis[used] = r / norm
        used += 1
        return True

    for j in sorted(radii):  # the radii of fillets nobody sized
        v = _nice(x[2 * j] / scale, scale)
        row = np.zeros(size)
        row[2 * j] = 1.0
        if v is not None and abs(v * scale - x[2 * j]) > 1e-9 and free(row):
            out.append(("fix", j, 0, v * scale))
    for k in (0, 1):
        coords = x[k::2]
        idx = np.argsort(coords)
        lv = []  # (value, point) per distinct level
        for i in idx:
            if i in radii:
                continue
            if not lv or coords[i] - lv[-1][0] > 1e-7:
                lv.append((float(coords[i]), int(i)))
        lo, hi = (lv[0][0], lv[-1][0]) if lv else (0.0, 0.0)
        for kk, axis in levels:
            if kk != k or not lo - 1.0 <= axis <= hi + 1.0:
                continue
            for value, i in lv:
                dist = abs(value - axis)
                v = _nice(2 * dist / scale, scale, 2.0) if dist > 1e-6 else None
                if v is None or abs(v * scale / 2 - dist) < 1e-9:
                    continue
                row = np.zeros(size)
                row[2 * i + k] = 1.0
                if free(row):
                    out.append(("fix", i, k, axis + math.copysign(v * scale / 2, value - axis)))
        for (va, a), (vb, b) in zip(lv, lv[1:]):
            v = _nice((vb - va) / scale, scale)
            if v is None or abs(v * scale - (vb - va)) < 1e-9:
                continue
            row = np.zeros(size)
            row[2 * b + k], row[2 * a + k] = 1.0, -1.0
            if free(row):
                out.append(("dx", a, b, k, v * scale))
    return out


def _rows(conds, x):
    """Jacobian rows and values of the conditions at x."""
    size = len(x)
    rows, res = [], []
    for cond in conds:
        cond = _plain(cond)
        row = np.zeros(size)
        kind = cond[0]
        if kind == "dir":
            _, a, b, th = cond
            sn, cs = math.sin(th), math.cos(th)
            val = (x[2 * b] - x[2 * a]) * sn - (x[2 * b + 1] - x[2 * a + 1]) * cs
            row[2 * b], row[2 * a], row[2 * b + 1], row[2 * a + 1] = sn, -sn, -cs, cs
        elif kind in ("circle", "dist", "circleR"):
            _, i, c, r = cond
            dx, dy = x[2 * i] - x[2 * c], x[2 * i + 1] - x[2 * c + 1]
            d = math.hypot(dx, dy) or 1.0
            if kind == "circleR":
                val = d - x[2 * r]
                row[2 * r] = -1.0
            else:
                val = d - r
            row[2 * i], row[2 * i + 1] = dx / d, dy / d
            row[2 * c], row[2 * c + 1] = -dx / d, -dy / d
        elif kind == "tangent":
            _, i, c, th = cond
            cs, sn = math.cos(th), math.sin(th)
            val = (x[2 * i] - x[2 * c]) * cs + (x[2 * i + 1] - x[2 * c + 1]) * sn
            row[2 * i], row[2 * i + 1], row[2 * c], row[2 * c + 1] = cs, sn, -cs, -sn
        elif kind == "dx":
            _, a, b, k, t = cond
            val = x[2 * b + k] - x[2 * a + k] - t
            row[2 * b + k], row[2 * a + k] = 1.0, -1.0
        elif kind == "fix":
            _, i, k, v = cond
            val = x[2 * i + k] - v
            row[2 * i + k] = 1.0
        elif kind == "mid":
            _, a, b, m, k = cond
            val = x[2 * a + k] + x[2 * b + k] - 2 * x[2 * m + k]
            row[2 * a + k], row[2 * b + k], row[2 * m + k] = 1.0, 1.0, -2.0
        elif kind == "sym":
            _, a, b, k, v = cond
            val = x[2 * a + k] + x[2 * b + k] - 2 * v
            row[2 * a + k], row[2 * b + k] = 1.0, 1.0
        else:
            if kind == "online":
                _, i, a, b = cond
                ax, ay, bx, by = x[2 * a], x[2 * a + 1], x[2 * b], x[2 * b + 1]
            else:
                _, i, (ax, ay), (bx, by) = cond
            px, py = x[2 * i], x[2 * i + 1]
            L = math.hypot(bx - ax, by - ay) or 1.0
            val = ((bx - ax) * (py - ay) - (by - ay) * (px - ax)) / L
            row[2 * i] = -(by - ay) / L
            row[2 * i + 1] = (bx - ax) / L
            if kind == "online":
                row[2 * a] = (by - py) / L
                row[2 * a + 1] = (px - bx) / L
                row[2 * b] = (py - ay) / L
                row[2 * b + 1] = -(px - ax) / L
        rows.append(row)
        res.append(val)
    return (np.array(rows) if rows else np.zeros((0, size))), np.array(res)


def _gauss_newton(conds, x0, size, start=None):
    """Positions meeting the conditions (weight W², all but exactly: the
    residual is about shift / W²) nearest to x0. Normal equations: the
    weighted conditions plus the unit pull keep them positive definite, so a
    plain solve does (an SVD least squares was the bulk of an assembly's time)."""
    W2 = 1e12
    x = (x0 if start is None else start).copy()
    eye = np.eye(size)
    for _ in range(30):
        J, val = _rows(conds, x)
        A = W2 * (J.T @ J) + eye
        rhs = -W2 * (J.T @ val) + (x0 - x)
        try:
            step = np.linalg.solve(A, rhs)
        except np.linalg.LinAlgError:
            step, *_ = np.linalg.lstsq(A, rhs, rcond=None)
        x += step
        if np.abs(step).max() < 1e-10:
            break
    return x


def _write_back(drawing, nodes, arcs, arc_var, x, end, moved, n, directions, dropped):
    for arc in arcs:
        j = arc_var[id(arc)]
        arc.center = (float(x[2 * j]), float(x[2 * j + 1]))
    for i, (p, members) in enumerate(nodes):
        q = (float(x[2 * i]), float(x[2 * i + 1]))
        # where an arc meets the node, its own end point is the exact one
        for e, k in members:
            if isinstance(e, ir.Arc):
                ang = math.degrees(math.atan2(q[1] - e.center[1], q[0] - e.center[0])) % 360.0
                if k == 0:
                    e.start_angle = ang
                else:
                    e.end_angle = ang
                q = end(e, k)
                break
        for e, k in members:
            if isinstance(e, ir.Arc):
                ang = math.degrees(math.atan2(q[1] - e.center[1], q[0] - e.center[0])) % 360.0
                if k == 0:
                    e.start_angle = ang
                else:
                    e.end_angle = ang
            elif k == 0:
                e.p1 = q
            else:
                e.p2 = q
    return {"nodes": n, "directions": directions, "moved": moved, "dropped": dropped}
