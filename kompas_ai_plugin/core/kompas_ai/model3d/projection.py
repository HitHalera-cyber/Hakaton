"""Views of a part computed from its triangle mesh (STL), not by KOMPAS.

KOMPAS' own linked views of a model need the projection names, the view
parameters and a rebuild to come out right, and on some installations they
stay empty frames. The part's mesh (KOMPAS saves it as STL) is enough to
draw the views ourselves:

  * edges: the sharp edges of the mesh (faces meeting at a real angle) and,
    for each view, the outline of curved faces (where the surface turns
    away from the viewer);
  * visibility: a depth buffer of the mesh per view; an edge is hidden
    where something lies in front of it;
  * the pieces are traced into lines, arcs and circles like the strokes of
    a PDF and placed on a sheet by ГОСТ 2.305 (front view, top view under
    it, left view to its right, isometry in the free corner).

The result is a plain drawing (not linked to the model).
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .. import ir
from ..geometry.chains import build_chains
from ..geometry.segmentation import merge_cocircular, segment_chain, snap_concentric
from ..pdf.vector_extractor import RawSegment

FEATURE = 30.0  # deg: faces meeting at a sharper angle make an edge
GRID = 1000  # depth-buffer pixels along the larger side of a view
VISIBLE, HIDDEN = 0.5, 0.35  # stroke widths the tracer keeps apart
FLAT_ARC = 1000.0  # sheet mm: an "arc" of a bigger radius is a straight edge

# view → (right, up, towards the viewer) in model axes; KOMPAS: Y up, Z to the viewer
VIEWS = {
    "Спереди": ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
    "Сверху": ((1, 0, 0), (0, 0, -1), (0, 1, 0)),
    "Слева": ((0, 0, 1), (0, 1, 0), (-1, 0, 0)),
}


def read_stl(path: str | Path) -> np.ndarray:
    """Triangles (n, 3, 3) of a binary or text STL file."""
    data = Path(path).read_bytes()
    if len(data) >= 84:
        n = struct.unpack_from("<I", data, 80)[0]
        if 84 + 50 * n == len(data):
            rec = np.frombuffer(data, dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)),
                                                      ("a", "<u2")]), count=n, offset=84)
            return rec["v"].astype(float)
    text = data.decode("latin-1")
    nums = [float(v) for line in text.splitlines()
            for parts in [line.split()] if parts[:1] == ["vertex"] for v in parts[1:4]]
    if not nums or len(nums) % 9:
        raise ValueError("файл STL не прочитан")
    return np.array(nums, dtype=float).reshape(-1, 3, 3)


@dataclass
class Mesh:
    vertices: np.ndarray  # (m, 3)
    faces: np.ndarray  # (n, 3) vertex indices
    normals: np.ndarray  # (n, 3) unit
    edges: np.ndarray  # (k, 2) vertex indices
    edge_faces: list = field(default_factory=list)  # per edge: the faces on it

    @property
    def lo(self):
        return self.vertices.min(axis=0)

    @property
    def hi(self):
        return self.vertices.max(axis=0)


def build_mesh(triangles: np.ndarray) -> Mesh:
    """Shared vertices (welded), face normals, the edges with their faces."""
    tri = np.asarray(triangles, dtype=float).reshape(-1, 3, 3)
    size = float(np.ptp(tri.reshape(-1, 3), axis=0).max()) or 1.0
    key = np.round(tri.reshape(-1, 3) / (size * 1e-6)).astype(np.int64)
    uniq, inverse = np.unique(key, axis=0, return_inverse=True)
    verts = np.zeros((len(uniq), 3))
    np.add.at(verts, inverse.ravel(), tri.reshape(-1, 3))
    verts /= np.bincount(inverse.ravel(), minlength=len(uniq))[:, None]
    faces = inverse.reshape(-1, 3)
    good = (faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]) & (faces[:, 0] != faces[:, 2])
    faces = faces[good]
    a, b, c = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
    n = np.cross(b - a, c - a)
    length = np.linalg.norm(n, axis=1)
    keep = length > 1e-12 * size * size
    faces, n, length = faces[keep], n[keep], length[keep]
    normals = n / length[:, None]
    pairs = np.sort(np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]), axis=1)
    owner = np.tile(np.arange(len(faces)), 3)
    edges, inv = np.unique(pairs, axis=0, return_inverse=True)
    edge_faces: list[list[int]] = [[] for _ in range(len(edges))]
    for e, f in zip(inv.ravel(), owner):
        edge_faces[e].append(int(f))
    return Mesh(verts, faces, normals, edges, edge_faces)


def _sharp(mesh: Mesh) -> np.ndarray:
    """Edges where faces meet at more than FEATURE degrees, or open edges."""
    cos = math.cos(math.radians(FEATURE))
    out = np.zeros(len(mesh.edges), dtype=bool)
    for i, fs in enumerate(mesh.edge_faces):
        if len(fs) != 2:
            out[i] = True
        else:
            # (abs: a face wound the wrong way round is no edge)
            out[i] = abs(float(mesh.normals[fs[0]] @ mesh.normals[fs[1]])) < cos
    return out


def _depth_buffer(uv: np.ndarray, w: np.ndarray, faces: np.ndarray, lo, px: float, shape):
    """The nearest depth (largest w) of the mesh at each pixel centre."""
    buf = np.full(shape, -np.inf)
    H, W = shape
    P = (uv[faces] - lo) / px - 0.5  # (n, 3, 2) pixel coordinates
    x0s = np.clip(np.floor(P[:, :, 0].min(axis=1)), 0, None).astype(int)
    x1s = np.clip(np.ceil(P[:, :, 0].max(axis=1)), None, W - 1).astype(int)
    y0s = np.clip(np.floor(P[:, :, 1].min(axis=1)), 0, None).astype(int)
    y1s = np.clip(np.ceil(P[:, :, 1].max(axis=1)), None, H - 1).astype(int)
    det = (P[:, 1, 1] - P[:, 2, 1]) * (P[:, 0, 0] - P[:, 2, 0]) \
        + (P[:, 2, 0] - P[:, 1, 0]) * (P[:, 0, 1] - P[:, 2, 1])
    W3 = w[faces]
    for i in np.nonzero((np.abs(det) > 1e-12) & (x1s >= x0s) & (y1s >= y0s))[0]:
        (ax, ay), (bx, by), (cx, cy) = P[i]
        x0, x1, y0, y1 = x0s[i], x1s[i], y0s[i], y1s[i]
        xs = np.arange(x0, x1 + 1)[None, :] - cx
        ys = np.arange(y0, y1 + 1)[:, None] - cy
        l1 = ((by - cy) * xs + (cx - bx) * ys) / det[i]
        l2 = ((cy - ay) * xs + (ax - cx) * ys) / det[i]
        l3 = 1.0 - l1 - l2
        inside = (l1 >= -1e-9) & (l2 >= -1e-9) & (l3 >= -1e-9)
        z = np.where(inside, l1 * W3[i, 0] + l2 * W3[i, 1] + l3 * W3[i, 2], -np.inf)
        region = buf[y0:y1 + 1, x0:x1 + 1]
        np.maximum(region, z, out=region)
    return buf


@dataclass
class View:
    name: str
    lines: list[tuple]  # ((u1, v1), (u2, v2), visible)
    lo: tuple[float, float]
    hi: tuple[float, float]


def project(mesh: Mesh, right, up, toward, name: str = "", hidden: bool = True) -> View:
    """The visible (and hidden) edges of the mesh seen along -``toward``."""
    R = np.array([right, up, toward], dtype=float)
    R /= np.linalg.norm(R, axis=1)[:, None]
    p = mesh.vertices @ R.T
    uv, w = p[:, :2], p[:, 2]
    lo, hi = uv.min(axis=0), uv.max(axis=0)
    size = float((hi - lo).max()) or 1.0
    px = size / GRID
    lo_buf = lo - 2 * px
    shape = (int((hi[1] - lo[1]) / px) + 5, int((hi[0] - lo[0]) / px) + 5)
    buf = _depth_buffer(uv, w, mesh.faces, lo_buf, px, shape)
    # the 3×3 nearest-free depth: an edge's own faces cover one side of it only
    pad = np.pad(buf, 1, constant_values=-np.inf)
    least = np.min([pad[dy:dy + shape[0], dx:dx + shape[1]]
                    for dy in range(3) for dx in range(3)], axis=0)
    eps = 3 * px + 1e-4 * size

    facing = mesh.normals @ R[2]
    sharp = _sharp(mesh)
    lines = []
    for i, (a, b) in enumerate(mesh.edges):
        fs = mesh.edge_faces[i]
        outline = len(fs) == 2 and facing[fs[0]] * facing[fs[1]] < 0 \
            and min(abs(facing[fs[0]]), abs(facing[fs[1]])) > 1e-9 \
            and abs(float(mesh.normals[fs[0]] @ mesh.normals[fs[1]])) < 1 - 1e-6
        if not (sharp[i] or outline):
            continue
        if len(fs) == 2 and sharp[i] and not outline and \
                abs(facing[fs[0]]) < 1e-6 and abs(facing[fs[1]]) < 1e-6:
            continue  # between two faces seen edge-on: a point of their line
        pa, pb = uv[a], uv[b]
        steps = max(1, int(math.ceil(float(np.linalg.norm(pb - pa)) / px)))
        t = (np.arange(steps + 1) + 0.0) / steps
        pts = pa[None, :] + (pb - pa)[None, :] * t[:, None]
        depth = w[a] + (w[b] - w[a]) * t
        ix = np.clip(((pts[:, 0] - lo_buf[0]) / px).astype(int), 0, shape[1] - 1)
        iy = np.clip(((pts[:, 1] - lo_buf[1]) / px).astype(int), 0, shape[0] - 1)
        seen = least[iy, ix] <= depth + eps
        # runs of one kind; a lone sample of the other kind is noise
        if len(seen) > 2:
            lone = (seen[1:-1] != seen[:-2]) & (seen[1:-1] != seen[2:])
            seen[1:-1][lone] = seen[:-2][lone]
        start = 0
        for k in range(1, len(seen) + 1):
            if k == len(seen) or seen[k] != seen[start]:
                if seen[start] or hidden:
                    q0, q1 = pts[start], pts[min(k, len(seen) - 1)]
                    if float(np.linalg.norm(q1 - q0)) > 1e-9:
                        lines.append((tuple(q0), tuple(q1), bool(seen[start])))
                start = k
    return View(name, lines, (float(lo[0]), float(lo[1])), (float(hi[0]), float(hi[1])))


def _unique(lines):
    """Edges that land on one another (the near and far edge of a step seen
    end-on) drawn once; visible wins."""
    best: dict[tuple, tuple] = {}
    for a, b, v in lines:
        ka, kb = tuple(round(c, 4) for c in a), tuple(round(c, 4) for c in b)
        key = (ka, kb) if ka <= kb else (kb, ka)
        if key not in best or (v and not best[key][2]):
            best[key] = (a, b, v)
    return list(best.values())


def _merge_collinear(lines):
    """Pieces of one straight line joined where they overlap or touch: a
    circle seen edge-on is a pile of chords on one line, and a bore's end
    lies on the end face's line."""
    groups: dict[tuple, list] = {}
    for a, b, v in lines:
        d = (b[0] - a[0], b[1] - a[1])
        L = math.hypot(*d)
        if L < 1e-9:
            continue
        ang = math.atan2(d[1], d[0]) % math.pi
        if math.pi - ang < 5e-5:  # 179.99° is 0°: one direction, one sign of the offset
            ang = 0.0
        u = (math.cos(ang), math.sin(ang))
        off = -a[0] * u[1] + a[1] * u[0]
        key = (round(ang, 4), round(off, 3), v)
        t0, t1 = sorted((a[0] * u[0] + a[1] * u[1], b[0] * u[0] + b[1] * u[1]))
        groups.setdefault(key, []).append((t0, t1, u, off))
    out = []
    for (_, _, v), items in groups.items():
        items.sort()
        u, off = items[0][2], items[0][3]
        n = (-u[1], u[0])
        cur = list(items[0][:2])
        for t0, t1, _, _ in items[1:] + [(math.inf, math.inf, u, off)]:
            if t0 <= cur[1] + 1e-6:
                cur[1] = max(cur[1], t1)
                continue
            out.append(((u[0] * cur[0] + n[0] * off, u[1] * cur[0] + n[1] * off),
                        (u[0] * cur[1] + n[0] * off, u[1] * cur[1] + n[1] * off), v))
            cur = [t0, t1]
    return out


