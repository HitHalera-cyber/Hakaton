"""The end view of a turned part: what the revolve alone does not give.

A fitting's flange is often not round: flats milled on its sides, notches,
a hexagon. The view along the axis (the one with the concentric circles of
the bores) shows that outline. Matched with the revolve profile — the
outline reaches as far from the centre along the section plane as the
profile's largest radius — it becomes a flange feature: the outline is
extruded over the flange's length along the axis and everything outside it
there is cut away.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from shapely.geometry import LineString, Point

from .. import ir
from .revolve import RevolveProfile, _snap

CONCENTRIC = 0.05  # sheet mm between centres of concentric circles
MATCH = 0.15  # model mm between the outline's reach and the profile radius
ROUND = 0.05  # model mm: an outline this close to a circle adds nothing


@dataclass
class FlangeSpec:
    """``loop``: the outline as sketch segments, model mm around the axis; the
    first coordinate lies along the section plane of the revolve profile,
    the second square to it. ``x0``–``x1``: the flange along the axis."""

    loop: list[tuple]
    x0: float
    x1: float
    radius: float  # how far the outline reaches from the axis
    inner: float = 0.0  # how close to the axis the outline comes (a flat)
    bore: float = 0.0  # radius of the hole through the flange (from the profile)

    def summary(self) -> str:
        kinds = {}
        for s in self.loop:
            kinds[s[0]] = kinds.get(s[0], 0) + 1
        return (f"Фланец по виду с торца: толщина {self.x1 - self.x0:.2f} мм, "
                f"контур {kinds.get('line', 0)} отрезков и {kinds.get('arc', 0)} дуг, "
                f"наибольший радиус {self.radius:.2f} мм")


def _centres(drawing) -> list[tuple[float, float]]:
    circles = [c for c in drawing.of_type(ir.Circle) if c.style == ir.STYLE_MAIN]
    out = []
    for c in circles:
        same = [d for d in circles if math.dist(d.center, c.center) <= CONCENTRIC]
        if len(same) >= 2 and not any(math.dist(c.center, o) <= CONCENTRIC for o in out):
            out.append(tuple(c.center))
    return out


def _reach(poly, c, direction) -> float:
    """How far the outline goes from c along ±direction (the smaller side)."""
    ux, uy = direction
    far = 10000.0
    reach = []
    for sgn in (1, -1):
        ray = LineString([c, (c[0] + sgn * ux * far, c[1] + sgn * uy * far)])
        cut = ray.intersection(poly.exterior)
        pts = [cut] if cut.geom_type == "Point" else list(getattr(cut, "geoms", []))
        d = [math.dist(c, (p.x, p.y)) for p in pts if p.geom_type == "Point"]
        reach.append(max(d) if d else 0.0)
    return min(reach)


def find_flange(drawing: ir.Drawing, profile: RevolveProfile, loops) -> FlangeSpec | None:
    from shapely.geometry import Polygon

    from ..geometry.ellipses import _loops, _samples

    k = profile.scale
    r_max = max(max(s[1][1], s[2][1]) if s[0] == "line" else s[1][1] + s[2]
                for loop in loops for s in loop)
    # the flange: where the profile runs at its largest radius
    xs = [x for loop in loops for s in loop if s[0] == "line"
          and abs(s[1][1] - r_max) <= 0.05 and abs(s[2][1] - r_max) <= 0.05
          for x in (s[1][0], s[2][0])]
    if not xs:
        return None
    x0, x1 = min(xs), max(xs)
    # the section plane runs along the profile's axis on the sheet: the same
    # direction in the end view when the views are projected (ГОСТ 2.305)
    (ax, ay), (bx, by) = profile.axis
    n = math.hypot(bx - ax, by - ay)
    along = ((bx - ax) / n, (by - ay) / n)
    across = (-along[1], along[0])
    pieces = [e for e in drawing.of_type(ir.Line) + drawing.of_type(ir.Arc)
              if e.style == ir.STYLE_MAIN]
    rings = []
    for loop in _loops(pieces):
        poly = Polygon(_ring(loop, _samples)).buffer(0)
        if poly.area > 0:
            rings.append((poly, loop))
    for c in _centres(drawing):
        around = [(poly, loop) for poly, loop in rings if poly.contains(Point(c))]
        if not around:
            continue
        outline, pieces_loop = max(around, key=lambda r: r[0].area)
        for u_dir, v_dir in ((across, along), (along, across)):
            if abs(_reach(outline, c, u_dir) / k - r_max) > MATCH:
                continue
            ring = list(outline.exterior.coords)
            dists = [math.dist(c, p) / k for p in ring]
            if max(dists) - min(dists) <= ROUND:
                return None  # round: the revolve is the whole flange

            def model(p):
                dx, dy = p[0] - c[0], p[1] - c[1]
                return ((dx * u_dir[0] + dy * u_dir[1]) / k, (dx * v_dir[0] + dy * v_dir[1]) / k)

            mirrored = u_dir[0] * v_dir[1] - u_dir[1] * v_dir[0] < 0
            segs = []
            for e in pieces_loop:
                if isinstance(e, ir.Line):
                    segs.append(["line", model(e.p1), model(e.p2)])
                else:
                    b1, b2 = _angle(model, e.center, e.start_angle), _angle(model, e.center, e.end_angle)
                    if mirrored:
                        b1, b2 = b2, b1
                    segs.append(["arc", model(e.center), e.radius / k, b1, b2])
            for sg in segs:  # centres and radii on the drawing's grid
                if sg[0] == "arc":
                    sg[1] = (_snap(sg[1][0]), _snap(sg[1][1]))
                    sg[2] = _snap(sg[2])
                else:
                    sg[1] = (_snap(sg[1][0]), _snap(sg[1][1]))
                    sg[2] = (_snap(sg[2][0]), _snap(sg[2][1]))
            return FlangeSpec([tuple(s) for s in close_loop(segs)], x0, x1, max(dists), min(dists),
                              _bore(loops, x0, x1))
    return None


def _ring(loop, samples):
    """The points of the loop in order (each piece turned to follow the last)."""
    pts = []
    for e in loop:
        q = [tuple(p) for p in samples([e])]
        if pts and math.dist(pts[-1], q[-1]) < math.dist(pts[-1], q[0]):
            q.reverse()
        elif not pts and len(loop) > 1:
            nxt = [tuple(p) for p in samples([loop[1]])]
            if min(math.dist(q[0], r) for r in (nxt[0], nxt[-1])) < \
                    min(math.dist(q[-1], r) for r in (nxt[0], nxt[-1])):
                q.reverse()
        pts += q
    return pts


def _bore(loops, x0, x1) -> float:
    """The smallest radius of the profile over x0–x1: the bore the flange
    extrusion must leave open (0 for a solid part)."""
    ys = []
    for loop in loops:
        for s in loop:
            if s[0] != "line":
                continue
            (ax, ay), (bx, by) = s[1], s[2]
            lo, hi = min(ax, bx), max(ax, bx)
            if hi >= x1 - 1e-6 and lo <= x0 + 1e-6 and abs(ay - by) < 1e-9:
                ys.append(ay)  # a line along the whole flange
    return min(ys) if ys else 0.0


def _ends_of(s):
    if s[0] == "line":
        return [s[1], s[2]]
    c, r = s[1], s[2]
    return [(c[0] + r * math.cos(math.radians(a)), c[1] + r * math.sin(math.radians(a)))
            for a in (s[3], s[4])]


def _meet(a, b, near):
    """The point where the curves of a and b cross, nearest ``near``."""
    def circle_line(c, r, p, q):
        dx, dy = q[0] - p[0], q[1] - p[1]
        fx, fy = p[0] - c[0], p[1] - c[1]
        A = dx * dx + dy * dy
        B = 2 * (fx * dx + fy * dy)
        C = fx * fx + fy * fy - r * r
        disc = B * B - 4 * A * C
        if A == 0 or disc < 0:
            return []
        out = []
        for sgn in (1, -1):
            t = (-B + sgn * math.sqrt(disc)) / (2 * A)
            out.append((p[0] + t * dx, p[1] + t * dy))
        return out

    if a[0] == "line" and b[0] == "line":
        from .revolve import _cross

        p = _cross(a[1], a[2], b[1], b[2])
        cands = [p] if p else []
    elif a[0] == "line" or b[0] == "line":
        line, arc = (a, b) if a[0] == "line" else (b, a)
        cands = circle_line(arc[1], arc[2], line[1], line[2])
    else:
        (x1, y1), r1 = a[1], a[2]
        (x2, y2), r2 = b[1], b[2]
        d = math.dist((x1, y1), (x2, y2))
        cands = []
        if 0 < d <= r1 + r2 and d >= abs(r1 - r2):
            l = (r1 * r1 - r2 * r2 + d * d) / (2 * d)
            h = math.sqrt(max(0.0, r1 * r1 - l * l))
            mx, my = x1 + l * (x2 - x1) / d, y1 + l * (y2 - y1) / d
            cands = [(mx + h * (y2 - y1) / d, my - h * (x2 - x1) / d),
                     (mx - h * (y2 - y1) / d, my + h * (x2 - x1) / d)]
    cands = [p for p in cands if math.dist(p, near) <= 0.2]
    return min(cands, key=lambda p: math.dist(p, near)) if cands else near


def close_loop(segs):
    """Ends of neighbouring segments onto the exact crossing of their curves,
    so the sketch contour is closed (the drawing's ends are a few
    hundredths apart after the dimensions moved them)."""
    segs = [list(s) for s in segs]
    n = len(segs)
    for i in range(n):
        a, b = segs[i], segs[(i + 1) % n]
        ea, eb = _ends_of(a), _ends_of(b)
        ia, ib = min(((x, y) for x in (0, 1) for y in (0, 1)),
                     key=lambda xy: math.dist(ea[xy[0]], eb[xy[1]]))
        near = ((ea[ia][0] + eb[ib][0]) / 2, (ea[ia][1] + eb[ib][1]) / 2)
        p = _meet(a, b, near)
        for seg, idx in ((a, ia), (b, ib)):
            if seg[0] == "line":
                seg[1 + idx] = p
            else:
                seg[3 + idx] = math.degrees(math.atan2(p[1] - seg[1][1], p[0] - seg[1][0])) % 360.0
    return segs


def _angle(model, c, a):
    p = (c[0] + math.cos(math.radians(a)), c[1] + math.sin(math.radians(a)))
    q, cm = model(p), model(c)
    return math.degrees(math.atan2(q[1] - cm[1], q[0] - cm[0])) % 360.0


@dataclass
class FilletSpec:
    """A fillet made after the milling: the corner of the profile at (x, y)
    — an edge circle of radius y around the axis at x — rounded to radius."""

    x: float
    y: float
    radius: float


def fillets_after_milling(loops, flange: FlangeSpec, tol: float = 0.05):
    """Fillets of the profile at the flange faces that reach past the flats:
    revolved, they would stay as rings on the milled faces. They leave the
    profile (a sharp corner) and come back as fillet operations after the
    flange is cut. Returns (loops, fillets)."""
    from .revolve import _cross

    out_loops, fillets = [], []
    for loop in loops:
        segs = [list(s) for s in loop]
        n = len(segs)
        drop = []
        for i, s in enumerate(segs):
            a, b = segs[i - 1], segs[(i + 1) % n]
            if s[0] != "arc" or a[0] != "line" or b[0] != "line":
                continue
            ends = _ends_of(s)
            on_face = any(abs(p[0] - x) <= tol for p in ends for x in (flange.x0, flange.x1))
            if not on_face or max(p[1] for p in ends) <= flange.inner + tol:
                continue
            corner = _cross(a[1], a[2], b[1], b[2])
            if corner is None:
                continue
            for line in (a, b):  # the lines run on to the corner
                k = 1 if math.dist(line[1], corner) < math.dist(line[2], corner) else 2
                line[k] = corner
            drop.append(i)
            fillets.append(FilletSpec(corner[0], corner[1], s[2]))
        out_loops.append([tuple(s) for i, s in enumerate(segs) if i not in drop])
    return out_loops, fillets
