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

    def snap_dim(p):
        best = min(nodes, key=lambda q: math.dist(p, q), default=None)
        if best is not None and math.dist(p, best) <= DIM_NODE:
            return best
        c = min(centres, key=lambda q: math.dist(p, q), default=None)
        if c is not None and math.dist(p, c) <= tol:
            return c  # from the centre of a hole or an arc
        for e in curves:  # a point of an arc (the bottom of a notch)
            d = math.dist(p, e.center)
            if d > 0 and abs(d - e.radius) <= tol:
                return (e.center[0] + (p[0] - e.center[0]) * e.radius / d,
                        e.center[1] + (p[1] - e.center[1]) * e.radius / d)
        return snap(p)

    moved = 0
    for d in drawing.of_type(ir.Dimension):
        if d.dim_type != "linear":
            continue
        for name in ("p1", "p2"):
            p = getattr(d, name)
            if p is not None:
                q = snap_dim(tuple(p))
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


def solve_contour(drawing: ir.Drawing) -> dict:
    """The contour as one system of conditions, solved together (a sketch
    solver in small). Unknowns: the nodes where ends meet and the centres of
    the arcs (radii stay as the dimensions set them). Conditions:
      * the ends of a node coincide exactly (they are one unknown);
      * a line near horizontal, vertical or a standard angle (chamfer 45°,
        cone 30°) runs exactly so;
      * a node of an arc lies on its circle; a fillet that meets a line
        nearly tangentially meets it exactly tangentially;
      * an end resting on another line (or on an axis) lies on it.
    Of all positions keeping these, the one nearest the drawing is taken
    (least squares, Gauss–Newton). One rule at a time undid the others:
    joining two ends tilted the horizontal that had just been made exact."""
    pieces = [e for e in drawing.entities if isinstance(e, (ir.Line, ir.Arc))
              and e.style == ir.STYLE_MAIN]
    axes = [e for e in drawing.of_type(ir.Line) if e.style == ir.STYLE_AXIAL]

    def end(e, k):
        if isinstance(e, ir.Line):
            return tuple(e.p1 if k == 0 else e.p2)
        a = math.radians(e.start_angle if k == 0 else e.end_angle)
        return (e.center[0] + e.radius * math.cos(a), e.center[1] + e.radius * math.sin(a))

    nodes: list[list] = []
    member_node = {}
    for e in pieces:
        for k in (0, 1):
            p = end(e, k)
            for i, node in enumerate(nodes):
                if math.dist(node[0], p) <= JOIN:
                    node[1].append((e, k))
                    member_node[(id(e), k)] = i
                    break
            else:
                member_node[(id(e), k)] = len(nodes)
                nodes.append([p, [(e, k)]])
    n = len(nodes)
    if n == 0:
        return {"nodes": 0}
    arcs = [e for e in pieces if isinstance(e, ir.Arc)]
    arc_var = {id(a): n + j for j, a in enumerate(arcs)}  # unknown index of the centre
    size = 2 * (n + len(arcs))
    x0 = np.array([c for node in nodes for c in node[0]]
                  + [c for a in arcs for c in a.center], dtype=float)

    lines = [e for e in pieces if isinstance(e, ir.Line)]
    direction = {}
    conds = []
    for line in lines:
        a, b = member_node[(id(line), 0)], member_node[(id(line), 1)]
        if a == b:
            continue
        (x1, y1), (x2, y2) = line.p1, line.p2
        ang = math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180.0
        best = min(STANDARD_ANGLES + (180.0,), key=lambda v: abs(ang - v))
        if abs(ang - best) <= ANGLE_SNAP:
            th = math.radians(best % 180.0)
            conds.append(("dir", a, b, th))
            direction[id(line)] = th
    for arc in arcs:
        for k in (0, 1):
            i = member_node[(id(arc), k)]
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
    for i, (p, members) in enumerate(nodes):
        if len(members) != 1:
            continue
        own = members[0][0]
        for line in lines + axes:
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

    x, dropped = x0.copy(), 0
    for _ in range(4):
        x = _gauss_newton(conds, x0, size)
        shift = np.hypot((x - x0)[0::2], (x - x0)[1::2])
        far = {i for i in range(len(shift)) if shift[i] > MAX_NODE_SHIFT}
        if not far:
            break
        # conditions that drag a point this far contradict the drawing (a
        # slope that is not a standard one, a wrong contact): left out there
        keep = [c for c in conds if not far & _cond_vars(c)]
        dropped += len(conds) - len(keep)
        conds = keep
    else:
        x = x0.copy()  # no consistent set found: the drawing stays as it is

    moved = float(np.abs(x - x0).max())
    return _write_back(drawing, nodes, arcs, arc_var, x, end, moved, n, len(direction), dropped)


MAX_NODE_SHIFT = 0.15  # sheet mm


def _cond_vars(cond) -> set:
    kind = cond[0]
    if kind == "dir":
        return {cond[1], cond[2]}
    if kind in ("circle", "tangent"):
        return {cond[1], cond[2]}
    if kind == "online":
        return {cond[1], cond[2], cond[3]}
    return {cond[1]}


def _gauss_newton(conds, x0, size):
    W = 1e6
    x = x0.copy()
    for _ in range(30):
        rows, res = [], []
        for cond in conds:
            row = np.zeros(size)
            kind = cond[0]
            if kind == "dir":
                _, a, b, th = cond
                sn, cs = math.sin(th), math.cos(th)
                val = (x[2 * b] - x[2 * a]) * sn - (x[2 * b + 1] - x[2 * a + 1]) * cs
                row[2 * b], row[2 * a], row[2 * b + 1], row[2 * a + 1] = sn, -sn, -cs, cs
            elif kind == "circle":
                _, i, c, r = cond
                dx, dy = x[2 * i] - x[2 * c], x[2 * i + 1] - x[2 * c + 1]
                d = math.hypot(dx, dy) or 1.0
                val = d - r
                row[2 * i], row[2 * i + 1] = dx / d, dy / d
                row[2 * c], row[2 * c + 1] = -dx / d, -dy / d
            elif kind == "tangent":
                _, i, c, th = cond
                cs, sn = math.cos(th), math.sin(th)
                val = (x[2 * i] - x[2 * c]) * cs + (x[2 * i + 1] - x[2 * c + 1]) * sn
                row[2 * i], row[2 * i + 1], row[2 * c], row[2 * c + 1] = cs, sn, -cs, -sn
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
            rows.append(W * row)
            res.append(-W * val)
        A = np.vstack(rows + [np.eye(size)]) if rows else np.eye(size)
        rhs = np.concatenate([np.array(res), x0 - x]) if rows else x0 - x
        step, *_ = np.linalg.lstsq(A, rhs, rcond=None)
        x += step
        if np.abs(step).max() < 1e-12:
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