def _drop_hidden_behind(lines):
    """A hidden edge right behind a visible one is not drawn."""
    lines = _merge_collinear(_unique(lines))
    vis = [(np.array(a), np.array(b)) for a, b, v in lines if v]
    cell = 2.0
    grid: dict[tuple[int, int], list] = {}
    for a, b in vis:
        for cx in range(int(math.floor(min(a[0], b[0]) / cell)), int(math.floor(max(a[0], b[0]) / cell)) + 1):
            for cy in range(int(math.floor(min(a[1], b[1]) / cell)),
                            int(math.floor(max(a[1], b[1]) / cell)) + 1):
                grid.setdefault((cx, cy), []).append((a, b))

    def covered(p):
        for a, b in grid.get((int(math.floor(p[0] / cell)), int(math.floor(p[1] / cell))), ()):
            d = b - a
            L2 = float(d @ d)
            t = 0.0 if L2 == 0 else max(0.0, min(1.0, float((p - a) @ d) / L2))
            if float(np.linalg.norm(p - (a + d * t))) < 0.02:
                return True
        return False

    out = []
    for a, b, v in lines:
        if not v:
            pa, pb = np.array(a), np.array(b)
            if all(covered(pa + (pb - pa) * t) for t in (0.0, 0.25, 0.5, 0.75, 1.0)):
                continue
        out.append((a, b, v))
    return out


