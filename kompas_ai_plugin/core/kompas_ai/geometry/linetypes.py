"""Reassemble dash-patterned lines (axial, dashed) from their dashes.

PDF exporters draw a dash-dot line as separate strokes. Thin collinear
segments separated by small gaps are merged back into one line, and thin
co-circular arcs into one circle/arc. The dash pattern decides the style:
long dashes alternating with short dots → axial (осевая), regular dashes →
dashed (штриховая).
"""

from __future__ import annotations

import math

from .fitting import angle_diff, direction_deg, fit_circle, point_line_distance
from .segmentation import Primitive

MAX_GAP = 3.0  # mm between consecutive dashes
OFFSET_TOLERANCE = 0.12  # mm
ANGLE_TOLERANCE = 0.8  # deg
DOT_MAX = 2.5  # mm; a "dot" of a dash-dot line
CIRCLE_COVERAGE = 300.0  # deg of dashes+gaps to call a dashed arc set a full circle


def merge_dashed(prims: list[Primitive], thin_width: float) -> list[Primitive]:
    """Return primitives with dash groups replaced by single styled primitives."""
    thin = [p for p in prims if abs(p.width - thin_width) < 1e-3]
    rest = [p for p in prims if abs(p.width - thin_width) >= 1e-3]
    lines = [p for p in thin if p.kind == "line"]
    arcs = [p for p in thin if p.kind == "arc"]
    others = [p for p in thin if p.kind not in ("line", "arc")]
    merged_arcs = _merge_arcs(arcs)
    lines = _absorb_dots(lines, merged_arcs)
    return rest + others + _merge_lines(lines) + merged_arcs


def _absorb_dots(lines: list[Primitive], curves: list[Primitive]) -> list[Primitive]:
    """Short dots of a dash-dot circle have too few vertices to be fitted as
    arcs; drop the lines that lie on an already assembled dash-dot circle."""
    dashed = [c for c in curves if "axial" in c.tags]
    keep = []
    for line in lines:
        on = any(line.length <= DOT_MAX + 0.5
                 and all(abs(math.dist(p, c.center) - c.radius) <= 0.15 for p in (line.p1, line.p2))
                 for c in dashed)
        if not on:
            keep.append(line)
    return keep


def _merge_lines(lines: list[Primitive]) -> list[Primitive]:
    groups: list[list[Primitive]] = []
    for line in sorted(lines, key=lambda p: -p.length):
        for group in groups:
            ref = group[0]
            if angle_diff(direction_deg(ref.p1, ref.p2), direction_deg(line.p1, line.p2)) \
                    <= ANGLE_TOLERANCE \
                    and point_line_distance(line.p1, ref.p1, ref.p2) <= OFFSET_TOLERANCE \
                    and point_line_distance(line.p2, ref.p1, ref.p2) <= OFFSET_TOLERANCE:
                group.append(line)
                break
        else:
            groups.append([line])

    out = []
    for group in groups:
        out.extend(_runs_on_line(group))
    return out


def _runs_on_line(group: list[Primitive]) -> list[Primitive]:
    """Split one collinear group into runs whose gaps are dash-sized."""
    ref = max(group, key=lambda p: p.length)
    ux, uy = ref.p2[0] - ref.p1[0], ref.p2[1] - ref.p1[1]
    norm = math.hypot(ux, uy)
    ux, uy = ux / norm, uy / norm

    def t(p):
        return (p[0] - ref.p1[0]) * ux + (p[1] - ref.p1[1]) * uy

    intervals = sorted(((min(t(p.p1), t(p.p2)), max(t(p.p1), t(p.p2)), p) for p in group),
                       key=lambda iv: iv[:2])
    # A solid line overlapping dashes on the same axis (an extension line drawn
    # along an axis) is a separate object: keep it out of the dash groups.
    solo = [iv for iv in intervals
            if any(o is not iv and min(iv[1], o[1]) - max(iv[0], o[0]) > 0.5 for o in intervals)
            and iv[1] - iv[0] >= max(o[1] - o[0] for o in intervals
                                     if min(iv[1], o[1]) - max(iv[0], o[0]) > 0.5)]
    intervals = [iv for iv in intervals if all(iv is not s for s in solo)]
    if not intervals:
        return [iv[2] for iv in solo]
    runs: list[list] = [[intervals[0]]]
    for iv in intervals[1:]:
        if iv[0] - max(x[1] for x in runs[-1]) <= MAX_GAP:
            runs[-1].append(iv)
        else:
            runs.append([iv])

    out = [iv[2] for iv in solo]
    for run in runs:
        if len(run) == 1:
            out.append(run[0][2])
            continue
        lo, hi = min(x[0] for x in run), max(x[1] for x in run)
        gaps = _gaps([(x[0], x[1]) for x in run])
        if not gaps:  # touching pieces of one solid line (e.g. split by a junction)
            style_tag = None
        else:
            dashes = [x[1] - x[0] for x in run]
            style_tag = "axial" if min(dashes) <= DOT_MAX and max(dashes) > 2 * DOT_MAX \
                else "dashed"
        p1 = (ref.p1[0] + ux * lo, ref.p1[1] + uy * lo)
        p2 = (ref.p1[0] + ux * hi, ref.p1[1] + uy * hi)
        merged = Primitive("line", [p1, p2], run[0][2].width,
                           max(x[2].error for x in run), p1=p1, p2=p2)
        merged.tags = set().union(*(x[2].tags for x in run))
        if style_tag:
            merged.tags.add(style_tag)
        merged.tags.add(f"pieces={len(run)}")
        out.append(merged)
    return out


