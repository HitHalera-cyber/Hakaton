"""Main and thin lines of a drawing plotted with one line width.

AutoCAD and its clones often print without lineweights: every line comes
out as the same hairline. The recognizer tells a contour from dimension,
extension, centre and hatch lines by width, so here the thin ones are found
by what they do instead:

  * a line ending in an arrowhead is a dimension or leader line;
  * a line through an arrow tip, across the arrow, running a little past it,
    is an extension line;
  * pieces of one line with regular short gaps are a dashed (centre, hidden)
    line;
  * a family of parallel lines at a regular spacing is hatching;
  * a line through a circle's centre and out of it on both sides is a
    centre mark or an axis.

Everything else is the contour. Widths are then set as KOMPAS would write
them (0.25 / 0.5 mm) so the later stages work unchanged.
"""

from __future__ import annotations

import math

from ..geometry.fitting import angle_diff, direction_deg, point_segment_distance
from ..geometry.segmentation import Primitive
from .hatch import detect_hatches

THIN, MAIN = 0.25, 0.5
TIP = 0.35  # mm: an arrow tip this close to a line lies on it
OVERSHOOT = (0.3, 8.0)  # mm: how far an extension line runs past the dimension line
DASH_GAP = (0.4, 4.0)  # mm: gaps between the dashes of a centre or hidden line
DASH_MAX = 40.0  # mm: the longest dash
DOT = 1.5  # mm: the dot of a dash-dot line


def infer_thin(prims: list[Primitive], arrows, texts=()) -> int:
    """Set widths by role; returns the number of lines found thin. ``texts``:
    the page's texts (RawText), for the shelves under them."""
    thin: set[int] = set()
    lines = [p for p in prims if p.kind == "line"]
    for p in prims:
        if _ends_in_arrow(p, arrows):
            thin.add(id(p))
    for p in lines:
        if id(p) not in thin and _extension(p, arrows, [q for q in prims if id(q) not in thin]):
            thin.add(id(p))
    dashed = _dashes(lines) | _dashed_arcs([p for p in prims if p.kind == "arc"])
    thin |= dashed | _split_dashes(prims, dashed)
    thin.update(_centre_marks(lines, [p for p in prims if p.kind in ("circle", "arc")]))
    # dimension lines among them keep the lattice whole; a stroke from circle
    # to circle may have been taken for a piece of it (one chord)
    chords = [p for p in prims if p.kind == "arc" and len(p.points) == 2]
    groups, _ = detect_hatches(lines + chords)
    hatch = {id(l) for g in groups for l in g.lines} - thin
    contour = [p for p in lines if id(p) not in thin and id(p) not in hatch]

    def corner(e) -> bool:
        """Contour lines turn here (not: one contour line split where a hatch
        stroke ends on it)."""
        at = [p for p in contour if any(math.dist(e, c) < 0.05 for c in _ends(p))]
        return bool(at) and not any(
            angle_diff(direction_deg(p.p1, p.p2), direction_deg(q.p1, q.p2)) < 1.0
            for i, p in enumerate(at) for q in at[i + 1:])

    for g in groups:
        for l in g.lines:  # a chamfer beside the hatching joins two contour lines
            if all(corner(e) for e in _ends(l)):
                hatch.discard(id(l))
    thin.update(hatch)
    thin.update(_shelves(lines, texts))
    thin.update(_symmetry_axes(lines, thin))
    for p in prims:
        p.width = THIN if id(p) in thin else MAIN
    return len(thin)


def _ends(p: Primitive):
    return (p.p1, p.p2) if p.p1 is not None else ()


def _ends_in_arrow(p: Primitive, arrows) -> bool:
    for a in arrows:
        for end in _ends(p):
            if math.dist(a.tip, end) <= max(TIP, a.length + 0.5):
                if p.kind != "line":  # a dimension arc meets its arrow along it
                    r = (end[0] - p.center[0], end[1] - p.center[1])
                    rn = math.hypot(*r) or 1.0
                    radial = abs(r[0] * a.direction[0] + r[1] * a.direction[1]) / rn
                    on = abs(math.dist(a.tip, p.center) - p.radius) <= TIP
                    if on and radial < 0.2:
                        return True
                    continue
                # along the line: the arrow lies on it
                if point_segment_distance(a.tip, *_infinite(p)) <= TIP and \
                        angle_diff(direction_deg(p.p1, p.p2),
                                   math.degrees(math.atan2(a.direction[1], a.direction[0]))) < 6.0:
                    return True
    return False