def trace(view: View, scale: float, at, start_id: int = 1) -> list[ir.Entity]:
    """The view's edges placed on the sheet (centre of the view at ``at``,
    ``scale`` sheet/model) as lines, arcs and circles."""
    cu, cv = (view.lo[0] + view.hi[0]) / 2, (view.lo[1] + view.hi[1]) / 2

    def place(p):
        return (at[0] + (p[0] - cu) * scale, at[1] + (p[1] - cv) * scale)

    segs = [RawSegment(place(a), place(b), VISIBLE if v else HIDDEN)
            for a, b, v in _drop_hidden_behind(view.lines)]
    segs = [s for s in segs if s.length > 1e-6]
    prims = snap_concentric(merge_cocircular(
        [p for chain in build_chains(segs, tol=0.01) for p in segment_chain(chain, smooth=False)]))
    out: list[ir.Entity] = []
    n = start_id
    for p in prims:
        style = ir.STYLE_MAIN if p.width >= VISIBLE - 1e-6 else ir.STYLE_DASHED
        if p.kind == "line":
            if math.dist(p.p1, p.p2) < 0.2:
                continue  # a sliver left where edges nearly meet
            out.append(ir.Line(f"L{n}", p1=p.p1, p2=p.p2, style=style))
        elif p.kind == "circle":
            out.append(ir.Circle(f"C{n}", center=p.center, radius=p.radius, style=style))
        elif p.radius > FLAT_ARC:  # nearly straight chords: a line, not an arc off the sheet
            out.append(ir.Line(f"L{n}", p1=tuple(p.points[0]), p2=tuple(p.points[-1]),
                               style=style))
        else:
            out.append(ir.Arc(f"A{n}", center=p.center, radius=p.radius,
                              start_angle=p.start_angle, end_angle=p.end_angle, style=style))
        n += 1
    return out


