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
        u = (math.cos(ang), math.sin(ang))
        off = -a[0] * u[1] + a[1] * u[0]
        key = (round(ang, 4) % round(math.pi, 4), round(off, 3), v)
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


def axis_of_revolution(mesh: Mesh) -> tuple[float, float] | None:
    """(y, z) of the X axis the part is turned around, if it is a body of
    revolution about X (every vertex ring centred on one axis)."""
    v = mesh.vertices
    y0, z0 = (v[:, 1].min() + v[:, 1].max()) / 2, (v[:, 2].min() + v[:, 2].max()) / 2
    size = float(np.ptp(v, axis=0).max()) or 1.0
    if abs(np.ptp(v[:, 1]) - np.ptp(v[:, 2])) > 1e-3 * size:
        return None
    # every face normal lies in the plane of the axis and its own position
    c = mesh.vertices[mesh.faces].mean(axis=1)
    radial = np.stack([np.zeros(len(c)), c[:, 1] - y0, c[:, 2] - z0], axis=1)
    rn = np.linalg.norm(radial, axis=1)
    ok = rn > 1e-6 * size
    cross = np.cross(radial[ok] / rn[ok, None], mesh.normals[ok])
    # the normal has no part around the axis (no X component of the cross)
    if np.abs(cross[:, 0]).max() > 0.05:
        return None
    return float(y0), float(z0)


def model_drawing(triangles: np.ndarray, view_scale: float | None = None,
                  layout=None, source: str = "") -> tuple[ir.Drawing, list[str]]:
    """An ir.Drawing of the part's views on a sheet, and notes for the report."""
    from ..gui.workers import lay_out_views
    from ..kompas.writer import scale_name

    layout = layout or lay_out_views
    mesh = build_mesh(triangles)
    lo, hi = mesh.lo, mesh.hi
    size = tuple(float(v) for v in hi - lo)
    fmt, land, s, places = layout(size, view_scale)
    axis = axis_of_revolution(mesh)
    notes = [f"Виды построены программой по сетке модели ({len(mesh.faces)} треугольников)"]
    views = dict(VIEWS)
    if axis is not None:
        views.pop("Сверху")  # the same as the front view
        notes.append("Тело вращения: вид сверху не нужен (совпадает с главным)")
    entities: list[ir.Entity] = []
    for name, basis in views.items():
        view = project(mesh, *basis, name=name)
        entities += trace(view, s, places["#" + name], start_id=len(entities) + 1)
        if axis is not None and name == "Спереди":
            entities += _axis_line(view, s, places["#Спереди"], mesh, axis, len(entities) + 1)
    entities += _centre_marks(entities, s, len(entities) + 1)
    # the isometry (visible edges only) in the free corner, as big as it fits:
    # under the front view (a body of revolution: no top view there), else
    # under the left view, above the title block
    sizes = {0: (1189, 841), 1: (841, 594), 2: (594, 420), 3: (420, 297), 4: (297, 210)}
    W, H = sizes[fmt] if land else sizes[fmt][::-1]
    fx, fy = places["#Спереди"]
    if axis is not None:
        box = (30.0, W - 10.0, 65.0, fy - size[1] * s / 2 - 10.0)
    else:
        lx_, _ = places["#Слева"]
        _, ty = places["#Сверху"]
        box = (lx_ - size[2] * s / 2, W - 10.0, 65.0, ty + size[2] * s / 2)
    iso = project(mesh, *_isometry(), name="Изометрия", hidden=False)
    iw, ih = iso.hi[0] - iso.lo[0], iso.hi[1] - iso.lo[1]
    bw, bh = box[1] - box[0], box[3] - box[2]
    k = min(s, 0.9 * bw / iw if iw else s, 0.9 * bh / ih if ih else s)
    if k >= 0.2 * s and bw > 0 and bh > 0:
        k = _standard_below(k)
        at = ((box[0] + box[1]) / 2, (box[2] + box[3]) / 2)
        entities += trace(iso, k, at, start_id=len(entities) + 1)
        notes.append(f"Изометрия в масштабе {scale_name(k)} (без невидимых линий)")
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


def _axis_line(view: View, s, at, mesh: Mesh, axis, start_id):
    """The axis of a body of revolution in the front view, 5 mm past it."""
    cu, cv = (view.lo[0] + view.hi[0]) / 2, (view.lo[1] + view.hi[1]) / 2
    y = at[1] + (axis[0] - cv) * s
    x0 = at[0] + (view.lo[0] - cu) * s - 5.0
    x1 = at[0] + (view.hi[0] - cu) * s + 5.0
    return [ir.Line(f"L{start_id}", p1=(x0, y), p2=(x1, y), style=ir.STYLE_AXIAL)]


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
