"""Assemble dimensions from their drawn parts: value text, dimension line,
arrowheads and extension lines.

For every text that looks like a dimension value ("Ø25", "4,67", "45°",
"R10", "120 ±0,1") the nearest matching dimension line is searched:
a thin line parallel to the text (linear, diameter) or a thin arc around it
(angular). Arrow tips lying on that line give the measured size; extension
lines leading from the tips give the measured points of the part.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field, replace

from ..geometry.fitting import angle_diff, direction_deg, point_line_distance, point_segment_distance
from ..geometry.segmentation import Primitive
from ..pdf.vector_extractor import RawText
from .arrows import Arrow

DIM_TEXT_RE = re.compile(
    # "6 отв. Ø18", "4 holes Ø9", "2×Ø8", "3xM6" — the count of equal elements
    r"^(?:(?P<count>\d+)\s*(?:(?:отв|holes?)\.?\s*|[x×X]\s*(?=[ØR⌀M])))?"
    r"(?P<prefix>[ØR⌀]|M(?=\d))?\s*(?P<value>\d+(?:[.,]\d+)?)"
    r"(?:\s*(?P<deg>°)\s*(?:(?P<min>\d{1,2})\s*['′])?(?:\s*(?P<sec>\d{1,2})\s*(?:\"|″|''))?)?"
    r"\s*(?P<tail>.*)$")
# What may follow the value: a tolerance (±0,1 / +0,2 -0,1), a fit (H7, (h6)),
# a thread pitch (×1,5) or a chamfer angle (×45°). Anything else ("2u", "1m",
# "130 R, мм", two numbers) is ordinary text, not a dimension.
TAIL_RE = re.compile(
    r"^(|±\s*\d+(?:[.,]\d+)?°?|[+\-−]\s*\d+(?:[.,]\d+)?(?:\s*[+\-−]\s*\d+(?:[.,]\d+)?)?"
    r"|\(?[A-Za-z]{1,2}\d{1,2}\)?|[x×]\s*\d+(?:[.,]\d+)?°?)"
    r"\s*\*?$")  # "*" marks a size ensured by the tool (ГОСТ 2.307)
TIP_ON_LINE = 0.35  # mm
PARALLEL_TOLERANCE = 3.0  # deg
EXT_ON_TIP = 0.35  # mm
CENTER_ON_LINE = 0.4  # mm
MAX_TEXT_GAP = 15.0  # mm; a value text is never farther than this beyond its dimension line


@dataclass
class DimText:
    raw: RawText
    prefix: str
    value: float
    decimals: int
    angular: bool
    tail: str
    count: int = 1

    @property
    def center(self) -> tuple[float, float]:
        b = self.raw.bbox
        return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)


@dataclass
class FoundDimension:
    dim_type: str
    text: DimText
    measured: float
    p1: tuple[float, float] | None = None
    p2: tuple[float, float] | None = None
    line_point: tuple[float, float] | None = None
    center: tuple[float, float] | None = None
    radius: float | None = None
    orientation: str = "aligned"
    ref: Primitive | None = None
    tips: int = 0
    used: list[Primitive] = field(default_factory=list)


def parse_dim_text(t: RawText) -> DimText | None:
    m = DIM_TEXT_RE.match(t.text.strip())
    if not m or not TAIL_RE.match(m.group("tail").strip()):
        return None
    raw_value = m.group("value")
    value = float(raw_value.replace(",", "."))
    decimals = len(re.split(r"[.,]", raw_value)[1]) if re.search(r"[.,]", raw_value) else 0
    angular = bool(m.group("deg"))
    if angular:  # 37°57' → 37.95°; the rounding unit is then a minute
        minutes, seconds = int(m.group("min") or 0), int(m.group("sec") or 0)
        value += minutes / 60 + seconds / 3600
        if m.group("min"):
            decimals = 2
    prefix = (m.group("prefix") or "").replace("⌀", "Ø")
    count = int(m.group("count") or 1)
    if count < 1:
        return None
    return DimText(t, prefix, value, decimals, angular, m.group("tail").strip(), count)


DEVIATION_RE = re.compile(r"^[+\-−±]\s*\d+(?:[.,]\d+)?$")


def attach_deviations(found: list[FoundDimension], texts: list[RawText]) -> list[RawText]:
    """Deviations written as separate small texts after the value ("R3" and a
    raised "+0,2") join their dimension: "R3+0,2". Returns the texts left over."""
    left = []
    for t in texts:
        best, best_dist = None, None
        if DEVIATION_RE.match(t.text.strip()):
            for d in found:
                raw = d.text.raw
                if angle_diff(raw.angle, t.angle, 360.0) > 3.0:
                    continue
                end = raw.last_origin or raw.origin
                a = math.radians(raw.angle)
                dx, dy = t.origin[0] - end[0], t.origin[1] - end[1]
                along = dx * math.cos(a) + dy * math.sin(a)
                across = -dx * math.sin(a) + dy * math.cos(a)
                if 0.0 < along <= 2.5 * raw.height and abs(across) <= 1.2 * raw.height:
                    if best is None or along < best_dist:
                        best, best_dist = d, along
        if best is None:
            left.append(t)
            continue
        dev = t.text.strip().replace("−", "-")
        best.text = replace(best.text, raw=replace(best.text.raw, text=best.text.raw.text + dev),
                            tail=(best.text.tail + dev).strip())
    return left


def find_dimensions(texts: list[DimText], arrows: list[Arrow], thin: list[Primitive],
                    curves: list[Primitive], axes: list[Primitive] = (),
                    lines: list[Primitive] = ()) -> list[FoundDimension]:
    """Match each dimension text with its dimension line and arrows.

    ``thin`` are thin lines/arcs (dimension and extension line candidates),
    ``curves`` the main circles/arcs that diameter/radius dims may refer to,
    ``axes`` the axis lines (a diameter on a half view ends past the axis).
    """
    found = []
    for dt in texts:
        dim = _angular(dt, arrows, thin, lines) if dt.angular \
            else _linear(dt, arrows, thin, curves, axes)
        if dim is not None:
            found.append(dim)
    return found


# --- linear, diameter, radius ---------------------------------------------------


def _linear(dt: DimText, arrows, thin, curves, axes=()) -> FoundDimension | None:
    best = None
    for line in thin:
        if line.kind != "line" or line.length < 1.0:
            continue
        if angle_diff(direction_deg(line.p1, line.p2), dt.raw.angle % 180.0) > PARALLEL_TOLERANCE:
            continue
        across = point_line_distance(dt.center, line.p1, line.p2)
        if across > dt.raw.height * 0.6 + 3.0:
            continue
        tips = _tips_on_line(line, arrows)
        if not tips:
            continue
        along_gap = _outside_extent(dt.center, line)
        if along_gap > max(MAX_TEXT_GAP, 3 * dt.raw.height) \
                and _outside_shelf(dt.center, line, thin) > dt.raw.height:
            continue
        # The value is written above its dimension line: the line lies on the
        # baseline side of the text (below it in the text's own frame).
        a = math.radians(dt.raw.angle)
        down = (math.sin(a), -math.cos(a))
        foot = _foot(dt.center, line)
        side = (foot[0] - dt.center[0]) * down[0] + (foot[1] - dt.center[1]) * down[1]
        score = across + 0.2 * along_gap + (0.0 if len(tips) >= 2 else 10.0) \
            + (0.0 if side >= -0.3 else 5.0)
        if best is None or score < best[0]:
            best = (score, line, tips)
    if best is None:
        return None
    _, line, tips = best
    shelves = _collinear_pieces(line, dt, thin)

    if len(tips) >= 2:
        t1, t2 = _pair_near_text(tips, line, dt.center)
        measured = math.dist(t1, t2)
        circle = _circle_between(t1, t2, curves) if dt.prefix == "Ø" else None
        if circle is not None:
            return FoundDimension("diameter", dt, measured, p1=t1, p2=t2, center=circle.center,
                                  radius=circle.radius, ref=circle, tips=2,
                                  used=[line] + shelves)
        dim = FoundDimension("linear", dt, measured, p1=t1, p2=t2, tips=2, used=[line] + shelves,
                             line_point=((t1[0] + t2[0]) / 2, (t1[1] + t2[1]) / 2))
        _attach_extension_lines(dim, line, thin)
        return dim

    # One arrow: a radius or a diameter leader ending on a circle …
    tip = tips[0]
    circle = _circle_on_leader(tip, line, curves)
    if circle is None:
        # … or a diameter on a half view: the line runs past the axis and
        # only one arrow is drawn. The size is twice the tip–axis distance.
        cross = _axis_crossing(line, axes) if dt.prefix == "Ø" else None
        if cross is None:
            return None
        mirror = (2 * cross[0] - tip[0], 2 * cross[1] - tip[1])
        dim = FoundDimension("linear", dt, 2 * math.dist(tip, cross), p1=tip, p2=mirror, tips=1,
                             used=[line] + shelves, line_point=cross)
        _attach_extension_lines(dim, line, thin)
        dim.p2 = mirror if dim.p2 == mirror else dim.p2
        return dim
    if dt.prefix == "Ø":
        return FoundDimension("diameter", dt, 2 * circle.radius, p1=tip, center=circle.center,
                              radius=circle.radius, ref=circle, tips=1, used=[line] + shelves)
    return FoundDimension("radius", dt, circle.radius, p1=tip, center=circle.center,
                          radius=circle.radius, ref=circle, tips=1, used=[line] + shelves)


def _collinear_pieces(line: Primitive, dt: DimText, thin) -> list[Primitive]:
    """Other pieces of the same dimension line (e.g. the shelf under an outside text)."""
    ux, uy = _unit(line.p1, line.p2)

    def t(p):
        return (p[0] - line.p1[0]) * ux + (p[1] - line.p1[1]) * uy

    lo = min(0.0, t(dt.center)) - 1.0
    hi = max(line.length, t(dt.center)) + 1.0
    out = []
    for other in thin:
        if other is line or other.kind != "line" or "axial" in other.tags:
            continue
        if point_line_distance(other.p1, line.p1, line.p2) > 0.2 \
                or point_line_distance(other.p2, line.p1, line.p2) > 0.2:
            continue
        a, b = sorted((t(other.p1), t(other.p2)))
        if b >= lo and a <= hi:
            out.append(other)
    return out


def _foot(p, line: Primitive):
    ux, uy = _unit(line.p1, line.p2)
    t = (p[0] - line.p1[0]) * ux + (p[1] - line.p1[1]) * uy
    return (line.p1[0] + ux * t, line.p1[1] + uy * t)


def _outside_shelf(p, line: Primitive, thin) -> float:
    """Distance of ``p`` beyond the dimension line extended by its collinear
    pieces (the shelf a small dimension's text is written on)."""
    ux, uy = _unit(line.p1, line.p2)

    def t(q):
        return (q[0] - line.p1[0]) * ux + (q[1] - line.p1[1]) * uy

    lo, hi = 0.0, line.length
    pieces = [o for o in thin if o is not line and o.kind == "line"
              and point_line_distance(o.p1, line.p1, line.p2) <= 0.2
              and point_line_distance(o.p2, line.p1, line.p2) <= 0.2]
    grown = True
    while grown:
        grown = False
        for o in pieces:
            a, b = sorted((t(o.p1), t(o.p2)))
            if a <= hi + 0.5 and b >= lo - 0.5 and (a < lo or b > hi):
                lo, hi = min(lo, a), max(hi, b)
                grown = True
    tp = t(p)
    return max(0.0, lo - tp, tp - hi)


def _tips_on_line(line: Primitive, arrows: list[Arrow]) -> list[tuple[float, float]]:
    ux, uy = _unit(line.p1, line.p2)
    tips = []
    for a in arrows:
        if point_line_distance(a.tip, line.p1, line.p2) > TIP_ON_LINE:
            continue
        if abs(a.direction[0] * uy - a.direction[1] * ux) > 0.1:  # arrow not along the line
            continue
        t = (a.tip[0] - line.p1[0]) * ux + (a.tip[1] - line.p1[1]) * uy
        along = a.direction[0] * ux + a.direction[1] * uy
        if -1.0 <= t <= line.length + 1.0:
            tips.append(a.tip)
        # AutoCAD-style dimension lines stop at the base of a filled arrow:
        # the tip is then up to one arrow length beyond the line end, pointing away.
        elif (-1.0 - a.length <= t < -1.0 and along < 0) or \
                (line.length + 1.0 < t <= line.length + 1.0 + a.length and along > 0):
            tips.append(a.tip)
    return tips


def _pair_near_text(tips, line: Primitive, text_center):
    """Two neighbouring arrow tips whose interval is nearest to the text.

    Chain dimensions share one line with many arrows; the value belongs to
    the span it is written over (or next to, for small spans).
    """
    ux, uy = _unit(line.p1, line.p2)

    def t(p):
        return (p[0] - line.p1[0]) * ux + (p[1] - line.p1[1]) * uy

    ordered = sorted(tips, key=t)
    tc = t(text_center)
    best = None
    for a, b in zip(ordered, ordered[1:]):
        lo, hi = t(a), t(b)
        if hi - lo < 0.3:  # two arrows at one point (touching chain dims)
            continue
        gap = max(0.0, lo - tc, tc - hi)
        key = (round(gap, 1), hi - lo)
        if best is None or key < best[0]:
            best = (key, a, b)
    if best is None:
        return _farthest_pair(tips)
    return best[1], best[2]


def _farthest_pair(points):
    best = (points[0], points[1])
    for i, a in enumerate(points):
        for b in points[i + 1:]:
            if math.dist(a, b) > math.dist(*best):
                best = (a, b)
    return best


def _unit(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dy) or 1.0
    return dx / n, dy / n


def _outside_extent(p, line: Primitive) -> float:
    ux, uy = _unit(line.p1, line.p2)
    t = (p[0] - line.p1[0]) * ux + (p[1] - line.p1[1]) * uy
    return max(0.0, -t, t - line.length)


def _axis_crossing(line: Primitive, axes) -> tuple[float, float] | None:
    """Point where the dimension line crosses a perpendicular axis line."""
    for ax in axes:
        if ax.kind != "line":
            continue
        if angle_diff(direction_deg(ax.p1, ax.p2), direction_deg(line.p1, line.p2) + 90.0) > 2.0:
            continue
        x = _intersection(line.p1, line.p2, ax.p1, ax.p2)
        if x is None:
            continue
        on_line = point_segment_distance(x, line.p1, line.p2) <= 6.0
        on_axis = point_segment_distance(x, ax.p1, ax.p2) <= 1.0
        if on_line and on_axis:
            return x
    return None


def _intersection(a1, a2, b1, b2):
    d = (a2[0] - a1[0]) * (b2[1] - b1[1]) - (a2[1] - a1[1]) * (b2[0] - b1[0])
    if abs(d) < 1e-12:
        return None
    t = ((b1[0] - a1[0]) * (b2[1] - b1[1]) - (b1[1] - a1[1]) * (b2[0] - b1[0])) / d
    return (a1[0] + t * (a2[0] - a1[0]), a1[1] + t * (a2[1] - a1[1]))


def _circle_between(t1, t2, curves) -> Primitive | None:
    mid = ((t1[0] + t2[0]) / 2, (t1[1] + t2[1]) / 2)
    half = math.dist(t1, t2) / 2
    for c in curves:
        if c.kind in ("circle", "arc") and math.dist(c.center, mid) <= CENTER_ON_LINE \
                and abs(c.radius - half) <= 0.02 * half + 0.1:
            return c
    return None


def _circle_on_leader(tip, line: Primitive, curves) -> Primitive | None:
    for c in curves:
        if c.kind not in ("circle", "arc"):
            continue
        if point_line_distance(c.center, line.p1, line.p2) <= CENTER_ON_LINE \
                and abs(math.dist(tip, c.center) - c.radius) <= 0.2:
            return c
    return None


def _attach_extension_lines(dim: FoundDimension, dim_line: Primitive, thin) -> None:
    """Replace arrow tips by the far ends of the extension lines through them."""
    line_dir = direction_deg(dim_line.p1, dim_line.p2)
    points = []
    for tip in (dim.p1, dim.p2):
        point = tip
        for ext in thin:
            if ext is dim_line or ext.kind != "line":
                continue
            if angle_diff(direction_deg(ext.p1, ext.p2), line_dir + 90.0) > PARALLEL_TOLERANCE:
                continue
            if point_segment_distance(tip, ext.p1, ext.p2) > EXT_ON_TIP:
                continue
            far = max((ext.p1, ext.p2), key=lambda p: math.dist(p, tip))
            # The measured point is where the extension line meets the dim-line
            # normal through the tip — i.e. the far end projected on that normal.
            point = far
            dim.used.append(ext)
            break
        points.append(point)
    dim.p1, dim.p2 = points
    if angle_diff(line_dir, 0.0) <= PARALLEL_TOLERANCE:
        dim.orientation = "horizontal"
    elif angle_diff(line_dir, 90.0) <= PARALLEL_TOLERANCE:
        dim.orientation = "vertical"


# --- angular ----------------------------------------------------------------------


def _angular(dt: DimText, arrows, thin, lines=()) -> FoundDimension | None:
    best = None
    for arc in thin:
        if arc.kind != "arc":
            continue
        d = abs(math.dist(dt.center, arc.center) - arc.radius)
        if d > dt.raw.height + 4.0:
            continue
        tips = [a.tip for a in arrows
                if abs(math.dist(a.tip, arc.center) - arc.radius) <= TIP_ON_LINE
                and _within_arc(arc, a.tip, margin=10.0)]
        if len(tips) < 2 or not _within_arc(arc, dt.center, margin=30.0):
            continue
        if best is None or d < best[0]:
            best = (d, arc, tips)
    if best is None:
        return None
    _, arc, tips = best
    t1, t2 = _angular_pair_near_text(tips, arc, dt.center)
    a1 = math.atan2(t1[1] - arc.center[1], t1[0] - arc.center[0])
    a2 = math.atan2(t2[1] - arc.center[1], t2[0] - arc.center[0])
    angle = abs(math.degrees((a2 - a1 + math.pi) % (2 * math.pi) - math.pi))
    center = arc.center
    sides = [_side_line(tip, arc.center, list(thin) + list(lines)) for tip in (t1, t2)]
    if all(sides):
        # Both sides are drawn lines: the vertex is their intersection and the
        # angle theirs — exact, unlike tips read from filled arrowheads.
        vertex = _line_cross(*sides)
        if vertex is not None and math.dist(vertex, arc.center) <= 1.0:
            center = vertex
            t1, t2 = (_project(t, *line) for t, line in zip((t1, t2), sides))
            a1 = math.atan2(t1[1] - center[1], t1[0] - center[0])
            a2 = math.atan2(t2[1] - center[1], t2[0] - center[0])
            angle = abs(math.degrees((a2 - a1 + math.pi) % (2 * math.pi) - math.pi))
    dim = FoundDimension("angular", dt, angle, p1=t1, p2=t2, center=center,
                         radius=math.dist(center, t1), line_point=_arc_mid(arc), tips=2,
                         used=[arc])
    # Extension lines run radially from the vertex through the tips. They are
    # consumed, but p1/p2 stay at the tips: an extension line may start at the
    # vertex itself, where the direction of the side is undefined.
    for tip in (t1, t2):
        for ext in thin:
            if ext.kind == "line" and point_segment_distance(tip, ext.p1, ext.p2) <= EXT_ON_TIP \
                    and point_line_distance(arc.center, ext.p1, ext.p2) <= 1.0:
                dim.used.append(ext)
                break
    return dim


def _side_line(tip, vertex, lines):
    """The longest line through the tip that also passes near the vertex."""
    best = None
    for ln in lines:
        if ln.kind != "line" or ln.length < 1.0:
            continue
        if point_line_distance(tip, ln.p1, ln.p2) <= EXT_ON_TIP \
                and point_line_distance(vertex, ln.p1, ln.p2) <= 1.0 \
                and (best is None or ln.length > best.length):
            best = ln
    return (best.p1, best.p2) if best else None


def _line_cross(l1, l2):
    (x1, y1), (x2, y2) = l1
    (x3, y3), (x4, y4) = l2
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < 1e-9:
        return None
    a = x1 * y2 - y1 * x2
    b = x3 * y4 - y3 * x4
    return ((a * (x3 - x4) - (x1 - x2) * b) / den, (a * (y3 - y4) - (y1 - y2) * b) / den)


def _project(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)
    return (a[0] + dx * t, a[1] + dy * t)


def _arc_mid(arc: Primitive):
    mid = math.radians(arc.start_angle + arc.sweep / 2)
    return (arc.center[0] + arc.radius * math.cos(mid), arc.center[1] + arc.radius * math.sin(mid))


def _polar_deg(center, p) -> float:
    return math.degrees(math.atan2(p[1] - center[1], p[0] - center[0])) % 360.0


def _within_arc(arc: Primitive, p, margin: float) -> bool:
    rel = (_polar_deg(arc.center, p) - arc.start_angle) % 360.0
    return rel <= arc.sweep + margin or rel >= 360.0 - margin


def _angular_pair_near_text(tips, arc: Primitive, text_center):
    """Neighbouring tips (by angle along the arc) around the text position."""
    def rel(p):
        r = (_polar_deg(arc.center, p) - arc.start_angle) % 360.0
        return r - 360.0 if r > 360.0 - 30.0 else r

    ordered = sorted(tips, key=rel)
    tc = rel(text_center)
    best = None
    for a, b in zip(ordered, ordered[1:]):
        lo, hi = rel(a), rel(b)
        if hi - lo < 0.05:
            continue
        gap = max(0.0, lo - tc, tc - hi)
        key = (round(gap, 1), hi - lo)
        if best is None or key < best[0]:
            best = (key, a, b)
    return (best[1], best[2]) if best else _farthest_pair(tips)