def _isometry():
    w = np.array([1.0, 1.0, 1.0]) / math.sqrt(3)
    up = np.array([0.0, 1.0, 0.0])
    v = up - (up @ w) * w
    v /= np.linalg.norm(v)
    u = np.cross(v, w)
    return tuple(u), tuple(v), tuple(w)


REVOLVED = 0.7  # of the surface turned around an axis: a body of revolution


def revolve_axis(mesh: Mesh):
    """(direction, point) of the axis the part is turned around — X, Y or Z,
    whichever most of its surface is turned around (a flange's flats and
    holes aside) — or None."""
    v = mesh.vertices
    size = float(np.ptp(v, axis=0).max()) or 1.0
    tri = mesh.vertices[mesh.faces]
    centres = tri.mean(axis=1)
    area = np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1) / 2
    best = None
    for k in range(3):
        a = np.zeros(3)
        a[k] = 1.0
        others = [i for i in range(3) if i != k]
        if abs(np.ptp(v[:, others[0]]) - np.ptp(v[:, others[1]])) > 0.05 * size:
            continue  # not round across this axis
        c = (v.min(axis=0) + v.max(axis=0)) / 2
        radial = centres - c
        radial[:, k] = 0.0
        rn = np.linalg.norm(radial, axis=1)
        ok = rn > 1e-6 * size
        around = np.abs(np.cross(radial[ok] / rn[ok, None], mesh.normals[ok]) @ a)
        share = float(area[ok][around < 0.05].sum() / (area[ok].sum() or 1.0))
        if share >= REVOLVED and (best is None or share > best[0]):
            best = (share, a, c)
    return (best[1], best[2]) if best else None


def axis_of_revolution(mesh: Mesh) -> tuple[float, float] | None:
    """(y, z) of the axis when the part is turned around X (see revolve_axis)."""
    found = revolve_axis(mesh)
    if found is None or abs(found[0][0]) < 0.5:
        return None
    return float(found[1][1]), float(found[1][2])


def _clip_behind(tri: np.ndarray, c, w) -> np.ndarray:
    """The triangles (pieces) behind the plane through ``c`` facing ``w``."""
    d = (tri - c) @ w  # (n, 3) signed distances
    behind = (d <= 1e-9).all(axis=1)
    out = list(tri[behind])
    for t, dd in zip(tri[~behind], d[~behind]):
        if (dd > 1e-9).all():
            continue
        poly = []
        for i in range(3):
            p, q, dp, dq = t[i], t[(i + 1) % 3], dd[i], dd[(i + 1) % 3]
            if dp <= 1e-9:
                poly.append(p)
            if (dp <= 1e-9) != (dq <= 1e-9):
                poly.append(p + (q - p) * (dp / (dp - dq)))
        for i in range(1, len(poly) - 1):
            out.append(np.array([poly[0], poly[i], poly[i + 1]]))
    return np.array(out) if out else np.zeros((0, 3, 3))


def _section(tri: np.ndarray, c, R) -> list:
    """The cut faces of the part in the plane through ``c`` facing R[2], in
    the view's (right, up) coordinates: shapely polygons of material."""
    from shapely.geometry import LineString
    from shapely.ops import polygonize, unary_union

    w = R[2]
    # a hair off the plane: vertices lying on it would cut their edges twice
    d = (tri - c) @ w - 1e-6 * float(np.ptp(tri.reshape(-1, 3), axis=0).max() or 1.0)
    segs = []
    for t, dd in zip(tri, d):
        pts = []
        for i in range(3):
            p, q, dp, dq = t[i], t[(i + 1) % 3], dd[i], dd[(i + 1) % 3]
            if tuple(q) < tuple(p):  # one order per edge: its two faces cut it at one point
                p, q, dp, dq = q, p, dq, dp
            if (dp < 0) != (dq < 0) and abs(dp - dq) > 1e-12:
                pts.append(p + (q - p) * (dp / (dp - dq)))
        if len(pts) == 2:
            a, b = pts[0] @ R[:2].T, pts[1] @ R[:2].T
            if np.linalg.norm(a - b) > 1e-9:
                segs.append((tuple(a), tuple(b)))
    if not segs:
        return []
    lines = [LineString(sg) for sg in segs]
    faces = list(polygonize(unary_union(lines)))

    def inside(p) -> bool:  # ray to +right: odd crossings of the cut lines
        x, y = p.x, p.y
        n = 0
        for (x1, y1), (x2, y2) in segs:
            if (y1 > y) != (y2 > y):
                xc = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
                n += xc > x
        return n % 2 == 1

    return [f for f in faces if f.area > 1e-6 and inside(f.representative_point())]


