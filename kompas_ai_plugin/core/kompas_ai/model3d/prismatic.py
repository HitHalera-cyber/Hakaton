"""Parts that are not bodies of revolution: a plate, a bracket, a cover —
the outline of the main view extruded to the part's thickness, its inner
closed outlines (holes, slots, windows) cut through.

The main view is the biggest closed outline of the sheet. The thickness is
read, in this order: a note (s4, S = 4, «толщина 4»); the view next to it in
projection (on the same height: its width; under or over it: its height),
taken as the number of a size that measures it; else a plausible value,
said in the report so it can be changed in KOMPAS.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from shapely.geometry import LinearRing, Polygon
from shapely.ops import unary_union

from .. import ir

THICKNESS_RE = re.compile(r"(?:^|\s)(?:s|S|t|толщин[аыу]?)\s*=?\s*(\d+(?:[.,]\d+)?)")


@dataclass
class ExtrudeProfile:
    loops: list  # sketch loops in model mm: ("line", p1, p2) / ("arc", c, r, a1, a2)
    thickness: float  # model mm
    how: str  # where the thickness came from
    width: float
    height: float
    holes: int
    sheet_box: tuple = (0.0, 0.0, 0.0, 0.0)  # the main view on the sheet, mm
    scale: float = 1.0

    def summary(self) -> str:
        return (f"Призматическая деталь: контур {self.width:.2f} × {self.height:.2f} мм, "
                f"толщина {self.thickness:g} мм ({self.how}), сквозных вырезов {self.holes}")


def find_extrude_profile(drawing: ir.Drawing) -> ExtrudeProfile | None:
    from ..model3d.revolve import main_primitives
    from ..semantics.regions import contour_faces

    faces = contour_faces(main_primitives(drawing))
    if not faces:
        return None
    union = unary_union(faces)
    views = sorted((g for g in (union.geoms if hasattr(union, "geoms") else [union])
                    if g.geom_type == "Polygon"), key=lambda g: -g.area)
    if not views:
        return None
    # the view that shows the shape: the most edges and cuts (an L, a plate
    # with holes) — not the plain rectangle seen from the side or above,
    # even when that is bigger; small views (details) do not compete
    big = [v for v in views if v.area >= 0.2 * views[0].area]
    main = max(big, key=lambda v: (_shape_score(v, faces), v.area))
    views = [main] + [v for v in views if v is not main]
    outer = Polygon(main.exterior)
    ring = LinearRing(main.exterior.coords)
    # the material next to the outline; what it encloses are the cuts
    band = unary_union([f for f in faces if f.representative_point().within(outer)
                        and f.exterior.distance(ring) < 0.05])
    cuts = []
    for part in (band.geoms if hasattr(band, "geoms") else [band]):
        cuts += [Polygon(r) for r in part.interiors if Polygon(r).area >= 1.0]
    cuts += [Polygon(r) for r in main.interiors if Polygon(r).area >= 1.0]
    cuts = _unique(cuts)
    if getattr(drawing, "raster", False):
        # a photo's letters are lines too: the loops of «0», «8», «Ø» are no
        # holes — a cut is round (a hole) or bigger than a letter
        cuts = [q for q in cuts if q.area >= 25.0 or _round(q)]
    scale = drawing.scale.value or 1.0
    x0, y0, x1, y1 = outer.bounds
    thickness, how = _thickness(drawing, main, views[1:], scale)
    exact = _exact_geometry(drawing)
    loops = [_loop(list(outer.exterior.coords), (x0, y0), scale, exact)]
    loops += [_loop(list(c.exterior.coords), (x0, y0), scale, exact) for c in cuts]
    loops = [l for l in loops if l]
    if not loops:
        return None
    return ExtrudeProfile(loops, thickness, how, (x1 - x0) / scale, (y1 - y0) / scale,
                          len(loops) - 1, (x0, y0, x1, y1), scale)


def _shape_score(view, faces) -> int:
    """Corners of the outline (straight runs merged) plus the closed outlines
    inside it."""
    ring = view.simplify(0.05).exterior
    pts = list(ring.coords)[:-1]
    corners = 0
    for a, b, cc in zip(pts, pts[1:] + pts[:1], pts[2:] + pts[:2]):
        t1 = math.atan2(b[1] - a[1], b[0] - a[0])
        t2 = math.atan2(cc[1] - b[1], cc[0] - b[0])
        if abs((math.degrees(t2 - t1) + 180.0) % 360.0 - 180.0) > 20.0:
            corners += 1
    inner = sum(1 for f in faces if f.within(view) and f.exterior.distance(view.exterior) > 0.05)
    return corners + 2 * inner


def _round(poly) -> bool:
    """A circle bigger than a letter: as round as a circle, over 2.5 mm across."""
    if poly.area <= 0:
        return False
    roundness = 4 * math.pi * poly.area / poly.length ** 2
    x0, y0, x1, y1 = poly.bounds
    return roundness > 0.85 and min(x1 - x0, y1 - y0) >= 5.0


def _unique(polys):
    out = []
    for p in sorted(polys, key=lambda p: -p.area):
        if not any(p.symmetric_difference(q).area < 0.02 * p.area for q in out):
            out.append(p)
    return out


def _thickness(drawing, main, others, scale) -> tuple[float, str]:
    for t in drawing.of_type(ir.Text):
        m = THICKNESS_RE.search(t.text or "")
        if m:
            return float(m.group(1).replace(",", ".")), f"надпись «{t.text.strip()}»"
    x0, y0, x1, y1 = main.bounds
    best = None
    for v in others:
        a0, b0, a1, b1 = v.bounds
        if v.area < 0.02 * main.area:
            continue
        overlap_y = min(y1, b1) - max(y0, b0)
        overlap_x = min(x1, a1) - max(x0, a0)
        if overlap_y > 0.6 * (y1 - y0) and (a0 > x1 or a1 < x0):  # beside: its width
            size, gap = a1 - a0, min(abs(a0 - x1), abs(x0 - a1))
        elif overlap_x > 0.6 * (x1 - x0) and (b0 > y1 or b1 < y0):  # over/under: its height
            size, gap = b1 - b0, min(abs(b0 - y1), abs(y0 - b1))
        else:
            continue
        if best is None or gap < best[1]:
            best = (size, gap)
    if best is not None:
        measured = best[0] / scale
        for d in drawing.of_type(ir.Dimension):
            if d.nominal and d.dim_type == "linear" and abs(d.nominal - measured) <= \
                    max(0.05, 0.02 * measured):
                return d.nominal, f"вид сбоку, размер {d.text}"
        return round(measured, 2), "по виду сбоку"
    guess = max(1.0, round(min(x1 - x0, y1 - y0) / scale / 10.0))
    return guess, "не указана на чертеже — взята примерно, поправьте в КОМПАС"


def _exact_geometry(drawing):
    """The drawing's own points and curves (sheet mm): the ends of its main
    lines and arcs, and its circles and arcs (centre, radius) — the fitted
    outline is put back onto them."""
    nodes, curves = [], []
    for e in drawing.entities:
        if getattr(e, "style", None) != ir.STYLE_MAIN:
            continue
        if isinstance(e, ir.Line):
            nodes += [tuple(e.p1), tuple(e.p2)]
        elif isinstance(e, (ir.Arc, ir.Circle)):
            curves.append((tuple(e.center), e.radius))
            if isinstance(e, ir.Arc):
                for a in (e.start_angle, e.end_angle):
                    t = math.radians(a)
                    nodes.append((e.center[0] + e.radius * math.cos(t),
                                  e.center[1] + e.radius * math.sin(t)))
    return nodes, curves


SNAP = 0.5  # sheet mm: a fitted point this near a point of the drawing is that point


def _loop(coords, origin, scale, exact=((), ())):
    """A closed ring of the sheet as sketch segments in model mm (lines and
    arcs fitted back from the ring's points, then put onto the drawing's own
    ends and curves; a circle as three arcs)."""
    from ..geometry.chains import Chain
    from ..geometry.segmentation import segment_chain
    from .revolve import _join_ends, _straighten

    nodes, curves = exact

    def snap(p):
        q = min(nodes, key=lambda n: math.dist(n, p), default=None)
        return q if q is not None and math.dist(q, p) <= SNAP else p

    def curve(c, r):
        best = min(curves, key=lambda k: math.dist(k[0], c) + abs(k[1] - r), default=None)
        if best is not None and math.dist(best[0], c) <= 0.3 and abs(best[1] - r) <= 0.3:
            return best
        return c, r

    def model(p):
        return ((p[0] - origin[0]) / scale, (p[1] - origin[1]) / scale)

    segs = []
    for p in segment_chain(Chain(list(coords), 0.5, True), smooth=False):
        if p.kind == "line":
            segs.append(["line", model(snap(p.p1)), model(snap(p.p2))])
        elif p.kind == "circle":
            # three arcs: two halves would meet twice at the same pair of ends
            c, r = curve(p.center, p.radius)
            segs += [["arc", model(c), r / scale, a, a + 120.0] for a in (0.0, 120.0, 240.0)]
        else:
            # counter-clockwise from its start to its end, whichever way the
            # outline runs; the ends put onto the drawing's own
            c, r = curve(p.center, p.radius)
            ends = []
            for a in (p.start_angle, p.end_angle):
                t = math.radians(a)
                q = (p.center[0] + p.radius * math.cos(t), p.center[1] + p.radius * math.sin(t))
                # the fit may stop short where the arc runs into a line: a
                # point of the drawing on the same circle nearby is its end
                on = [n for n in nodes if abs(math.dist(n, c) - r) <= 0.05
                      and math.dist(n, q) <= max(SNAP, 0.35 * r)]
                ends.append(min(on, key=lambda n: math.dist(n, q)) if on else snap(q))
            segs.append(["arc", model(c), r / scale, angle_of(ends[0], c), angle_of(ends[1], c)])
    if not segs:
        return None
    segs = _join_ends(_straighten(segs))
    # a line takes the exact ends of the arcs beside it: the loop closes on them
    for i, s in enumerate(segs):
        prev, nxt = segs[i - 1], segs[(i + 1) % len(segs)]
        if s[0] != "line":
            continue
        if prev[0] == "arc":
            s[1] = _arc_end(prev, 1, s[1])
        if nxt[0] == "arc":
            s[2] = _arc_end(nxt, 0, s[2])
    return [tuple(s) for s in segs]


def _arc_end(arc, k, near):
    """The end of an arc (k = 0 start, 1 end) — or of its other end when that
    one is the nearer (an arc may run either way round the loop)."""
    (cx, cy), r = arc[1], arc[2]
    pts = []
    for a in (arc[3], arc[4]):
        t = math.radians(a)
        pts.append((cx + r * math.cos(t), cy + r * math.sin(t)))
    return min(pts, key=lambda q: math.dist(q, near))


def extrude_verdict(drawing: ir.Drawing) -> tuple[bool, str]:
    try:
        prof = find_extrude_profile(drawing)
    except Exception as exc:
        return False, f"контур не разобран: {exc!r}"
    if prof is None:
        return False, "нет замкнутого контура"
    return True, prof.summary()


def angle_of(p, c) -> float:
    return math.degrees(math.atan2(p[1] - c[1], p[0] - c[0])) % 360.0