def _extension(p: Primitive, arrows, others) -> bool:
    """Across an arrow, through its tip (or ending right at it) and a little
    past it, the end there free: a contour line goes on into another one."""
    ang = direction_deg(p.p1, p.p2)
    for a in arrows:
        across = angle_diff(ang, math.degrees(math.atan2(a.direction[1], a.direction[0])))
        if across < 84.0 or point_segment_distance(a.tip, p.p1, p.p2) > TIP:
            continue
        end = min((p.p1, p.p2), key=lambda e: math.dist(a.tip, e))
        past = math.dist(a.tip, end)
        free = not any(q is not p and any(math.dist(end, e) < OVERSHOOT[0] for e in _ends(q))
                       for q in others)
        if free and past <= min(OVERSHOOT[1], 0.4 * p.length):
            return True
    return False


def _dashes(lines: list[Primitive]) -> set[int]:
    """Short collinear pieces with short gaps between them: three or more in
    a row, or a dash and a dot (two lines meeting with a gap are not dashed —
    an extension line starting off a contour)."""
    link: dict[int, set[int]] = {}
    by_id = {id(l): l for l in lines}
    short = [l for l in lines if l.length <= DASH_MAX]
    by_angle: dict[int, list[Primitive]] = {}
    for l in short:
        by_angle.setdefault(round(direction_deg(l.p1, l.p2)) % 180, []).append(l)
    for key, group in by_angle.items():
        pool = group + by_angle.get((key + 1) % 180, []) + by_angle.get((key - 1) % 180, [])
        for l in group:
            for m in pool:
                if m is l or angle_diff(direction_deg(l.p1, l.p2), direction_deg(m.p1, m.p2)) > 1.0:
                    continue
                # on one line…
                if max(point_segment_distance(e, *_infinite(l)) for e in (m.p1, m.p2)) > 0.1:
                    continue
                # …end to end with a dash gap
                gap = min(math.dist(e, f) for e in (l.p1, l.p2) for f in (m.p1, m.p2))
                if DASH_GAP[0] <= gap <= DASH_GAP[1] and not _overlaps(l, m):
                    link.setdefault(id(l), set()).add(id(m))
                    link.setdefault(id(m), set()).add(id(l))
    out: set[int] = set()
    seen: set[int] = set()
    for start in link:
        if start in seen:
            continue
        run, todo = [], [start]
        seen.add(start)
        while todo:
            k = todo.pop()
            run.append(k)
            for j in link[k] - seen:
                seen.add(j)
                todo.append(j)
        if len(run) >= 3 or min(by_id[k].length for k in run) <= DOT:
            out.update(run)
    return out


def _centre_marks(lines: list[Primitive], curves: list[Primitive]) -> set[int]:
    """A line through a circle's centre running out of it on both sides: a
    centre mark or an axis."""
    out: set[int] = set()
    for l in lines:
        if any(point_segment_distance(c.center, l.p1, l.p2) < 0.2
               and min(math.dist(c.center, l.p1), math.dist(c.center, l.p2)) > c.radius + 0.5
               for c in curves):
            out.add(id(l))
    return out


def _split_dashes(prims: list[Primitive], dashed: set[int]) -> set[int]:
    """A dash cut where another line crosses it: the pieces touch end to end
    on the same line or circle."""
    out: set[int] = set()
    pieces = [p for p in prims if p.p1 is not None and p.length <= DASH_MAX]
    todo = [p for p in pieces if id(p) in dashed]
    while todo:
        d = todo.pop()
        for q in pieces:
            if id(q) in dashed or id(q) in out or q.kind != d.kind:
                continue
            if min(math.dist(e, f) for e in _ends(d) for f in _ends(q)) > 0.05:
                continue
            if d.kind == "arc":
                same = math.dist(d.center, q.center) < 0.1 and abs(d.radius - q.radius) < 0.1
            else:
                same = angle_diff(direction_deg(d.p1, d.p2), direction_deg(q.p1, q.p2)) < 1.0 and \
                    max(point_segment_distance(e, *_infinite(d)) for e in _ends(q)) < 0.1
            if same:
                out.add(id(q))
                todo.append(q)
    return out


SYMMETRIC = 0.5  # of the contour lines mirrored across a line: it is the axis