def _revolve_drawing(mesh: Mesh, axis, view_scale, layout, notes):
    """A body of revolution as ГОСТ draws it: the main view a section along
    the axis (hatched, the axis horizontal), the view from the end on its
    right, the isometry below; no hidden lines."""
    a, c = axis
    # looking across the axis: the coordinate axis that shows more of the part
    cands = [np.eye(3)[k] for k in range(3) if abs(a[k]) < 0.5]
    v_ext = []
    for t in cands:
        up = np.cross(t, a)
        v_ext.append(float(np.ptp(mesh.vertices @ up)))
    t = cands[int(np.argmax(v_ext))]
    R_main = np.array([a, np.cross(t, a), t])
    R_end = np.array([t, np.cross(t, a), -a])
    length = float(np.ptp(mesh.vertices @ a))
    dia = max(v_ext)
    fmt, land, s, places = layout((length, dia, dia), view_scale)
    entities: list[ir.Entity] = []

    # the section: the half behind the cut, its edges seen; the cut hatched
    tri = mesh.vertices[mesh.faces]
    half = build_mesh(_clip_behind(tri, c, t))
    main = project(half, *R_main, name="Разрез", hidden=False)
    at = places["#Спереди"]
    entities += trace(main, s, at, start_id=1)
    cu, cv = (main.lo[0] + main.hi[0]) / 2, (main.lo[1] + main.hi[1]) / 2

    def place(p):
        return (at[0] + (p[0] - cu) * s, at[1] + (p[1] - cv) * s)

    cut = _section(tri, c, R_main)
    entities += _revolve_dims(cut, c @ R_main[1], place, s, len(entities) + 1)
    for k, poly in enumerate(cut):
        rings = [[place(q) for q in poly.exterior.coords]] + \
            [[place(q) for q in ring.coords] for ring in poly.interiors]
        entities.append(ir.Hatch(f"H{k + 1}", angle=45.0, spacing=2.0, contours=rings))
    # the axis, 5 mm past the part
    ax = c @ R_main[1]
    y = at[1] + (ax - cv) * s
    entities.append(ir.Line(f"L{len(entities) + 1}", p1=(place(main.lo)[0] - 5, y),
                            p2=(place(main.hi)[0] + 5, y), style=ir.STYLE_AXIAL))
    if cut:
        notes.append("Главный вид — разрез по оси (тело вращения), штриховка по сечению; "
                     "основные размеры (диаметры, длины ступеней, общая длина) проставлены по "
                     "модели — проверьте и добавьте остальные в КОМПАС")

    end = project(mesh, *R_end, name="Слева", hidden=False)
    entities += trace(end, s, places["#Слева"], start_id=len(entities) + 1)
    entities += _centre_marks(entities, s, len(entities) + 1)

    sizes = {0: (1189, 841), 1: (841, 594), 2: (594, 420), 3: (420, 297), 4: (297, 210)}
    W, H = sizes[fmt] if land else sizes[fmt][::-1]
    box = (30.0, W - 10.0, 65.0, at[1] - dia * s / 2 - 10.0)
    _isometry_into(mesh, entities, box, s, notes)
    return fmt, land, s, W, H, entities


def _main_direction(mesh: Mesh):
    """(right, up, toward) of the main view: looking along the axis the part
    shows its biggest outline across (X, Y or Z); up is Z, or Y looking down Z."""
    tri = mesh.vertices[mesh.faces]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])  # 2 × area along the normal
    shown = [float(np.abs(n[:, k]).sum()) for k in range(3)]
    k = int(np.argmax(shown))
    w = np.eye(3)[k]
    up = np.eye(3)[2] if k != 2 else np.eye(3)[1]
    return np.cross(up, w), up, w


def _cut_view(mesh: Mesh, R, c, s, at, start_id, name):
    """A section: the material behind the plane through ``c`` facing R[2] —
    its edges seen, its cut hatched — placed at ``at``."""
    tri = mesh.vertices[mesh.faces]
    half = build_mesh(_clip_behind(tri, c, R[2]))
    view = project(half, *R, name=name, hidden=False)
    out = trace(view, s, at, start_id=start_id)
    cu, cv = (view.lo[0] + view.hi[0]) / 2, (view.lo[1] + view.hi[1]) / 2

    def place(p):
        return (at[0] + (p[0] - cu) * s, at[1] + (p[1] - cv) * s)

    cut = _section(tri, c, R)
    for k, poly in enumerate(cut):
        rings = [[place(q) for q in poly.exterior.coords]] + \
            [[place(q) for q in ring.coords] for ring in poly.interiors]
        out.append(ir.Hatch(f"H{start_id}_{k + 1}", angle=45.0, spacing=2.0, contours=rings))
    return out, view, place, bool(cut)


