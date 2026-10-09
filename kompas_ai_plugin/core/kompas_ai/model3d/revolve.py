"""Profile of a body of revolution (shaft, fitting, bushing) from a drawing.

A turned part is drawn along its axis. The half of the view on one side of
the axis, revolved 360° around it, gives the solid:
  * a section (разрез): the hatched material on one side of the axis is
    exactly the profile — the bore is already left out;
  * a plain view: the faces bounded by the outline on one side of the axis
    that touch the axis (the part is solid there).
The profile is returned in model millimetres: x along the axis from its
start, y the distance from the axis (≥ 0).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from .. import ir
from ..geometry.segmentation import Primitive
from ..semantics.regions import contour_faces

MIN_AXIS = 20.0  # sheet mm
TOUCH = 0.05  # sheet mm


@dataclass
class RevolveProfile:
    rings: list[list[tuple[float, float]]]  # closed loops, model mm (x along, y radius)
    axis: tuple[tuple[float, float], tuple[float, float]]  # sheet mm
    source: str  # "hatch" | "outline"
    area: float  # model mm²
    sheet_rings: list = None  # the same loops in sheet mm (exact drawing geometry)
    side: int = 1
    scale: float = 1.0

    def summary(self) -> str:
        length = max(x for r in self.rings for x, _ in r) - min(x for r in self.rings for x, _ in r)
        radius = max(y for r in self.rings for _, y in r)
        how = "заштрихованный разрез" if self.source == "hatch" else "контур вида"
        return (f"Профиль тела вращения ({how}): длина {length:.2f} мм, "
                f"наибольший диаметр {2 * radius:.2f} мм, контуров {len(self.rings)}")


def find_revolve_profile(drawing: ir.Drawing) -> RevolveProfile | None:
    scale = drawing.scale.value or 1.0
    best = None
    for axis in _axes(drawing):
        on_axis = None
        for side in (1, -1):
            faces = _view_half(drawing, axis, side)
            if not faces:
                continue
            region, source = _hatched(drawing, faces), "hatch"
            if region is None or region.is_empty:
                region, source = unary_union(faces), "outline"
            # A section shows the bore; a plain view on the other side of a
            # half-section does not — prefer the hatched side.
            score = (source == "hatch", region.area)
            if on_axis is None or score > on_axis[0]:
                on_axis = (score, region, axis, side, source)
        # between axes (views) the biggest half wins: a cross-section A-A is
        # smaller than the main view of the part
        if on_axis and (best is None or on_axis[1].area > best[1].area):
            best = on_axis
    if best is None:
        return None
    _, region, axis, side, source = best
    rings = _to_model(region, axis, side, scale)
    if not rings:
        return None
    sheet_rings = [[tuple(p) for p in ring.coords] for part in _polygons(region)
                   for ring in [part.exterior] + list(part.interiors)]
    return RevolveProfile(rings, axis, source, region.area / scale ** 2, sheet_rings, side, scale)


def _axes(drawing: ir.Drawing):
    out = []
    for l in drawing.of_type(ir.Line):
        if l.style == ir.STYLE_AXIAL and math.dist(l.p1, l.p2) >= MIN_AXIS:
            out.append((tuple(l.p1), tuple(l.p2)))
    return out


def _half_plane(axis, side, extent=1000.0) -> Polygon:
    """The strip on one side of the axis, as long as the axis."""
    (x1, y1), (x2, y2) = axis
    dx, dy = x2 - x1, y2 - y1
    n = math.hypot(dx, dy)
    nx, ny = -dy / n * side, dx / n * side
    return Polygon([(x1, y1), (x2, y2), (x2 + nx * extent, y2 + ny * extent),
                    (x1 + nx * extent, y1 + ny * extent)])


def _hatched(drawing, faces):
    """The faces of the half view that are hatched (the material of a section).
    The faces come from the final (dimension-exact) geometry; the hatch only
    tells which of them are material — its own outline predates the
    regularisation."""
    hatches = []
    for h in drawing.of_type(ir.Hatch):
        if h.contours:
            poly = Polygon(h.contours[0], h.contours[1:]).buffer(0)
            if not poly.is_empty:
                hatches.append(poly.buffer(0.2))
    if not hatches:
        return None
    material = [f for f in faces if any(h.contains(f.representative_point()) for h in hatches)]
    return unary_union(material) if material else None


def _within_axis_span(poly, axis) -> bool:
    (x1, y1), (x2, y2) = axis
    dx, dy = x2 - x1, y2 - y1
    n = math.hypot(dx, dy)
    ux, uy = dx / n, dy / n
    ts = [((x - x1) * ux + (y - y1) * uy) for x, y in poly.exterior.coords]
    return min(ts) >= -1.0 and max(ts) <= n + 1.0


def _view_half(drawing, axis, side):
    """The faces of the outline on one side of the axis that are connected to
    the axis — one half of the view, without the other views of the sheet."""
    prims = []
    for e in drawing.entities:
        if isinstance(e, ir.Line) and e.style == ir.STYLE_MAIN:
            prims.append(Primitive("line", [e.p1, e.p2], 0.5, 0.0, p1=e.p1, p2=e.p2))
        elif isinstance(e, ir.Circle) and e.style == ir.STYLE_MAIN:
            prims.append(Primitive("circle", [], 0.5, 0.0, center=e.center, radius=e.radius))
        elif isinstance(e, ir.Arc) and e.style == ir.STYLE_MAIN:
            sweep = (e.end_angle - e.start_angle) % 360.0 or 360.0
            prims.append(Primitive("arc", [], 0.5, 0.0, center=e.center, radius=e.radius,
                                   start_angle=e.start_angle, end_angle=e.end_angle,
                                   sweep=sweep))
    prims.append(Primitive("line", list(axis), 0.25, 0.0, p1=axis[0], p2=axis[1]))
    half = _half_plane(axis, side)
    faces = [f for f in contour_faces(prims) if f.intersection(half).area >= 0.95 * f.area
             and _within_axis_span(f, axis)]
    if not faces:
        return None
    line = LineString(axis)
    component = [i for i, f in enumerate(faces) if f.distance(line) <= TOUCH]
    seen = set(component)
    while component:  # faces sharing a boundary with the ones already taken
        i = component.pop()
        for j, g in enumerate(faces):
            if j not in seen and faces[i].distance(g) <= TOUCH \
                    and faces[i].boundary.intersection(g.boundary).length > TOUCH:
                seen.add(j)
                component.append(j)
    if not seen:
        return None
    return [faces[i] for i in seen]


def _to_model(region, axis, side, scale) -> list[list[tuple[float, float]]]:
    (x1, y1), (x2, y2) = axis
    dx, dy = x2 - x1, y2 - y1
    n = math.hypot(dx, dy)
    ux, uy = dx / n, dy / n
    nx, ny = -uy * side, ux * side

    def model(p):
        vx, vy = p[0] - x1, p[1] - y1
        return ((vx * ux + vy * uy) / scale, max(0.0, (vx * nx + vy * ny) / scale))

    parts = _polygons(region)
    rings = []
    for part in parts:
        part = Polygon([model(p) for p in part.exterior.coords],
                       [[model(p) for p in hole.coords] for hole in part.interiors])
        for ring in [part.exterior] + list(part.interiors):
            pts = [(round(x, 4), round(y, 4)) for x, y in ring.coords]
            if len(pts) >= 4:
                rings.append(pts)
    return rings


def _polygons(geom) -> list[Polygon]:
    if geom.geom_type == "Polygon":
        return [geom] if geom.area > 1e-9 else []
    return [p for g in getattr(geom, "geoms", []) for p in _polygons(g)]


def bounding_box(rings) -> Polygon:
    xs = [x for r in rings for x, _ in r]
    ys = [y for r in rings for _, y in r]
    return box(min(xs), min(ys), max(xs), max(ys))


def profile_segments(profile: RevolveProfile, radii=()) -> list[list[tuple]]:
    """Each loop as sketch segments in model mm: ("line", p1, p2) or
    ("arc", center, r, a1, a2), arcs counter-clockwise from a1 to a2 (degrees).

    Lines and arcs are recognised on the sheet geometry (where the fitting
    tolerances belong) and then moved to model mm, so fillets come back as
    true arcs with their exact radii; ends are joined exactly. The profile
    starts at x = 0; faces and cylinders are put on a GRID mm grid, fillets
    get the radius written on the drawing (``radii``, model mm) and are made
    tangent to their lines again."""
    from ..geometry.chains import Chain
    from ..geometry.segmentation import segment_chain

    (x1, y1), (x2, y2) = profile.axis
    n = math.hypot(x2 - x1, y2 - y1)
    ux, uy = (x2 - x1) / n, (y2 - y1) / n
    nx, ny = -uy * profile.side, ux * profile.side
    k = profile.scale

    def model(p):
        vx, vy = p[0] - x1, p[1] - y1
        return ((vx * ux + vy * uy) / k, max(0.0, (vx * nx + vy * ny) / k))

    mirrored = ux * ny - uy * nx < 0  # the mapping reverses the direction of arcs

    def model_angle(c, a):
        p = (c[0] + math.cos(math.radians(a)), c[1] + math.sin(math.radians(a)))
        q, cm = model(p), model(c)
        return math.degrees(math.atan2(q[1] - cm[1], q[0] - cm[0])) % 360.0

    out = []
    for ring in profile.sheet_rings:
        segs = []
        for p in segment_chain(Chain(list(ring), 0.5, True), smooth=False):
            if p.kind == "line":
                segs.append(["line", model(p.p1), model(p.p2)])
            else:
                a1, a2 = (0.0, 360.0) if p.kind == "circle" else (p.start_angle, p.end_angle)
                b1, b2 = model_angle(p.center, a1), model_angle(p.center, a2)
                if mirrored:
                    b1, b2 = b2, b1
                segs.append(["arc", model(p.center), p.radius / k, b1, b2])
        out.append(segs)
    if out:
        x0 = min(min(_seg_ends(sg)[0][0], _seg_ends(sg)[1][0]) for loop in out for sg in loop)
        x0 = round(x0 / GRID) * GRID  # whole steps, so the grid stays the drawing's
        for loop in out:
            for sg in loop:
                if sg[0] == "line":
                    sg[1], sg[2] = (sg[1][0] - x0, sg[1][1]), (sg[2][0] - x0, sg[2][1])
                else:
                    sg[1] = (sg[1][0] - x0, sg[1][1])
    return [[tuple(sg) for sg in _join_ends(_refillet(_straighten(loop), radii))]
            for loop in out]


STRAIGHT = 0.02  # model mm
GRID = 0.05  # model mm: faces and cylinders of a turned part sit on it
SNAP = 0.015  # model mm a coordinate may be moved onto the grid


def _straighten(segs):
    """Lines within STRAIGHT of horizontal/vertical become exactly so (the
    drawing's geometry carries a few micrometres of noise); the neighbours
    follow the moved ends."""
    for s in segs:
        if s[0] != "line":
            continue
        (x1, y1), (x2, y2) = s[1], s[2]
        if abs(y2 - y1) <= STRAIGHT and abs(x2 - x1) > STRAIGHT:
            y = _snap((y1 + y2) / 2)
            s[1], s[2] = (x1, y), (x2, y)
        elif abs(x2 - x1) <= STRAIGHT and abs(y2 - y1) > STRAIGHT:
            x = _snap((x1 + x2) / 2)
            s[1], s[2] = (x, y1), (x, y2)
    # line–line joints: both ends to the intersection of the two lines
    n = len(segs)
    for i in range(n):
        a, b = segs[i], segs[(i + 1) % n]
        if a[0] == "line" and b[0] == "line":
            p = _cross(a[1], a[2], b[1], b[2])
            if p is not None and math.dist(p, a[2]) <= 0.05 and math.dist(p, b[1]) <= 0.05:
                a[2] = b[1] = p
    return segs


def _snap(v: float) -> float:
    g = round(v / GRID) * GRID
    return round(g, 6) if abs(g - v) <= SNAP else v


def _snap_radius(r: float, radii) -> float:
    """The radius written on the drawing when the fitted one is close to it,
    else the fitted one on the grid when it is close to that."""
    near = [q for q in radii if abs(q - r) <= 0.25 * q]
    if near:
        return min(near, key=lambda q: abs(q - r))
    return _snap(r)


def _refillet(segs, radii=()):
    """An arc between two lines is a fillet: rebuilt tangent to both lines
    with its exact radius, the lines trimmed to the tangent points. The
    fitted arc ends are a few micrometres off, which left the neighbouring
    lines slanted after the ends were joined."""
    n = len(segs)
    for i in range(n):
        arc, a, b = segs[i], segs[i - 1], segs[(i + 1) % n]
        if arc[0] != "arc" or a[0] != "line" or b[0] != "line" or n < 3:
            continue
        c, r = arc[1], _snap_radius(arc[2], radii)
        ia = _near_end(a, _seg_ends(arc))
        ib = _near_end(b, _seg_ends(arc))
        center = _fillet_center(a, b, c, r)
        if center is None or math.dist(center, c) > max(0.1, r):
            continue
        ta, tb = _foot(center, a), _foot(center, b)
        s1, s2 = _seg_ends(arc)
        first_on_a = math.dist(s1, a[ia]) <= math.dist(s2, a[ia])
        p1, p2 = (ta, tb) if first_on_a else (tb, ta)
        a1 = math.degrees(math.atan2(p1[1] - center[1], p1[0] - center[0])) % 360.0
        a2 = math.degrees(math.atan2(p2[1] - center[1], p2[0] - center[0])) % 360.0
        arc[1], arc[2], arc[3], arc[4] = center, r, a1, a2
        a[ia], b[ib] = ta, tb
    return segs


def _near_end(line, points) -> int:
    """Index (1 or 2) of the line end that touches one of ``points``."""
    return min((1, 2), key=lambda k: min(math.dist(line[k], q) for q in points))


def _fillet_center(a, b, c, r):
    """Centre at distance r from both lines, on the side of ``c``."""
    def offset(line):
        (x1, y1), (x2, y2) = line[1], line[2]
        n = math.hypot(x2 - x1, y2 - y1)
        if n < 1e-9:
            return None
        nx, ny = -(y2 - y1) / n, (x2 - x1) / n
        if (c[0] - x1) * nx + (c[1] - y1) * ny < 0:
            nx, ny = -nx, -ny
        return (x1 + nx * r, y1 + ny * r), (x2 + nx * r, y2 + ny * r)

    oa, ob = offset(a), offset(b)
    if oa is None or ob is None:
        return None
    return _cross(oa[0], oa[1], ob[0], ob[1])


def _foot(p, line):
    (x1, y1), (x2, y2) = line[1], line[2]
    dx, dy = x2 - x1, y2 - y1
    t = ((p[0] - x1) * dx + (p[1] - y1) * dy) / (dx * dx + dy * dy)
    return (x1 + t * dx, y1 + t * dy)


def _cross(p1, p2, p3, p4):
    d = (p1[0] - p2[0]) * (p3[1] - p4[1]) - (p1[1] - p2[1]) * (p3[0] - p4[0])
    if abs(d) < 1e-12:
        return None
    a = p1[0] * p2[1] - p1[1] * p2[0]
    b = p3[0] * p4[1] - p3[1] * p4[0]
    return ((a * (p3[0] - p4[0]) - (p1[0] - p2[0]) * b) / d,
            (a * (p3[1] - p4[1]) - (p1[1] - p2[1]) * b) / d)


def _seg_ends(s):
    if s[0] == "line":
        return s[1], s[2]
    c, r, a1, a2 = s[1:]
    return ((c[0] + r * math.cos(math.radians(a1)), c[1] + r * math.sin(math.radians(a1))),
            (c[0] + r * math.cos(math.radians(a2)), c[1] + r * math.sin(math.radians(a2))))


def _join_ends(segs):
    """Move line ends onto the neighbouring arc/line ends so the loop is closed
    exactly (KOMPAS needs a closed sketch for the rotation)."""
    for i, s in enumerate(segs):
        if s[0] != "line":
            continue
        for j in (i - 1, (i + 1) % len(segs)):
            other = _seg_ends(segs[j])
            for k in (1, 2):
                best = min(other, key=lambda q: math.dist(q, s[k]))
                if math.dist(best, s[k]) <= 0.05:
                    s[k] = best
    return segs


COARSE_PITCH = {3: 0.5, 4: 0.7, 5: 0.8, 6: 1.0, 8: 1.25, 10: 1.5, 12: 1.75, 14: 2.0, 16: 2.0,
                18: 2.5, 20: 2.5, 22: 2.5, 24: 3.0, 27: 3.0, 30: 3.5, 36: 4.0, 42: 4.5, 48: 5.0}


@dataclass
class ThreadSpec:
    diameter: float  # nominal, mm
    pitch: float
    x: float  # a point on the threaded cylinder: along the axis …
    radius: float  # … and its radius (model mm)
    outside: bool  # external thread (on a shaft) or internal (in a bore)

    def text(self) -> str:
        return f"M{self.diameter:g}×{self.pitch:g}".replace(".", ",") + \
            (" наружная" if self.outside else " внутренняя")


def thread_specs(drawing: ir.Drawing, profile: RevolveProfile, loops) -> list[ThreadSpec]:
    """Threads from the «M22×1,5» dimensions: the cylinder of the profile with
    that diameter (outer or bore)."""
    region = unary_union([Polygon(r) for r in profile.rings]) if profile.rings else None
    out = []
    for d in drawing.of_type(ir.Dimension):
        m = re.match(r"^M(\d+(?:[.,]\d+)?)(?:\s*[x×]\s*(\d+(?:[.,]\d+)?))?", d.text.strip())
        if not m:
            continue
        dia = float(m.group(1).replace(",", "."))
        pitch = float(m.group(2).replace(",", ".")) if m.group(2) \
            else COARSE_PITCH.get(int(round(dia)), 1.5)
        best = None
        for loop in loops:
            for s in loop:
                if s[0] != "line" or abs(s[1][1] - s[2][1]) > STRAIGHT:
                    continue
                r = s[1][1]
                # a thread is drawn at the major diameter outside, the minor in a bore
                if abs(2 * r - dia) <= max(0.25 * pitch * 2, 0.6):
                    length = abs(s[2][0] - s[1][0])
                    if best is None or length > best[0]:
                        best = (length, s)
        if best is None:
            continue
        s = best[1]
        x = (s[1][0] + s[2][0]) / 2
        r = s[1][1]
        outside = region is not None and region.contains(Point(x, r - 0.05))
        out.append(ThreadSpec(dia, pitch, x, r, outside))
    return out


def drawing_radii(drawing: ir.Drawing) -> list[float]:
    """Radii written on the drawing (R1, R0,5…), model mm: fillets get them exactly."""
    return sorted({d.nominal for d in drawing.of_type(ir.Dimension)
                   if d.dim_type == "radius" and d.nominal})
