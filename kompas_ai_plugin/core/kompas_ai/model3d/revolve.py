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
from dataclasses import dataclass

from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

from .. import ir
from ..geometry.segmentation import Primitive
from ..semantics.regions import contour_faces

MIN_AXIS = 20.0  # sheet mm
TOUCH = 0.05  # sheet mm
SIMPLIFY = 0.005  # model mm


@dataclass
class RevolveProfile:
    rings: list[list[tuple[float, float]]]  # closed loops, model mm (x along, y radius)
    axis: tuple[tuple[float, float], tuple[float, float]]  # sheet mm
    source: str  # "hatch" | "outline"
    area: float  # model mm²

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
            half = _view_half(drawing, axis, side)
            if half is None or half.is_empty:
                continue
            region, source = _hatched(drawing, half), "hatch"
            if region is None or region.is_empty:
                region, source = half, "outline"
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
    return RevolveProfile(rings, axis, source, region.area / scale ** 2)


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


def _hatched(drawing, half):
    """Hatched material inside the half view (a section)."""
    polys = []
    for h in drawing.of_type(ir.Hatch):
        if not h.contours:
            continue
        poly = Polygon(h.contours[0], h.contours[1:]).buffer(0)
        if not poly.is_empty and poly.intersection(half).area >= 0.5 * poly.area:
            polys.append(poly.intersection(half))
    return unary_union(polys) if polys else None


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
    return unary_union([faces[i] for i in seen])


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
        part = part.simplify(SIMPLIFY, preserve_topology=True)
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
