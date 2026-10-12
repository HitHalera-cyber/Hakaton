"""Closed regions of the main contour and the hatch boundaries.

KOMPAS (and most CAD systems) define a hatch by its boundary, so the hatch
strokes found in the PDF are mapped back to the faces of the main contour
they fill: the contour is noded and polygonised, every face containing hatch
strokes is hatched, and touching hatched faces form one hatch region.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import polygonize, unary_union

from ..geometry.segmentation import Primitive
from .hatch import HatchGroup

ARC_STEP_DEG = 3.0
MIN_FACE_AREA = 0.5  # mm²
SNAP_EXTENSION = 0.2  # mm


@dataclass
class HatchRegion:
    angle: float
    spacing: float
    polygon: Polygon
    line_count: int

    def contours(self) -> list[list[tuple[float, float]]]:
        rings = [self.polygon.exterior] + list(self.polygon.interiors)
        return [[(round(x, 4), round(y, 4)) for x, y in ring.coords] for ring in rings]


ON_CURVE = 0.15  # mm; a line end this close to a circle is attached to it


def _curve_points(p: Primitive, extra_angles=(), extend=(True, True)) -> list[tuple[float, float]]:
    if p.kind == "line":
        # Extend slightly so that lines ending a hair short of another line
        # still split the faces (polygonize needs exact intersections). An end
        # placed on a curve vertex is not extended: it already coincides.
        dx, dy = p.p2[0] - p.p1[0], p.p2[1] - p.p1[1]
        n = math.hypot(dx, dy) or 1.0
        e1 = SNAP_EXTENSION / n if extend[0] else 0.0
        e2 = SNAP_EXTENSION / n if extend[1] else 0.0
        return [(p.p1[0] - dx * e1, p.p1[1] - dy * e1), (p.p2[0] + dx * e2, p.p2[1] + dy * e2)]
    start, sweep = (0.0, 360.0) if p.kind == "circle" else (p.start_angle, p.sweep)
    steps = max(4, int(math.ceil(sweep / ARC_STEP_DEG)))
    # position along the curve → angle used for the vertex
    angles = {sweep * i / steps: start + sweep * i / steps for i in range(steps + 1)}
    # Line ends on the curve become curve vertices (the very same angle value,
    # see contour_faces), so lines touch the polygonal approximation exactly.
    for a in extra_angles:
        rel = (a - start) % 360.0
        if rel <= sweep + 1e-9:
            angles = {k: v for k, v in angles.items() if abs(k - rel) > 1e-6}
            angles[min(rel, sweep)] = a
    return [_on_curve(p, angles[k]) for k in sorted(angles)]


def _on_curve(c: Primitive, angle: float) -> tuple[float, float]:
    # One formula for curve vertices and the line ends snapped onto them, so
    # the coordinates are bit-identical and polygonize sees a shared node.
    return (c.center[0] + c.radius * math.cos(math.radians(angle)),
            c.center[1] + c.radius * math.sin(math.radians(angle)))


def contour_faces(contour: list[Primitive], grid: float | None = None) -> list[Polygon]:
    """Polygonise the contour into its smallest faces. ``grid``: coordinates
    are rounded to it first, so ends of two arcs a micrometre apart meet."""
    curves = [p for p in contour if p.kind in ("circle", "arc")]
    extra: dict[int, list[float]] = {id(c): [] for c in curves}
    lines = []
    for p in contour:
        if p.kind != "line":
            continue
        ends, free = [], []
        for end in (p.p1, p.p2):
            snapped = False
            for c in curves:
                if abs(math.dist(end, c.center) - c.radius) <= ON_CURVE:
                    a = math.degrees(math.atan2(end[1] - c.center[1], end[0] - c.center[0]))
                    if c.kind == "arc":
                        # An end a hair beyond the arc's end is on its end point;
                        # otherwise the ring does not close and no face is found.
                        rel = (a - c.start_angle) % 360.0
                        if rel > c.sweep:
                            a = c.start_angle + (c.sweep if rel - c.sweep < 360.0 - rel
                                                 else 0.0)
                    extra[id(c)].append(a)
                    end = _on_curve(c, a)
                    snapped = True
                    break
            ends.append(end)
            free.append(not snapped)
        moved = Primitive("line", ends, p.width, p.error, p1=ends[0], p2=ends[1])
        lines.append(LineString(_curve_points(moved, extend=tuple(free))))
    lines += [LineString(_curve_points(c, extra[id(c)])) for c in curves]
    if not lines:
        return []
    noded = unary_union(lines)
    if grid:
        from shapely import set_precision

        noded = unary_union(set_precision(noded, grid))
    return [f for f in polygonize(noded) if f.area >= MIN_FACE_AREA]


def hatch_regions(groups: list[HatchGroup], contour: list[Primitive]) -> tuple[list[HatchRegion], list[HatchGroup]]:
    """Return hatch regions and the groups whose boundary was not found."""
    faces = contour_faces(contour)
    # Merge groups with the same pattern: one pattern may be split into several
    # stroke groups by holes, but the region is decided by the faces.
    patterns: dict[tuple[int, float], list[HatchGroup]] = {}
    for g in groups:
        patterns.setdefault((round(g.angle), round(g.spacing, 1)), []).append(g)

    from shapely import STRtree

    tree = STRtree(faces) if faces else None  # an assembly has thousands of faces
    areas = [f.area for f in faces]
    regions, orphans = [], []
    for (_, _), pattern_groups in patterns.items():
        lines = [l for g in pattern_groups for l in g.lines]
        hit: dict[int, int] = {}
        strokes: dict[int, list] = {}
        missed = 0
        for line in lines:
            mid = Point((line.p1[0] + line.p2[0]) / 2, (line.p1[1] + line.p2[1]) / 2)
            idx = _smallest_face_containing(faces, mid, tree, areas)
            if idx is None:
                missed += 1
            else:
                hit[idx] = hit.get(idx, 0) + 1
                strokes.setdefault(idx, []).append(line)
        if not hit:
            orphans.extend(pattern_groups)
            continue
        angle = pattern_groups[0].angle
        spacing = sum(g.spacing for g in pattern_groups) / len(pattern_groups)
        # a face the strokes do not fill is not the hatch's outline (a contour
        # left open by the PDF joins it with its neighbours): the hatch is
        # where its strokes are
        pieces = []
        for i in hit:
            covered = sum(l.length for l in strokes[i]) * spacing
            if areas[i] <= OVERFILL * covered + 4 * spacing * spacing:
                pieces.append(faces[i])
            else:
                band = _stroke_area(strokes[i], spacing).intersection(faces[i])
                if not band.is_empty and band.area >= MIN_FACE_AREA:
                    pieces.append(band)
        merged = unary_union(pieces) if pieces else Polygon()
        if merged.is_empty:
            orphans.extend(pattern_groups)
            continue
        parts = [g for g in (list(merged.geoms) if hasattr(merged, "geoms") else [merged])
                 if g.geom_type == "Polygon" and g.area >= MIN_FACE_AREA]
        for part in parts:
            count = sum(n for i, n in hit.items() if part.buffer(0.01).intersects(faces[i]))
            regions.append(HatchRegion(angle, spacing, part, count))
    return regions, orphans


OVERFILL = 1.8  # a face this much bigger than its strokes cover is not filled by them


def _stroke_area(strokes, spacing: float):
    """The area hatched by parallel strokes: each run of neighbouring strokes
    (one stroke per row, rows a spacing apart) as the polygon through their
    ends — the true outline where the strokes end on it — half a spacing
    wider on either side."""
    ref = max(strokes, key=lambda l: l.length)
    ux, uy = ref.p2[0] - ref.p1[0], ref.p2[1] - ref.p1[1]
    n = math.hypot(ux, uy) or 1.0
    ux, uy = ux / n, uy / n
    rows = []
    for l in strokes:
        ts = sorted(((p[0] * ux + p[1] * uy) for p in (l.p1, l.p2)))
        s = ((l.p1[0] + l.p2[0]) / 2) * -uy + ((l.p1[1] + l.p2[1]) / 2) * ux
        rows.append((s, ts[0], ts[1]))
    rows.sort()
    runs: list[list] = []
    for row in rows:
        if runs and row[0] - runs[-1][-1][0] <= 1.6 * spacing \
                and min(row[2], runs[-1][-1][2]) > max(row[1], runs[-1][-1][1]):
            runs[-1].append(row)
        else:
            runs.append([row])

    def point(s, t):
        return (t * ux - s * uy, t * uy + s * ux)

    polys = []
    h = spacing / 2
    for run in runs:
        first, last = run[0], run[-1]
        left = [point(first[0] - h, first[1])] + [point(s, a) for s, a, _ in run] \
            + [point(last[0] + h, last[1])]
        right = [point(first[0] - h, first[2])] + [point(s, b) for s, _, b in run] \
            + [point(last[0] + h, last[2])]
        poly = Polygon(left + right[::-1]).buffer(0)
        if not poly.is_empty:
            polys.append(poly)
    return unary_union(polys) if polys else Polygon()


def _smallest_face_containing(faces: list[Polygon], point: Point, tree=None,
                              areas=None) -> int | None:
    best, best_area = None, math.inf
    near = tree.query(point) if tree is not None else range(len(faces))
    for i in sorted(int(k) for k in near):
        area = areas[i] if areas is not None else faces[i].area
        if area < best_area and faces[i].contains(point):
            best, best_area = i, area
    return best
