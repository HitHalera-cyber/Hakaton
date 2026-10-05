"""Recognise axis lines that were exported as solid thin lines.

A dash-dot line shorter than one dash period is drawn solid in the PDF, so
short centre lines lose their pattern. They are recognised by their role:
  * a thin line through the centre of a circle or arc (centre mark), or
  * a thin line running midway between two parallel contour lines
    (axis of a channel, slot or shaft).
"""

from __future__ import annotations

from ..geometry.fitting import angle_diff, direction_deg, point_line_distance, point_segment_distance
from ..geometry.segmentation import Primitive

ON_CENTER = 0.1  # mm
PARALLEL = 0.5  # deg
MIDWAY = 0.1  # mm, |d1 - d2|


def mark_axis_lines(thin_lines: list[Primitive], main: list[Primitive]) -> int:
    """Tag thin solid lines that act as axes with ``axial``; return how many."""
    curves = [p for p in main if p.kind in ("circle", "arc")]
    lines = [p for p in main if p.kind == "line"]
    count = 0
    for t in thin_lines:
        if t.kind != "line" or t.tags & {"axial", "dashed"}:
            continue
        if _through_center(t, curves) or _midway(t, lines):
            t.tags.add("axial")
            count += 1
    return count


def _through_center(t: Primitive, curves) -> bool:
    return any(point_segment_distance(c.center, t.p1, t.p2) <= ON_CENTER
               and point_line_distance(c.center, t.p1, t.p2) <= ON_CENTER for c in curves)


def _midway(t: Primitive, lines) -> bool:
    ang = direction_deg(t.p1, t.p2)
    mid = ((t.p1[0] + t.p2[0]) / 2, (t.p1[1] + t.p2[1]) / 2)
    sides = []
    for l in lines:
        if angle_diff(direction_deg(l.p1, l.p2), ang) > PARALLEL:
            continue
        d = point_line_distance(mid, l.p1, l.p2)
        if d < 0.2 or d > 50.0:
            continue
        side = (l.p2[0] - l.p1[0]) * (mid[1] - l.p1[1]) - (l.p2[1] - l.p1[1]) * (mid[0] - l.p1[0])
        # the two side lines must overlap the axis along its length
        if _overlap(t, l) <= 0.3 * t.length:
            continue
        sides.append((d, side > 0))
    for i, (d1, s1) in enumerate(sides):
        for d2, s2 in sides[i + 1:]:
            if s1 != s2 and abs(d1 - d2) <= MIDWAY:
                return True
    return False


def _overlap(a: Primitive, b: Primitive) -> float:
    ux, uy = a.p2[0] - a.p1[0], a.p2[1] - a.p1[1]
    n = (ux * ux + uy * uy) ** 0.5 or 1.0
    ux, uy = ux / n, uy / n

    def t(p):
        return (p[0] - a.p1[0]) * ux + (p[1] - a.p1[1]) * uy

    lo = max(0.0, min(t(b.p1), t(b.p2)))
    hi = min(a.length, max(t(b.p1), t(b.p2)))
    return max(0.0, hi - lo)
