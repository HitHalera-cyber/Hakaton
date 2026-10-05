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
from dataclasses import dataclass, field

from ..geometry.fitting import angle_diff, direction_deg, point_line_distance, point_segment_distance
from ..geometry.segmentation import Primitive
from ..pdf.vector_extractor import RawText
from .arrows import Arrow

DIM_TEXT_RE = re.compile(
    r"^(?P<prefix>[ØR⌀]|M(?=\d))?\s*(?P<value>\d+(?:[.,]\d+)?)\s*(?P<deg>°)?\s*(?P<tail>.*)$")
TIP_ON_LINE = 0.35  # mm
PARALLEL_TOLERANCE = 3.0  # deg
EXT_ON_TIP = 0.35  # mm
CENTER_ON_LINE = 0.4  # mm


@dataclass
class DimText:
    raw: RawText
    prefix: str
    value: float
    decimals: int
    angular: bool
    tail: str

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
    if not m:
        return None
    raw_value = m.group("value")
    value = float(raw_value.replace(",", "."))
    decimals = len(re.split(r"[.,]", raw_value)[1]) if re.search(r"[.,]", raw_value) else 0
    prefix = (m.group("prefix") or "").replace("⌀", "Ø")
    return DimText(t, prefix, value, decimals, bool(m.group("deg")), m.group("tail").strip())


def find_dimensions(texts: list[DimText], arrows: list[Arrow], thin: list[Primitive],
                    curves: list[Primitive]) -> list[FoundDimension]:
    """Match each dimension text with its dimension line and arrows.

    ``thin`` are thin lines/arcs (dimension and extension line candidates),
    ``curves`` the main circles/arcs that diameter/radius dims may refer to.
    """
    found = []
    for dt in texts:
        dim = _angular(dt, arrows, thin) if dt.angular else _linear(dt, arrows, thin, curves)
        if dim is not None:
            found.append(dim)
    return found


# --- linear, diameter, radius ---------------------------------------------------


def _linear(dt: DimText, arrows, thin, curves) -> FoundDimension | None:
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
        score = across + 0.2 * along_gap + (0.0 if len(tips) >= 2 else 10.0)
        if best is None or score < best[0]:
            best = (score, line, tips)
    if best is None:
        return None
    _, line, tips = best
    shelves = _collinear_pieces(line, dt, thin)

    if len(tips) >= 2:
        t1, t2 = _farthest_pair(tips)
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

    # One arrow: a radius or a diameter leader ending on a circle.
    tip = tips[0]
    circle = _circle_on_leader(tip, line, curves)
    if circle is None:
        return None
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


def _tips_on_line(line: Primitive, arrows: list[Arrow]) -> list[tuple[float, float]]:
    ux, uy = _unit(line.p1, line.p2)
    tips = []
    for a in arrows:
        if point_line_distance(a.tip, line.p1, line.p2) > TIP_ON_LINE:
            continue
        if abs(a.direction[0] * uy - a.direction[1] * ux) > 0.1:  # arrow not along the line
            continue
        t = (a.tip[0] - line.p1[0]) * ux + (a.tip[1] - line.p1[1]) * uy
        if -1.0 <= t <= line.length + 1.0:
            tips.append(a.tip)
    return tips


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


def _angular(dt: DimText, arrows, thin) -> FoundDimension | None:
    best = None
    for arc in thin:
        if arc.kind != "arc":
            continue
        d = abs(math.dist(dt.center, arc.center) - arc.radius)
        if d > dt.raw.height + 4.0:
            continue
        tips = [a.tip for a in arrows if abs(math.dist(a.tip, arc.center) - arc.radius) <= TIP_ON_LINE]
        if len(tips) < 2:
            continue
        if best is None or d < best[0]:
            best = (d, arc, tips)
    if best is None:
        return None
    _, arc, tips = best
    t1, t2 = _farthest_pair(tips)
    a1 = math.atan2(t1[1] - arc.center[1], t1[0] - arc.center[0])
    a2 = math.atan2(t2[1] - arc.center[1], t2[0] - arc.center[0])
    angle = abs(math.degrees((a2 - a1 + math.pi) % (2 * math.pi) - math.pi))
    dim = FoundDimension("angular", dt, angle, p1=t1, p2=t2, center=arc.center,
                         radius=arc.radius, line_point=_arc_mid(arc), tips=2, used=[arc])
    # Extension lines run radially from the vertex through the tips; the
    # measured points are their ends nearest the vertex.
    points = []
    for tip in (t1, t2):
        point = tip
        for ext in thin:
            if ext.kind == "line" and point_segment_distance(tip, ext.p1, ext.p2) <= EXT_ON_TIP \
                    and point_line_distance(arc.center, ext.p1, ext.p2) <= 1.0:
                point = min((ext.p1, ext.p2), key=lambda p: math.dist(p, arc.center))
                dim.used.append(ext)
                break
        points.append(point)
    dim.p1, dim.p2 = points
    return dim


def _arc_mid(arc: Primitive):
    mid = math.radians(arc.start_angle + arc.sweep / 2)
    return (arc.center[0] + arc.radius * math.cos(mid), arc.center[1] + arc.radius * math.sin(mid))
