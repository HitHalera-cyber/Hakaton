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

MAX_GAP = 7.0  # mm between consecutive dashes (ISO 128 / AutoCAD patterns up to ~6 mm)
MIN_DASHES = 3  # a dash pattern shows at least dash–dot–dash
OFFSET_TOLERANCE = 0.12  # mm
ANGLE_TOLERANCE = 0.8  # deg
DOT_MAX = 2.5  # mm; a "dot" of a dash-dot line
CIRCLE_COVERAGE = 300.0  # deg of dashes+gaps to call a dashed arc set a full circle


def merge_dashed(prims: list[Primitive], thin_width: float,
                 arrow_tips: list[tuple[tuple[float, float], tuple[float, float]]] = ()
                 ) -> list[Primitive]:
    """Return primitives with dash groups replaced by single styled primitives.

    ``arrow_tips``: (tip, direction) of the arrows. A gap with an arrow
    pointing along the line separates two dimension lines of a chain; it is
    not a gap of a dash pattern."""
    thin = [p for p in prims if abs(p.width - thin_width) < 1e-3]
    rest = [p for p in prims if abs(p.width - thin_width) >= 1e-3]
    lines = [p for p in thin if p.kind == "line"]
    arcs = [p for p in thin if p.kind == "arc"]
    others = [p for p in thin if p.kind not in ("line", "arc")]
    merged_arcs = _merge_arcs(arcs)
    chords = _chords_on(lines, merged_arcs)
    if chords:  # dashes split at a junction into chords: put them back on their circle
        lines = [l for l in lines if all(l is not c for c, _ in chords)]
        merged_arcs = _merge_arcs(arcs + [_as_arc(l, c) for l, c in chords])
    lines = _absorb_dots(lines, merged_arcs)
    return rest + others + _merge_lines(lines, arrow_tips) + merged_arcs


def _on_circle(line: Primitive, c: Primitive) -> bool:
    """A short chord of ``c``: both ends on it, the middle at the chord's sagitta."""
    if c.radius < 3.0 or line.length > max(DOT_MAX + 0.5, 0.5 * c.radius):
        return False
    if any(abs(math.dist(p, c.center) - c.radius) > 0.15 for p in (line.p1, line.p2)):
        return False
    mid = ((line.p1[0] + line.p2[0]) / 2, (line.p1[1] + line.p2[1]) / 2)
    return abs(math.dist(mid, c.center) - c.radius) <= line.length ** 2 / (8 * c.radius) + 0.15


def _chords_on(lines: list[Primitive], curves: list[Primitive]) -> list[tuple]:
    dashed = [c for c in curves if "axial" in c.tags]
    out = []
    for line in lines:
        c = next((c for c in dashed if _on_circle(line, c)), None)
        if c is not None:
            out.append((line, c))
    return out


def _as_arc(line: Primitive, c: Primitive) -> Primitive:
    a1 = math.degrees(math.atan2(line.p1[1] - c.center[1], line.p1[0] - c.center[0]))
    a2 = math.degrees(math.atan2(line.p2[1] - c.center[1], line.p2[0] - c.center[0]))
    sweep = (a2 - a1) % 360.0
    start = a1 if sweep <= 180.0 else a2
    sweep = min(sweep, 360.0 - sweep)
    arc = Primitive("arc", list(line.points), line.width, line.error, center=c.center,
                    radius=c.radius, start_angle=start % 360.0, end_angle=(start + sweep) % 360.0,
                    sweep=sweep)
    arc.tags = set(line.tags)
    return arc


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


def _merge_lines(lines: list[Primitive], arrow_tips=()) -> list[Primitive]:
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
        out.extend(_runs_on_line(group, arrow_tips))
    return out