def _prismatic_drawing(mesh: Mesh, view_scale, layout, notes):
    """A part that is no body of revolution: the main view where its outline
    is biggest; the left and the top views as sections А-А and Б-Б through
    the centre of the biggest hole of the main view (the bores and pockets
    show without hidden lines); the overall sizes and the holes' diameters;
    the isometry in the free corner. No hidden lines anywhere."""
    u, v, w = _main_direction(mesh)
    R_main = np.array([u, v, w])
    R_left = np.array([w, v, -u])
    R_top = np.array([u, -w, v])
    ext = [float(np.ptp(mesh.vertices @ d)) for d in (u, v, w)]
    # room kept for a further section and the isometry (the sheet one size up
    # rather than four views crammed)
    fmt, land, s, places = layout(tuple(1.35 * e for e in ext), view_scale)
    entities: list[ir.Entity] = []
    main = project(mesh, *R_main, name="Главный", hidden=False)
    at = places["#Спереди"]
    entities += trace(main, s, at, start_id=1)
    cu, cv = (main.lo[0] + main.hi[0]) / 2, (main.lo[1] + main.hi[1]) / 2

    def place(p):
        return (at[0] + (p[0] - cu) * s, at[1] + (p[1] - cv) * s)

    # the cutting planes through the biggest hole seen in the main view
    circles = [e for e in entities if isinstance(e, ir.Circle)]
    centre3 = (mesh.lo + mesh.hi) / 2
    if circles:
        big = max(circles, key=lambda e: e.radius)
        pu = cu + (big.center[0] - at[0]) / s
        pv = cv + (big.center[1] - at[1]) / s
    else:
        pu, pv = cu, cv
    depth = float(centre3 @ w)
    c = u * pu + v * pv + w * depth
    letters = []
    for name, R, place_key, line in (("А", R_left, "#Слева", "u"), ("Б", R_top, "#Сверху", "v")):
        part, view, _, has_cut = _cut_view(mesh, R, c, s, places[place_key],
                                           len(entities) + 1, f"{name}-{name}")
        if not has_cut:
            view = project(mesh, *R, name=name, hidden=False)
            entities += trace(view, s, places[place_key], start_id=len(entities) + 1)
            continue
        entities += part
        letters.append(name)
        top = max(q[1] for e in part if isinstance(e, ir.Line) for q in (e.p1, e.p2))
        px = places[place_key][0]
        entities.append(ir.Text(f"T{name}", text=f"{name}-{name}", position=(px - 6, top + 5),
                                height=5.0))
        # the plane's trace on the main view: short thick strokes past the outline
        lo_m, hi_m = place(main.lo), place(main.hi)
        if line == "u":
            x = place((pu, pv))[0]
            ends = [((x, hi_m[1] + 3), (x, hi_m[1] + 11)), ((x, lo_m[1] - 3), (x, lo_m[1] - 11))]
            tags = [(x + 1.5, hi_m[1] + 9), (x + 1.5, lo_m[1] - 13)]
        else:
            y = place((pu, pv))[1]
            ends = [((lo_m[0] - 3, y), (lo_m[0] - 11, y)), ((hi_m[0] + 3, y), (hi_m[0] + 11, y))]
            tags = [(lo_m[0] - 11, y + 2), (hi_m[0] + 7, y + 2)]
        for k, (a, b) in enumerate(ends):
            entities.append(ir.Line(f"LS{name}{k}", p1=a, p2=b, style=ir.STYLE_MAIN))
            entities.append(ir.Text(f"TS{name}{k}", text=name, position=tags[k], height=5.0))
    sizes = {0: (1189, 841), 1: (841, 594), 2: (594, 420), 3: (420, 297), 4: (297, 210)}
    W, H = sizes[fmt] if land else sizes[fmt][::-1]
    (_, ly_), (tx, _) = places["#Слева"], places["#Сверху"]
    # the free parts of the sheet: right of the top view under the left one,
    # and left of the top view under the main one (above the title block)
    boxes = [(tx + ext[0] * s / 2 + 10.0, W - 10.0, 65.0, ly_ - ext[1] * s / 2 - 16.0),
             (30.0, tx - ext[0] * s / 2 - 10.0, 65.0, at[1] - ext[1] * s / 2 - 20.0)]
    boxes = [b for b in boxes if b[1] > b[0] and b[3] > b[2]]
    extra = _local_section(mesh, R_main, R_left, circles, (pu, pv), cu, cv, depth, s, place,
                           at, boxes, ext, entities)
    if extra:
        letters.append("В")
    if letters:
        notes.append("Вместо видов слева и сверху — разрезы " + ", ".join(
            f"{x}-{x}" for x in letters) + " через центр самого большого отверстия главного вида")
    notes.append("Невидимые линии не показаны — внутреннее устройство видно на разрезах")
    entities += _centre_marks(entities, s, len(entities) + 1)
    entities += _prismatic_dims(main, place, s, entities, len(entities) + 1)

    if boxes:  # the isometry into the biggest free part left
        _isometry_into(mesh, entities, max(boxes, key=lambda b: (b[1] - b[0]) * (b[3] - b[2])),
                       s, notes)
    return fmt, land, s, W, H, entities


