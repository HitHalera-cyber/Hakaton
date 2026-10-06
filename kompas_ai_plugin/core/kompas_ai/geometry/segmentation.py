"""Split polylines into straight segments, arcs and circles.

A chain may contain several objects (a slot = line + arc + line). The chain
is consumed greedily: from the current vertex the longest run that fits a
line and the longest run that fits an arc (consistent bending, small residual)
are found, and the one covering more vertices wins. Afterwards vertices at a
line/arc boundary that lie on the arc are handed to the arc (the first chord
of a tangent arc barely turns and is first grabbed by the line), and
neighbouring pieces of the same line or circle are merged.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .chains import Chain
from .fitting import angle_diff, direction_deg, fit_circle, fit_line, turning_angles

LINE_TOLERANCE = 0.08  # mm; KOMPAS PDF coordinates are quantised to ~0.085 mm
CIRCLE_TOLERANCE = 0.08
MIN_ARC_POINTS = 4
MAX_ARC_TURN = 60.0  # deg per chord; larger turns are corners
FULL_CIRCLE = 355.0  # deg; a closed arc covering this much is a circle
MAX_SAGITTA = 0.5  # mm; chord-to-arc bulge allowed for one chord of a tessellated arc


@dataclass
class Primitive:
    kind: str  # line | arc | circle
    points: list[tuple[float, float]]
    width: float
    error: float
    p1: tuple[float, float] | None = None
    p2: tuple[float, float] | None = None
    center: tuple[float, float] | None = None
    radius: float | None = None
    start_angle: float | None = None  # CCW from start to end, degrees
    end_angle: float | None = None
    sweep: float | None = None
    tags: set[str] = field(default_factory=set)

    @property
    def length(self) -> float:
        if self.kind == "line":
            return math.dist(self.p1, self.p2)
        return math.radians(self.sweep or 360.0) * (self.radius or 0.0)


def segment_chain(chain: Chain) -> list[Primitive]:
    pieces = _greedy(chain.points, chain.width)
    pieces = _rebalance(pieces, chain.width)
    pieces = _merge_neighbours(pieces, chain.width, closed=chain.closed)
    if chain.closed and len(pieces) == 1 and pieces[0].kind == "arc" \
            and (pieces[0].sweep or 0) >= FULL_CIRCLE:
        arc = pieces[0]
        return [Primitive("circle", arc.points, chain.width, arc.error,
                          center=arc.center, radius=arc.radius)]
    return pieces


def _greedy(points, width) -> list[Primitive]:
    pieces = []
    i, n = 0, len(points)
    while i < n - 1:
        j = _longest(points, i, lambda pts: _try_line(pts, width), min_end=i + 1)
        k = _longest(points, i, lambda pts: _try_arc(pts, width), min_end=i + MIN_ARC_POINTS - 1)
        if k is not None and k >= j + 2:
            pieces.append(_try_arc(points[i:k + 1], width))
            i = k
        else:
            pieces.append(_try_line(points[i:j + 1], width))
            i = j
    return pieces


def _longest(points, start, make, min_end) -> int | None:
    """Largest end index such that points[start:end+1] is accepted by ``make``."""
    best = None
    for end in range(min_end, len(points)):
        if make(points[start:end + 1]) is None:
            if best is not None or end - min_end > 2:
                break
            continue
        best = end
    return best


def _rebalance(pieces: list[Primitive], width) -> list[Primitive]:
    """Move boundary vertices lying on a neighbouring arc from the line to the arc."""
    for i in range(len(pieces) - 1):
        a, b = pieces[i], pieces[i + 1]
        if a.kind == "line" and b.kind == "arc":
            while len(a.points) > 2 and _on_circle(a.points[-2], b):
                b = _try_arc(a.points[-2:-1] + b.points, width) or b
                a = _try_line(a.points[:-1], width) or a
                if b.points[0] != a.points[-1]:
                    break
        elif a.kind == "arc" and b.kind == "line":
            while len(b.points) > 2 and _on_circle(b.points[1], a):
                a = _try_arc(a.points + b.points[1:2], width) or a
                b = _try_line(b.points[1:], width) or b
                if a.points[-1] != b.points[0]:
                    break
        pieces[i], pieces[i + 1] = a, b
    return pieces


def _on_circle(p, arc: Primitive) -> bool:
    return abs(math.dist(p, arc.center) - arc.radius) <= CIRCLE_TOLERANCE + 0.002 * arc.radius


def _try_line(points, width) -> Primitive | None:
    if len(points) == 2:
        return Primitive("line", list(points), width, 0.0,
                         p1=tuple(points[0]), p2=tuple(points[1]))
    fit = fit_line(points)
    if fit.max_error <= LINE_TOLERANCE:
        return Primitive("line", list(points), width, fit.max_error, p1=fit.p1, p2=fit.p2)
    return None


def _try_arc(points, width) -> Primitive | None:
    if len(points) < MIN_ARC_POINTS:
        return None
    turns = turning_angles(points)
    if max(abs(t) for t in turns) > MAX_ARC_TURN:
        return None
    significant = [t for t in turns if abs(t) > 0.3]
    if significant and not (all(t > 0 for t in significant) or all(t < 0 for t in significant)):
        return None
    fit = fit_circle(points)
    if fit is None or fit.max_error > CIRCLE_TOLERANCE + 0.002 * fit.radius:
        return None
    # A tessellated arc has similar, short chords. One long straight chord
    # (a line followed by an arc) would bulge away from the fitted circle.
    for a, b in zip(points, points[1:]):
        half = math.dist(a, b) / 2
        if half >= fit.radius or fit.radius - math.sqrt(fit.radius ** 2 - half ** 2) > MAX_SAGITTA:
            return None
    return _make_arc(points, width, fit.center, fit.radius, fit.max_error)


def _make_arc(points, width, center, radius, error) -> Primitive:
    angles = [math.atan2(p[1] - center[1], p[0] - center[0]) for p in points]
    sweep = 0.0
    for a1, a2 in zip(angles, angles[1:]):
        d = a2 - a1
        d = (d + math.pi) % (2 * math.pi) - math.pi
        sweep += d
    start, end = math.degrees(angles[0]) % 360, math.degrees(angles[-1]) % 360
    if sweep < 0:  # stored CCW
        start, end = end, start
    return Primitive("arc", list(points), width, error, center=center, radius=radius,
                     start_angle=start, end_angle=end, sweep=abs(math.degrees(sweep)),
                     p1=tuple(points[0]), p2=tuple(points[-1]))


def _merge_neighbours(pieces: list[Primitive], width, closed: bool = False) -> list[Primitive]:
    merged: list[Primitive] = []
    for piece in pieces:
        if merged:
            joined = _join(merged[-1], piece, width)
            if joined is not None:
                merged[-1] = joined
                continue
        merged.append(piece)
    if closed and len(merged) > 1:  # the seam of a closed chain may cut an object
        joined = _join(merged[-1], merged[0], width)
        if joined is not None:
            merged = [joined] + merged[1:-1]
    return merged


def _join(a: Primitive, b: Primitive, width) -> Primitive | None:
    points = a.points + b.points[1:]
    if a.kind == "line" and b.kind == "line":
        if angle_diff(direction_deg(a.p1, a.p2), direction_deg(b.p1, b.p2)) > 1.0:
            return None
        fit = fit_line(points)
        if fit.max_error <= LINE_TOLERANCE:
            return Primitive("line", points, width, fit.max_error, p1=fit.p1, p2=fit.p2)
        return None
    if a.kind == "arc" and b.kind == "arc":
        if math.dist(a.center, b.center) > 3 * CIRCLE_TOLERANCE \
                or abs(a.radius - b.radius) > 3 * CIRCLE_TOLERANCE:
            return None
        fit = fit_circle(points)
        if fit and fit.max_error <= CIRCLE_TOLERANCE + 0.002 * fit.radius:
            return _make_arc(points, width, fit.center, fit.radius, fit.max_error)
    return None


def merge_cocircular(prims: list[Primitive]) -> list[Primitive]:
    """Join arcs of one circle that were cut at junctions (touching, same width).

    A circle touched by other objects is split into several chains at the
    junction points; its pieces are re-joined here. Pieces separated by gaps
    (dash patterns) are left to the line-type stage.
    """
    arcs = [p for p in prims if p.kind == "arc"]
    rest = [p for p in prims if p.kind != "arc"]
    groups: list[list[Primitive]] = []
    for arc in arcs:
        for g in groups:
            ref = g[0]
            tol = 3 * CIRCLE_TOLERANCE + 0.003 * ref.radius
            if abs(ref.width - arc.width) < 1e-3 and math.dist(ref.center, arc.center) <= tol \
                    and abs(ref.radius - arc.radius) <= tol:
                g.append(arc)
                break
        else:
            groups.append([arc])

    # Short chords lying on a circle (left over where a junction split it)
    # fill the gaps between its arc pieces.
    used_chords: set[int] = set()
    for g in groups:
        ref = max(g, key=lambda a: a.sweep)
        tol = CIRCLE_TOLERANCE + 0.002 * ref.radius
        for line in rest:
            if line.kind != "line" or abs(line.width - ref.width) >= 1e-3 or id(line) in used_chords:
                continue
            if line.length > 0.6 * ref.radius or not all(
                    abs(math.dist(p, ref.center) - ref.radius) <= tol for p in (line.p1, line.p2)):
                continue
            a1 = math.degrees(math.atan2(line.p1[1] - ref.center[1], line.p1[0] - ref.center[0]))
            a2 = math.degrees(math.atan2(line.p2[1] - ref.center[1], line.p2[0] - ref.center[0]))
            start, sweep = (a1 % 360.0, (a2 - a1) % 360.0)
            if sweep > 180.0:
                start, sweep = a2 % 360.0, 360.0 - sweep
            g.append(Primitive("arc", [line.p1, line.p2], ref.width, line.error, center=ref.center,
                               radius=ref.radius, start_angle=start, end_angle=(start + sweep) % 360,
                               sweep=sweep, p1=line.p1, p2=line.p2))
            used_chords.add(id(line))

    out = [p for p in rest if id(p) not in used_chords]
    for g in groups:
        out.extend(_join_touching(g) if len(g) > 1 else g)
    return out


def _join_touching(group: list[Primitive]) -> list[Primitive]:
    """Union of touching angular spans; a span covering the circle becomes a circle."""
    spans = sorted(((p.start_angle % 360.0, p.sweep, p) for p in group), key=lambda s: s[0])
    runs: list[list] = []
    for start, sweep, p in spans:
        if runs:
            r_start, r_sweep, members = runs[-1]
            gap = (start - (r_start + r_sweep)) % 360.0
            if gap <= 1.0 or gap >= 359.0 - sweep:  # touching or overlapping
                runs[-1] = [r_start, max(r_sweep, (start - r_start) % 360.0 + sweep), members + [p]]
                continue
        runs.append([start, sweep, [p]])
    # the last run may continue into the first one across 0°
    if len(runs) > 1:
        first, last = runs[0], runs[-1]
        gap = (first[0] - (last[0] + last[1])) % 360.0
        if gap <= 1.0:
            runs[0] = [last[0], last[1] + gap + first[1], last[2] + first[2]]
            runs.pop()

    out = []
    for start, sweep, members in runs:
        if len(members) == 1:
            out.append(members[0])
            continue
        points = [q for m in members for q in m.points]
        fit = fit_circle(points)
        center, radius = (fit.center, fit.radius) if fit else (members[0].center, members[0].radius)
        error = fit.max_error if fit else max(m.error for m in members)
        width = members[0].width
        if sweep >= FULL_CIRCLE:
            prim = Primitive("circle", points, width, error, center=center, radius=radius)
        else:
            end = (start + sweep) % 360.0
            prim = Primitive("arc", points, width, error, center=center, radius=radius,
                             start_angle=start, end_angle=end, sweep=sweep)
            a, b = (math.radians(start), math.radians(end))
            prim.p1 = (center[0] + radius * math.cos(a), center[1] + radius * math.sin(a))
            prim.p2 = (center[0] + radius * math.cos(b), center[1] + radius * math.sin(b))
        prim.tags = set().union(*(m.tags for m in members))
        out.append(prim)
    return out