def _runs_on_line(group: list[Primitive], arrow_tips=()) -> list[Primitive]:
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
    # Arrow tips on this line, as positions along it.
    stops = [t(p) for p, d in arrow_tips
             if abs((p[0] - ref.p1[0]) * uy - (p[1] - ref.p1[1]) * ux) <= 0.3
             and abs(d[0] * uy - d[1] * ux) < 0.1]
    runs: list[list] = [[intervals[0]]]
    for iv in intervals[1:]:
        reach = max(x[1] for x in runs[-1])
        blocked = iv[0] - reach > 0.05 and any(reach - 0.3 <= s <= iv[0] + 0.3 for s in stops)
        if iv[0] - reach <= MAX_GAP and not blocked:
            runs[-1].append(iv)
        else:
            runs.append([iv])

    runs = [part for run in runs for part in _split_irregular(run)]
    runs = [part for run in runs for part in _peel_long_ends(run)]
    out = [iv[2] for iv in solo]
    for run in runs:
        dash_dot = len(run) == 2 and min(x[1] - x[0] for x in run) <= 1.0 \
            and max(x[1] - x[0] for x in run) > 2 * DOT_MAX  # a short axis: dash + dot
        if len(run) > 1 and _gaps([(x[0], x[1]) for x in run]) and not dash_dot and \
                (len(run) < MIN_DASHES or not _regular(run)):
            # Two pieces with a gap are two lines (e.g. a leader broken by its
            # text), not a dash pattern.
            out.extend(x[2] for x in run)
            continue
        if len(run) == 1:
            out.append(run[0][2])
            continue
        lo, hi = min(x[0] for x in run), max(x[1] for x in run)
        gaps = _gaps([(x[0], x[1]) for x in run])
        if not gaps:  # touching pieces of one solid line (e.g. split by a junction)
            style_tag = None
        else:
            dashes = [x[1] - x[0] for x in run]
            style_tag = "axial" if (min(dashes) <= DOT_MAX and max(dashes) > 2 * DOT_MAX) \
                or _long_short(dashes) else "dashed"
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


def _regular(run: list) -> bool:
    """Dashes of one pattern repeat: the long dashes inside the run (the end
    ones may be cut) have about the same length."""
    lengths = [x[1] - x[0] for x in run]
    if min(lengths) <= DOT_MAX:  # dash-dot: the dots already show the pattern
        return True
    inner = lengths[1:-1] or lengths
    longs = [v for v in inner if v > DOT_MAX]
    if len(longs) < 2:
        return True
    # one dash length (hidden line) or two (AutoCAD CENTER: long dash, short dash)
    return len(_length_clusters(longs)) <= 2


def _length_clusters(values: list[float]) -> list[list[float]]:
    clusters: list[list[float]] = []
    for v in sorted(values):
        if clusters and v <= 1.35 * clusters[-1][0] + 0.3:
            clusters[-1].append(v)
        else:
            clusters.append([v])
    return clusters


def _long_short(lengths: list[float]) -> bool:
    """Long and short dashes alternating (CENTER-type pattern without dots)."""
    inner = lengths[1:-1] if len(lengths) > 3 else lengths
    clusters = _length_clusters(inner)
    return len(clusters) == 2 and clusters[1][0] >= 2.5 * clusters[0][-1]


def _peel_long_ends(run: list) -> list[list]:
    """A solid line continuing a dash line (an extension line of a dimension
    on the same straight, touching the first dash or after a gap) is much
    longer than the dashes: take it off the ends of the run as its own line."""
    if len(run) < 4:
        return [run]
    inner = [x[1] - x[0] for x in run[1:-1]]
    limit = 1.5 * max(inner) + 0.5
    parts = []
    if run[0][1] - run[0][0] > limit:
        parts.append([run[0]])
        run = run[1:]
    tail = None
    if run[-1][1] - run[-1][0] > limit:
        tail = [run[-1]]
        run = run[:-1]
    parts.append(run)
    if tail:
        parts.append(tail)
    return parts