def _local_section(mesh, R_main, R_left, circles, first, cu, cv, depth, s, place, at0, boxes,
                   ext, entities) -> bool:
    """Разрез В-В: a hole of the main view that А-А and Б-Б miss (a boss
    beside the body) cut along its axis, the part around it only, put under
    the main view where the sheet is free."""
    u, v, w = R_main
    pu, pv = first
    pick = None
    for e in sorted(circles, key=lambda e: -e.radius):
        qu = cu + (e.center[0] - at0[0]) / s
        qv = cv + (e.center[1] - at0[1]) / s
        r = e.radius / s
        if abs(qu - pu) > r + 1.0 and abs(qv - pv) > r + 1.0 and r > 2.0:
            pick = (qu, qv, r)
            break
    if pick is None:
        return False
    qu, qv, r = pick
    # around the hole: the boss and a little of what holds it
    reach = 1.6 * r + 5.0
    tri = mesh.vertices[mesh.faces]
    c = u * qu + v * qv + w * depth
    band = _clip_behind(tri, c + v * reach, v)
    band = _clip_behind(band, c - v * reach, -v)
    if not len(band):
        return False
    piece = build_mesh(band)
    width_w, height = ext[2] * s, 2 * reach * s
    box = next((b for b in boxes if b[1] - b[0] >= width_w + 10 and b[3] - b[2] >= height + 14),
               None)
    if box is None:
        return False
    boxes.remove(box)
    at = ((box[0] + box[1]) / 2, (box[2] + box[3]) / 2 - 3)
    view = project(piece, *R_left, name="В-В", hidden=False)
    entities += trace(view, s, at, start_id=len(entities) + 1)
    vu, vv = (view.lo[0] + view.hi[0]) / 2, (view.lo[1] + view.hi[1]) / 2
    from shapely.geometry import box as sbox


    window = sbox(-1e6, qv - reach, 1e6, qv + reach)
    cut = []
    for poly in _section(tri, c, R_left):
        part = poly.intersection(window)
        cut += [g for g in getattr(part, "geoms", [part]) if g.area > 1e-6]
    for k, poly in enumerate(cut):
        rings = [[(at[0] + (q[0] - vu) * s, at[1] + (q[1] - vv) * s) for q in ring.coords]
                 for ring in [poly.exterior] + list(poly.interiors)]
        entities.append(ir.Hatch(f"HV{k}", angle=45.0, spacing=2.0, contours=rings))
    top = at[1] + height / 2
    entities.append(ir.Text("TВ", text="В-В", position=(at[0] - 6, top + 5), height=5.0))
    x = place((qu, qv))[0]
    y_hi = place((qu, qv + r))[1] + 6
    y_lo = place((qu, qv - r))[1] - 6
    for k, (a, b, tag) in enumerate((((x, y_hi), (x, y_hi + 8), (x + 1.5, y_hi + 6)),
                                     ((x, y_lo), (x, y_lo - 8), (x + 1.5, y_lo - 10)))):
        entities.append(ir.Line(f"LSВ{k}", p1=a, p2=b, style=ir.STYLE_MAIN))
        entities.append(ir.Text(f"TSВ{k}", text="В", position=tag, height=5.0))
    return True


def _prismatic_dims(main: View, place, s: float, entities, start_id: int) -> list:
    """The overall width and height under and left of the main view, and the
    diameters of its round holes (each size once, biggest first)."""
    out = []
    n = start_id
    (x0, y0), (x1, y1) = place(main.lo), place(main.hi)
    w, h = round((main.hi[0] - main.lo[0]), 2), round((main.hi[1] - main.lo[1]), 2)
    out.append(ir.Dimension(f"D{n}", 0.9, ["по модели"], dim_type="linear", text=_num(w),
                            nominal=w, measured=round(x1 - x0, 4), p1=(x0, y0), p2=(x1, y0),
                            line_point=((x0 + x1) / 2, y0 - 12), orientation="horizontal"))
    out.append(ir.Dimension(f"D{n + 1}", 0.9, ["по модели"], dim_type="linear", text=_num(h),
                            nominal=h, measured=round(y1 - y0, 4), p1=(x0, y0), p2=(x0, y1),
                            line_point=(x0 - 12, (y0 + y1) / 2), orientation="vertical"))
    n += 2
    seen = set()
    holes = sorted((e for e in entities if isinstance(e, ir.Circle)
                    and x0 - 1 <= e.center[0] <= x1 + 1 and y0 - 1 <= e.center[1] <= y1 + 1),
                   key=lambda e: -e.radius)
    count: dict[float, int] = {}
    for e in holes:
        count[round(2 * e.radius / s, 2)] = count.get(round(2 * e.radius / s, 2), 0) + 1
    for e in holes:
        d = round(2 * e.radius / s, 2)
        if d in seen or len(seen) >= 6:
            continue
        seen.add(d)
        many = f"{count[d]} отв. " if count[d] > 1 else ""
        p = (e.center[0] + e.radius * math.cos(math.radians(45)),
             e.center[1] + e.radius * math.sin(math.radians(45)))
        out.append(ir.Dimension(f"D{n}", 0.9, ["по модели"], dim_type="diameter",
                                text=many + "Ø" + _num(d), nominal=d,
                                measured=round(2 * e.radius, 4),
                                p1=p, center=e.center, radius=e.radius))
        n += 1
    return out