def _gaps(intervals) -> list[float]:
    gaps = []
    reach = intervals[0][1]
    for lo, hi in intervals[1:]:
        if lo > reach + 0.05:
            gaps.append(lo - reach)
        reach = max(reach, hi)
    return gaps


def _merge_arcs(arcs: list[Primitive]) -> list[Primitive]:
    """Group dashes of one circle by their points, not by their own fits:
    a short dash has few vertices and its own centre/radius are unreliable."""
    groups: list[list[Primitive]] = []
    fits: list[tuple] = []
    for arc in sorted(arcs, key=lambda a: -a.length):
        for i, group in enumerate(groups):
            center, radius = fits[i]
            tol = 0.25 + 0.003 * radius
            if all(abs(math.dist(p, center) - radius) <= tol for p in arc.points):
                group.append(arc)
                fit = fit_circle([p for g in group for p in g.points])
                if fit is not None:
                    fits[i] = (fit.center, fit.radius)
                break
        else:
            groups.append([arc])
            fits.append((arc.center, arc.radius))

    out = []
    for group, ((cx, cy), r) in zip(groups, fits):
        for run in _arc_runs(group, r):
            if len(run) == 1:
                out.append(run[0])
                continue
            covered, start, end = _arc_union(run)
            points = [p for g in run for p in g.points]
            error = max(g.error for g in run)
            if covered >= CIRCLE_COVERAGE:
                merged = Primitive("circle", points, run[0].width, error, center=(cx, cy), radius=r)
            else:
                merged = Primitive("arc", points, run[0].width, error, center=(cx, cy), radius=r,
                                   start_angle=start, end_angle=end, sweep=(end - start) % 360)
            merged.tags = set().union(*(g.tags for g in run)) | {f"pieces={len(run)}"}
            # Pieces with gaps between them are dashes of a dash-dot circle;
            # touching pieces are one solid arc (e.g. chained angular dimensions).
            if covered - sum(g.sweep for g in run) > 0.5:
                merged.tags.add("axial")
            out.append(merged)
    return out


def _arc_runs(group: list[Primitive], radius: float) -> list[list[Primitive]]:
    """Split co-circular pieces into runs whose gaps are dash-sized."""
    max_gap_deg = math.degrees(MAX_GAP / max(radius, 1e-6))
    pieces = sorted(group, key=lambda g: g.start_angle % 360.0)
    runs: list[list[Primitive]] = [[pieces[0]]]
    reach = pieces[0].start_angle % 360.0 + pieces[0].sweep
    for g in pieces[1:]:
        start = g.start_angle % 360.0
        if start - reach <= max_gap_deg:
            runs[-1].append(g)
        else:
            runs.append([g])
        reach = max(reach, start + g.sweep)
    if len(runs) > 1:  # close the circle across 0°
        first = runs[0][0].start_angle % 360.0 + 360.0
        if first - reach <= max_gap_deg:
            runs[0] = runs.pop() + runs[0]
    return runs


def _arc_union(group: list[Primitive]) -> tuple[float, float, float]:
    """Angular span covered by the dashes including the gaps between them.

    Returns (span, start, end); the largest uncovered gap is taken as the
    opening of the arc.
    """
    spans = sorted((g.start_angle % 360, g.sweep) for g in group)
    ends = [(s, (s + w) % 360) for s, w in spans]
    largest_gap, gap_end = 0.0, spans[0][0]
    for i, (s, e) in enumerate(ends):
        nxt = ends[(i + 1) % len(ends)][0]
        gap = (nxt - e) % 360
        if gap > largest_gap:
            largest_gap, gap_end = gap, nxt
    start = gap_end
    span = 360.0 - largest_gap
    return span, start, (start + span) % 360