def _symmetry_axes(lines: list[Primitive], thin: set[int]) -> set[int]:
    """A long line the contour is mirrored across: the axis of a body of
    revolution, drawn solid and as thick as the rest."""
    contour = [l for l in lines if id(l) not in thin and l.length > 0.5]
    if len(contour) < 6:
        return set()
    xs = [c for l in contour for c in (l.p1[0], l.p2[0])]
    ys = [c for l in contour for c in (l.p1[1], l.p2[1])]
    extent = max(max(xs) - min(xs), max(ys) - min(ys))
    keys = {_key(l) for l in contour}
    out = set()
    for axis in contour:
        if axis.length < 0.5 * extent:
            continue
        mirrored = sum(1 for l in contour if l is not axis and _key(_mirror(l, axis)) in keys)
        if mirrored >= SYMMETRIC * (len(contour) - 1):
            out.add(id(axis))
    return out


def _key(l, step: float = 0.25):
    a, b = sorted(((round(l.p1[0] / step), round(l.p1[1] / step)),
                   (round(l.p2[0] / step), round(l.p2[1] / step))))
    return a, b


def _mirror(l: Primitive, axis: Primitive):
    ux, uy = axis.p2[0] - axis.p1[0], axis.p2[1] - axis.p1[1]
    n = math.hypot(ux, uy)
    ux, uy = ux / n, uy / n

    def m(p):
        vx, vy = p[0] - axis.p1[0], p[1] - axis.p1[1]
        t = vx * ux + vy * uy
        fx, fy = axis.p1[0] + ux * t, axis.p1[1] + uy * t
        return (2 * fx - p[0], 2 * fy - p[1])

    return Primitive("line", [], 0.0, 0.0, p1=m(l.p1), p2=m(l.p2))


def _shelves(lines: list[Primitive], texts) -> set[int]:
    """A line right under a text along it: the shelf of a leader or the
    underline of a note."""
    out = set()
    for t in texts:
        a = math.radians(t.angle)
        u, n = (math.cos(a), math.sin(a)), (-math.sin(a), math.cos(a))
        x0, y0 = t.origin
        width = (t.last_origin and math.dist(t.origin, t.last_origin) or 0.0) + t.height
        for l in lines:
            if angle_diff(direction_deg(l.p1, l.p2), t.angle % 180.0) > 2.0:
                continue
            below = [((p[0] - x0) * n[0] + (p[1] - y0) * n[1]) for p in (l.p1, l.p2)]
            along = sorted(((p[0] - x0) * u[0] + (p[1] - y0) * u[1]) for p in (l.p1, l.p2))
            if all(-0.6 * t.height - 0.3 <= b <= 0.1 for b in below) and \
                    along[0] <= 0.5 * width and along[1] >= 0.5 * width and \
                    along[1] - along[0] <= width + 4 * t.height:
                out.add(id(l))
    return out


def _dashed_arcs(arcs: list[Primitive]) -> set[int]:
    """Pieces of one circle with dash gaps between them (a centre circle)."""
    out: set[int] = set()
    for i, a in enumerate(arcs):
        for b in arcs[i + 1:]:
            if math.dist(a.center, b.center) > 0.1 or abs(a.radius - b.radius) > 0.1:
                continue
            gap = min(math.dist(e, f) for e in (a.p1, a.p2) for f in (b.p1, b.p2))
            if DASH_GAP[0] <= gap <= DASH_GAP[1]:
                out.update((id(a), id(b)))
    return out


def _infinite(l: Primitive, reach: float = 1000.0):
    ux, uy = l.p2[0] - l.p1[0], l.p2[1] - l.p1[1]
    n = math.hypot(ux, uy) or 1.0
    ux, uy = ux / n * reach, uy / n * reach
    return (l.p1[0] - ux, l.p1[1] - uy), (l.p2[0] + ux, l.p2[1] + uy)


def _overlaps(l: Primitive, m: Primitive) -> bool:
    ux, uy = l.p2[0] - l.p1[0], l.p2[1] - l.p1[1]
    n = math.hypot(ux, uy) or 1.0
    ux, uy = ux / n, uy / n

    def t(p):
        return (p[0] - l.p1[0]) * ux + (p[1] - l.p1[1]) * uy

    a0, a1 = 0.0, n
    b0, b1 = sorted((t(m.p1), t(m.p2)))
    return min(a1, b1) - max(a0, b0) > 0.05