def _split_irregular(run: list) -> list[list]:
    """Split a run where one gap is much larger than the pattern's gaps
    (a separate line lying on the continuation of a dash line)."""
    gaps = []
    reach = run[0][1]
    for iv in run[1:]:
        gaps.append(iv[0] - reach)
        reach = max(reach, iv[1])
    real = sorted(g for g in gaps if g > 0.05)
    if len(real) < 2:
        return [run]
    limit = 2.5 * real[len(real) // 2] + 0.5
    parts = [[run[0]]]
    for iv, g in zip(run[1:], gaps):
        if g > limit:
            parts.append([iv])
        else:
            parts[-1].append(iv)
    return parts


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

    groups, fits = _join_groups(groups, fits)
    out = []
    for group, ((cx, cy), r) in zip(groups, fits):
        spans = [_span_around(g, (cx, cy)) for g in group]
        for run in _arc_runs(spans, r):
            pieces = [g for _, _, g in run]
            if len(run) == 1:
                out.append(pieces[0])
                continue
            covered, start, end = _arc_union(run)
            points = [p for g in pieces for p in g.points]
            error = max(g.error for g in pieces)
            if covered >= CIRCLE_COVERAGE:
                merged = Primitive("circle", points, pieces[0].width, error, center=(cx, cy),
                                   radius=r)
            else:
                merged = Primitive("arc", points, pieces[0].width, error, center=(cx, cy),
                                   radius=r, start_angle=start, end_angle=end,
                                   sweep=(end - start) % 360)
            merged.tags = set().union(*(g.tags for g in pieces)) | {f"pieces={len(run)}"}
            # Pieces with gaps between them are dashes of a dash-dot circle;
            # touching pieces are one solid arc (e.g. chained angular dimensions).
            if covered - sum(w for _, w, _ in run) > 0.5:
                merged.tags.add("axial")
            out.append(merged)
    return out


def _join_groups(groups, fits):
    """Second pass: a group started by a short, badly fitted dash may describe
    the same circle as another group. Join groups whose points all lie on the
    other's circle, refitting after each join."""
    changed = True
    while changed:
        changed = False
        order = sorted(range(len(groups)), key=lambda i: -sum(len(g.points) for g in groups[i]))
        for ai, i in enumerate(order):
            for j in order[ai + 1:]:
                if groups[i] is None or groups[j] is None:
                    continue
                center, radius = fits[i]
                tol = 0.25 + 0.003 * radius
                if all(abs(math.dist(p, center) - radius) <= tol for g in groups[j] for p in g.points):
                    groups[i] = groups[i] + groups[j]
                    groups[j] = None
                    fit = fit_circle([p for g in groups[i] for p in g.points])
                    if fit is not None:
                        fits[i] = (fit.center, fit.radius)
                    changed = True
        keep = [k for k, g in enumerate(groups) if g is not None]
        groups, fits = [groups[k] for k in keep], [fits[k] for k in keep]
    return groups, fits


def _span_around(piece: Primitive, center) -> tuple[float, float, Primitive]:
    """(start, sweep, piece) of a dash measured around the common centre.
    A dot of a dash-dot circle has two vertices; its own centre is meaningless."""
    angles = [math.degrees(math.atan2(p[1] - center[1], p[0] - center[0])) for p in piece.points]
    unwrapped = [angles[0]]
    for a in angles[1:]:
        unwrapped.append(unwrapped[-1] + ((a - unwrapped[-1] + 180.0) % 360.0 - 180.0))
    lo, hi = min(unwrapped), max(unwrapped)
    return lo % 360.0, hi - lo, piece


def _arc_runs(spans: list[tuple], radius: float) -> list[list[tuple]]:
    """Split co-circular pieces into runs whose gaps are dash-sized."""
    max_gap_deg = math.degrees(MAX_GAP / max(radius, 1e-6))
    pieces = sorted(spans, key=lambda g: g[0])
    runs: list[list[tuple]] = [[pieces[0]]]
    reach = pieces[0][0] + pieces[0][1]
    for g in pieces[1:]:
        start = g[0]
        if start - reach <= max_gap_deg:
            runs[-1].append(g)
        else:
            runs.append([g])
        reach = max(reach, start + g[1])
    if len(runs) > 1:  # close the circle across 0°
        first = runs[0][0][0] + 360.0
        if first - reach <= max_gap_deg:
            runs[0] = runs.pop() + runs[0]
    return runs


def _arc_union(group: list[tuple]) -> tuple[float, float, float]:
    """Angular span covered by the dashes including the gaps between them.

    Returns (span, start, end); the largest uncovered gap is taken as the
    opening of the arc.
    """
    spans = sorted((s % 360.0, w) for s, w, _ in group)
    # Sweep the sorted intervals once (overlapping dashes are allowed); the
    # gap before each interval is measured from the farthest end so far.
    reach = spans[0][0] + spans[0][1]
    largest_gap, gap_end = 0.0, spans[0][0]
    for start, width in spans[1:]:
        gap = start - reach
        if gap > largest_gap:
            largest_gap, gap_end = gap, start
        reach = max(reach, start + width)
    wrap = spans[0][0] + 360.0 - reach
    if wrap > largest_gap:
        largest_gap, gap_end = wrap, spans[0][0]
    largest_gap = max(0.0, largest_gap)
    span = 360.0 - largest_gap
    return span, gap_end % 360.0, (gap_end + span) % 360.0