def _num(v: float) -> str:
    text = f"{v:.2f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def _revolve_dims(cut, axis_v: float, place, s: float, start_id: int) -> list:
    """The main sizes of a body of revolution off its section: the diameters
    of the outer steps and of the bores (across the view, as on a turned
    part's drawing), the lengths of the steps under the view and the overall
    length. Model mm in, sheet mm out."""
    from shapely.geometry import Point

    outer: dict[float, tuple] = {}
    inner: dict[float, tuple] = {}
    steps: set[float] = set()
    spans: list[tuple[float, float, float]] = []  # outer edges: x from, x to, radius
    xs = []
    for poly in cut:
        rings = [poly.exterior] + list(poly.interiors)
        for ring in rings:
            pts = list(ring.coords)
            xs += [p[0] for p in pts]
            for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
                r = y1 - axis_v
                if abs(y2 - y1) > 1e-3 or abs(x2 - x1) < 0.3 or r < 0.05:
                    continue
                xm = (x1 + x2) / 2
                key = round(r, 2)
                below = poly.contains(Point(xm, y1 - 0.05))
                table = outer if below else inner
                if key not in table or abs(x2 - x1) > table[key][1]:
                    table[key] = (xm, abs(x2 - x1))
                if below:
                    steps.update((round(x1, 3), round(x2, 3)))
                    spans.append((min(x1, x2), max(x1, x2), r))
    if not xs:
        return []
    out = []
    n = start_id
    used_x: list[float] = []

    def free_x(x):  # two diameters on one line would overlap
        while any(abs(x - u) < 2.5 / s for u in used_x):
            x += 3.0 / s
        used_x.append(x)
        return x

    rmax = max(outer) if outer else 0.0
    for r, (xm, _) in sorted(outer.items()) + sorted(inner.items()):
        x = free_x(xm)
        a, b = place((x, axis_v - r)), place((x, axis_v + r))
        value = round(2 * r, 2)
        out.append(ir.Dimension(f"D{n}", 0.9, ["по модели"], dim_type="linear",
                                text="Ø" + _num(value), nominal=value,
                                measured=round(abs(b[1] - a[1]), 4), p1=a, p2=b,
                                line_point=((a[0] + b[0]) / 2, (a[1] + b[1]) / 2),
                                orientation="vertical"))
        n += 1
    # the steps' lengths under the view, the overall length under them
    bottom = axis_v - rmax

    def foot(x):  # the outline under the view at x: where the extension line starts
        r = max([sp[2] for sp in spans if sp[0] - 1e-3 <= x <= sp[1] + 1e-3] or [rmax])
        return (x, axis_v - r)

    xs_steps = sorted(steps)
    level = place((0.0, bottom))[1] - 10.0
    for x1, x2 in zip(xs_steps, xs_steps[1:]):
        if x2 - x1 < 0.5:
            continue
        a, b = place(foot(x1)), place(foot(x2))
        value = round(x2 - x1, 2)
        out.append(ir.Dimension(f"D{n}", 0.9, ["по модели"], dim_type="linear",
                                text=_num(value), nominal=value, measured=round(b[0] - a[0], 4),
                                p1=a, p2=b, line_point=((a[0] + b[0]) / 2, level),
                                orientation="horizontal"))
        n += 1
    x0, x1 = min(xs), max(xs)
    a, b = place(foot(x0)), place(foot(x1))
    value = round(x1 - x0, 2)
    out.append(ir.Dimension(f"D{n}", 0.9, ["по модели"], dim_type="linear", text=_num(value),
                            nominal=value, measured=round(b[0] - a[0], 4), p1=a, p2=b,
                            line_point=((a[0] + b[0]) / 2, level - 10.0),
                            orientation="horizontal"))
    return out


def _isometry_into(mesh, entities, box, s, notes) -> None:
    from ..kompas.writer import scale_name

    iso = project(mesh, *_isometry(), name="Изометрия", hidden=False)
    iw, ih = iso.hi[0] - iso.lo[0], iso.hi[1] - iso.lo[1]
    bw, bh = box[1] - box[0], box[3] - box[2]
    if bw <= 0 or bh <= 0:
        return
    k = min(s, 0.9 * bw / iw if iw else s, 0.9 * bh / ih if ih else s)
    if k >= 0.2 * s:
        k = _standard_below(k)
        at = ((box[0] + box[1]) / 2, (box[2] + box[3]) / 2)
        entities += trace(iso, k, at, start_id=len(entities) + 1)
        notes.append(f"Изометрия в масштабе {scale_name(k)} (без невидимых линий)")


def model_drawing(triangles: np.ndarray, view_scale: float | None = None,
                  layout=None, source: str = "") -> tuple[ir.Drawing, list[str]]:
    """An ir.Drawing of the part's views on a sheet, and notes for the report."""
    from ..gui.workers import lay_out_views
    from ..kompas.writer import scale_name

    layout = layout or lay_out_views
    mesh = build_mesh(triangles)
    notes = [f"Виды построены программой по сетке модели ({len(mesh.faces)} треугольников)"]
    axis = revolve_axis(mesh)
    if axis is not None:
        fmt, land, s, W, H, entities = _revolve_drawing(mesh, axis, view_scale, layout, notes)
    else:
        fmt, land, s, W, H, entities = _prismatic_drawing(mesh, view_scale, layout, notes)
    drawing = ir.Drawing(source=source)
    drawing.sheet = ir.Sheet(format=f"A{fmt}", orientation="landscape" if land else "portrait",
                             width=W, height=H)
    drawing.scale = ir.Scale(value=s, text=scale_name(s), source="layout")
    drawing.entities = entities
    return drawing, notes


def _standard_below(k: float) -> float:
    """The largest ГОСТ 2.302 scale not above k."""
    from ..gui.workers import STANDARD_SCALES

    return next((v for v in STANDARD_SCALES if v <= k + 1e-9), k)


def _centre_marks(entities, s, start_id):
    """Centre lines across the circles of the views (3 mm past them)."""
    out = []
    n = start_id
    seen = []
    for e in entities:
        if not isinstance(e, ir.Circle) or e.radius < 1.0:
            continue
        if any(math.dist(e.center, c) < 0.05 for c in seen):
            continue  # concentric circles share the mark
        seen.append(e.center)
        r = max(c.radius for c in entities if isinstance(c, ir.Circle)
                and math.dist(c.center, e.center) < 0.05) + 3.0
        cx, cy = e.center
        out.append(ir.Line(f"L{n}", p1=(cx - r, cy), p2=(cx + r, cy), style=ir.STYLE_AXIAL))
        out.append(ir.Line(f"L{n + 1}", p1=(cx, cy - r), p2=(cx, cy + r), style=ir.STYLE_AXIAL))
        n += 2
    return out
