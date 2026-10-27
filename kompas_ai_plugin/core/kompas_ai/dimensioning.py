"""Sizes put on a finished drawing by ГОСТ 2.307.

A KOMPAS drawing comes in as DXF (KOMPAS saves its sheet so: sheet
millimetres, the line styles named K5LT_BASIC, K5LT_THIN, K5LT_AXLED…, the
sizes as DIMENSION objects). The views are found as groups of the contour
lines; a view drawn around a horizontal or vertical axis and symmetric about
it is a body of revolution and gets its diameters and the lengths of its
steps; any other view its overall sizes, the diameters of its holes, the
radii of its roundings and the places of the holes from its edges.

Then the sizes are laid out so that none runs into another: the first
dimension line 10 mm off the contour, the next ones 7 mm apart (ГОСТ 2.307
п. 1.7), the smaller sizes nearer to the part, a size whose value is wider
than itself moved off its neighbours' level, a side taken by another view
given up for the opposite one. A size already given in one view is not
repeated in another.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import ir

FIRST_GAP = 10.0  # sheet mm from the contour to the first dimension line
LINE_GAP = 7.0  # sheet mm between parallel dimension lines
TIGHT_GAP = 5.0  # sheet mm: the least, where there is no room for the above
CHAR_W = 2.5  # sheet mm a character of 3,5 mm dimension text takes
ARROWS = 7.0  # sheet mm the two arrows need inside a dimension line
VIEW_GAP = 2.0  # sheet mm: contour lines closer than this are one view
SMALL_VIEW = 8.0  # sheet mm: a smaller group of lines is a sign or a mark, not a view
DIA_GAP = 7.0  # sheet mm between two diameters' dimension lines
MAX_HOLE_PLACES = 8  # hole centres given their places at most in one view
MAX_RADII = 4
CHAIN = {"длина", "глубина", "положение"}  # sizes that make chains
TITLE_W, TITLE_H = 185.0, 55.0  # the main title block (ГОСТ 2.104), bottom right

FORMATS = {"A0": (1189, 841), "A1": (841, 594), "A2": (594, 420), "A3": (420, 297),
           "A4": (297, 210)}
SCALE_RE = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*:\s*(\d+(?:[.,]\d+)?)\s*$")


def _num(v: float) -> str:
    text = f"{v:.2f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


# --- reading the drawing ---------------------------------------------------------------------

def _style(entity, doc) -> str:
    """ir style of a DXF line: by its line type (KOMPAS names them K5LT_…),
    else by its layer's, else by its weight."""
    lt = (entity.dxf.get("linetype") or "BYLAYER").upper()
    layer = None
    if lt in ("BYLAYER", "BYBLOCK"):
        try:
            layer = doc.layers.get(entity.dxf.layer)
            lt = (layer.dxf.get("linetype") or "").upper()
        except Exception:
            lt = ""
    name = lt + " " + (entity.dxf.get("layer") or "").upper()
    if any(k in name for k in ("AXL", "AXIS", "AXIAL", "CENTER", "DASHDOT", "ОСЕВ")):
        return ir.STYLE_AXIAL
    if any(k in name for k in ("DASH", "HIDDEN", "ШТРИХ")):
        return ir.STYLE_DASHED
    if "BASIC" in name or "MAIN" in name or "ОСНОВ" in name:
        return ir.STYLE_MAIN
    if "THIN" in name or "ТОНК" in name:
        return ir.STYLE_THIN
    weight = entity.dxf.get("lineweight", -1)
    if weight is not None and weight < 0 and layer is not None:
        weight = layer.dxf.get("lineweight", -1)
    return ir.STYLE_MAIN if weight is not None and weight >= 35 else ir.STYLE_THIN


def plain_text(raw: str) -> str:
    """MTEXT codes off a text: «\\H5.0;\\W0.965;∅15,8h12» → «Ø15,8h12»."""
    from ezdxf.tools.text import plain_mtext

    try:
        text = plain_mtext(raw or "")
    except Exception:
        text = raw or ""
    text = re.sub(r"\\[A-Za-z][^;\\]*;", "", text)
    return (text.replace("∅", "Ø").replace("%%c", "Ø").replace("%%C", "Ø")
            .replace("•", "×").replace("%%d", "°").replace("%%p", "±").strip())


@dataclass
class Source:
    """What was read: the drawing (geometry, texts, sizes there already),
    the sheet's scale if its title block has one."""

    drawing: ir.Drawing
    scale: float | None = None
    notes: list[str] = field(default_factory=list)


def read_dxf(path: str | Path) -> Source:
    import ezdxf

    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    drawing = ir.Drawing(source=str(path))
    ents = drawing.entities
    n = [0]

    def nid(prefix):
        n[0] += 1
        return f"{prefix}{n[0]}"

    texts: list[tuple[str, tuple]] = []

    def add(e, in_block: bool):
        kind = e.dxftype()
        try:
            if kind == "LINE":
                p1, p2 = e.dxf.start, e.dxf.end
                if math.hypot(p2[0] - p1[0], p2[1] - p1[1]) > 1e-6:
                    ents.append(ir.Line(nid("L"), p1=(p1[0], p1[1]), p2=(p2[0], p2[1]),
                                        style=_style(e, doc)))
            elif kind == "CIRCLE":
                c = e.dxf.center
                ents.append(ir.Circle(nid("C"), center=(c[0], c[1]), radius=e.dxf.radius,
                                      style=_style(e, doc)))
            elif kind == "ARC":
                c = e.dxf.center
                ents.append(ir.Arc(nid("A"), center=(c[0], c[1]), radius=e.dxf.radius,
                                   start_angle=e.dxf.start_angle, end_angle=e.dxf.end_angle,
                                   style=_style(e, doc)))
            elif kind in ("LWPOLYLINE", "POLYLINE"):
                style = _style(e, doc)
                for v in e.virtual_entities():
                    v.dxf.linetype = e.dxf.get("linetype", "BYLAYER")
                    v.dxf.layer = e.dxf.get("layer", "0")
                    add(v, in_block)
                    if isinstance(ents[-1], (ir.Line, ir.Arc)):
                        ents[-1].style = style
            elif kind in ("SPLINE", "ELLIPSE"):
                style = _style(e, doc)
                pts = [(p[0], p[1]) for p in e.flattening(0.05)]
                for a, b in zip(pts, pts[1:]):
                    if math.dist(a, b) > 1e-6:
                        ents.append(ir.Line(nid("L"), p1=a, p2=b, style=style,
                                            notes=["кривая"]))
            elif kind in ("TEXT", "MTEXT", "ATTRIB"):
                raw = e.text if kind == "MTEXT" else e.dxf.text
                text = plain_text(raw)
                if text:
                    p = e.dxf.insert
                    h = e.dxf.get("char_height" if kind == "MTEXT" else "height", 3.5) or 3.5
                    ents.append(ir.Text(nid("T"), text=text, position=(p[0], p[1]), height=h,
                                        angle=e.dxf.get("rotation", 0.0) or 0.0))
                    texts.append((text, (p[0], p[1])))
            elif kind == "HATCH":
                rings = []
                from ezdxf import path as dxfpath

                for pth in dxfpath.from_hatch(e):
                    pts = [(p[0], p[1]) for p in pth.flattening(0.1)]
                    if len(pts) >= 3:
                        rings.append(pts)
                if rings:
                    ents.append(ir.Hatch(nid("H"), contours=rings,
                                         angle=e.dxf.get("pattern_angle", 45.0) or 45.0))
            elif kind == "INSERT":
                for v in e.virtual_entities():
                    add(v, True)
            elif kind == "DIMENSION" and not in_block:
                d = _dimension_of(e, nid("D"))
                if d is not None:
                    ents.append(d)
        except Exception:
            pass  # an object ezdxf cannot take apart is not needed for the sizes

    for e in msp:
        add(e, False)

    src = Source(drawing)
    _sheet_of(doc, drawing)
    # the scale in the title block: the «1:2» text lowest on the sheet
    scales = [(p[1], t) for t, p in texts if SCALE_RE.match(t)]
    if scales:
        a, b = SCALE_RE.match(min(scales)[1]).groups()
        src.scale = float(a.replace(",", ".")) / float(b.replace(",", "."))
        drawing.scale = ir.Scale(src.scale, min(scales)[1].strip(), "title_block")
    return src


def _sheet_of(doc, drawing: ir.Drawing) -> None:
    """The format: KOMPAS writes the sheet's corners as the drawing's extents."""
    try:
        lo, hi = doc.header.get("$EXTMIN"), doc.header.get("$EXTMAX")
        w, h = hi[0] - min(0.0, lo[0]), hi[1] - min(0.0, lo[1])
    except Exception:
        w = h = 0.0
    xs = [q[0] for e in drawing.entities for q in _points(e)]
    ys = [q[1] for e in drawing.entities for q in _points(e)]
    if not xs:
        return
    if w < max(xs) or h < max(ys) or w > 2000:
        w, h = max(xs) - min(0.0, min(xs)), max(ys) - min(0.0, min(ys))
    for name, (a, b) in FORMATS.items():
        for land, (W, H) in ((True, (a, b)), (False, (b, a))):
            if abs(w - W) < 3 and abs(h - H) < 3:
                drawing.sheet = ir.Sheet(format=name, orientation="landscape" if land
                                         else "portrait", width=W, height=H, frame_found=True)
                return
    drawing.sheet = ir.Sheet(format="custom", width=w, height=h)


def _dimension_of(e, did: str) -> ir.Dimension | None:
    """A DXF DIMENSION as an ir.Dimension (its measured points, line, text)."""
    kind = e.dxf.dimtype & 7
    text = e.dxf.get("text") or ""
    text = "" if text in ("", "<>") else plain_text(text.replace("<>", ""))

    def p(name):
        v = e.dxf.get(name)
        return None if v is None else (v[0], v[1])

    if kind in (0, 1):
        a, b, line = p("defpoint2"), p("defpoint3"), p("defpoint")
        if a is None or b is None:
            return None
        angle = (e.dxf.get("angle", 0.0) or 0.0) % 180.0 if kind == 0 else None
        orient = "horizontal" if angle is not None and abs(angle) < 1 or angle is not None \
            and abs(angle - 180) < 1 else "vertical" if angle is not None \
            and abs(angle - 90) < 1 else "aligned"
        measured = abs(b[0] - a[0]) if orient == "horizontal" else abs(b[1] - a[1]) \
            if orient == "vertical" else math.dist(a, b)
        return ir.Dimension(did, text=text, p1=a, p2=b, line_point=line, orientation=orient,
                            measured=measured, notes=["на чертеже"])
    if kind == 3:  # diameter: two points across
        a, b = p("defpoint"), p("defpoint4")
        if a is None or b is None:
            return None
        c = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        return ir.Dimension(did, dim_type="diameter", text=text, p1=b, center=c,
                            radius=math.dist(a, b) / 2, measured=math.dist(a, b),
                            notes=["на чертеже"])
    if kind == 4:  # radius: the centre and a point of the arc
        c, b = p("defpoint"), p("defpoint4")
        if c is None or b is None:
            return None
        return ir.Dimension(did, dim_type="radius", text=text, p1=b, center=c,
                            radius=math.dist(c, b), measured=math.dist(c, b),
                            notes=["на чертеже"])
    return ir.Dimension(did, dim_type="angular", text=text, notes=["на чертеже"])


def _points(e) -> list:
    if isinstance(e, ir.Line):
        return [e.p1, e.p2]
    if isinstance(e, (ir.Circle, ir.Arc)):
        b = _bbox(e)
        return [(b[0], b[1]), (b[2], b[3])]
    if isinstance(e, ir.Text):
        return [e.position]
    return []


def _bbox(e):
    if isinstance(e, ir.Line):
        return (min(e.p1[0], e.p2[0]), min(e.p1[1], e.p2[1]),
                max(e.p1[0], e.p2[0]), max(e.p1[1], e.p2[1]))
    if isinstance(e, ir.Circle):
        c, r = e.center, e.radius
        return (c[0] - r, c[1] - r, c[0] + r, c[1] + r)
    if isinstance(e, ir.Arc):
        pts = [_arc_point(e, e.start_angle), _arc_point(e, e.end_angle)]
        for k in range(4):
            if _on_arc(e, 90.0 * k):
                pts.append(_arc_point(e, 90.0 * k))
        return (min(q[0] for q in pts), min(q[1] for q in pts),
                max(q[0] for q in pts), max(q[1] for q in pts))
    return None


def _arc_point(a, deg):
    t = math.radians(deg)
    return (a.center[0] + a.radius * math.cos(t), a.center[1] + a.radius * math.sin(t))


def _on_arc(a, deg) -> bool:
    return (deg - a.start_angle) % 360.0 <= (a.end_angle - a.start_angle) % 360.0 + 1e-9


def _sweep(a) -> float:
    s = (a.end_angle - a.start_angle) % 360.0
    return 360.0 if s < 1e-9 else s


# --- the views --------------------------------------------------------------------------------

@dataclass
class View:
    box: tuple  # x0, y0, x1, y1 of its contour, sheet mm
    entities: list  # its contour lines, arcs, circles
    others: list  # thin and axial lines, hatches near it
    scale: float = 1.0
    axis: tuple | None = None  # ("h"|"v", coordinate) of a body of revolution's axis

    @property
    def width(self) -> float:
        return self.box[2] - self.box[0]

    @property
    def height(self) -> float:
        return self.box[3] - self.box[1]


def find_views(drawing: ir.Drawing) -> list[View]:
    """Groups of contour lines, biggest first, without the frame, the title
    block and small signs."""
    items = [(e, _bbox(e)) for e in drawing.entities
             if isinstance(e, (ir.Line, ir.Arc, ir.Circle)) and e.style == ir.STYLE_MAIN]
    items = [(e, b) for e, b in items if b is not None]
    parent = list(range(len(items)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    order = sorted(range(len(items)), key=lambda i: items[i][1][0])
    active: list[int] = []
    for i in order:
        b = items[i][1]
        active = [j for j in active if items[j][1][2] + VIEW_GAP >= b[0]]
        for j in active:
            c = items[j][1]
            if c[1] - VIEW_GAP <= b[3] and b[1] - VIEW_GAP <= c[3]:
                parent[root(i)] = root(j)
        active.append(i)
    groups: dict[int, list] = {}
    for i in range(len(items)):
        groups.setdefault(root(i), []).append(i)
    sheet_w, sheet_h = drawing.sheet.width, drawing.sheet.height

    def box_of(members):
        boxes = [items[i][1] for i in members]
        return (min(b[0] for b in boxes), min(b[1] for b in boxes),
                max(b[2] for b in boxes), max(b[3] for b in boxes))

    # a hole standing free inside an outline belongs to its view (the
    # smallest outline round it, not the frame)
    parts = sorted(groups.values(), key=lambda m: _area(box_of(m)))
    merged: list[list] = []
    for k, members in enumerate(parts):
        b = box_of(members)
        host = next((o for o in parts[k + 1:] if _area(box_of(o)) > _area(b)
                     and _contains(box_of(o), b) and _frame_format(box_of(o)) is None), None)
        if host is not None:
            host.extend(members)
        else:
            merged.append(members)
    views = []
    for members in merged:
        box = box_of(members)
        w, h = box[2] - box[0], box[3] - box[1]
        if max(w, h) < SMALL_VIEW:
            continue
        frame = _frame_format(box)
        if frame is not None:
            if not drawing.sheet.frame_found:
                name, land, W, H = frame
                drawing.sheet = ir.Sheet(format=name, orientation="landscape" if land
                                         else "portrait", width=W, height=H, frame_found=True)
            continue
        if w > 0.7 * sheet_w or h > 0.7 * sheet_h:
            continue  # a frame of another kind
        if len(members) < 3:
            continue  # a lone line: a section mark, a leader
        views.append(View(box, [items[i][0] for i in members], []))
    for v in views:
        x0, y0, x1, y1 = v.box
        for e in drawing.entities:
            if isinstance(e, (ir.Line, ir.Arc, ir.Circle)) and e.style != ir.STYLE_MAIN:
                b = _bbox(e)
                if b and b[0] >= x0 - 12 and b[2] <= x1 + 12 and b[1] >= y0 - 12 \
                        and b[3] <= y1 + 12:
                    v.others.append(e)
            elif isinstance(e, ir.Hatch) and e.contours:
                xs = [q[0] for q in e.contours[0]]
                ys = [q[1] for q in e.contours[0]]
                if min(xs) >= x0 - 1 and max(xs) <= x1 + 1 and min(ys) >= y0 - 1 \
                        and max(ys) <= y1 + 1:
                    v.others.append(e)
    views = [v for v in views if not _axonometric(v)]
    views.sort(key=lambda v: -v.width * v.height)
    return views


def _axonometric(v: View) -> bool:
    """An isometry: most of its long straight lines neither level nor upright."""
    total = slanted = 0.0
    size = max(v.width, v.height)
    for e in v.entities:
        if isinstance(e, ir.Line) and "кривая" not in e.notes:
            dx, dy = abs(e.p2[0] - e.p1[0]), abs(e.p2[1] - e.p1[1])
            L = math.hypot(dx, dy)
            if L < 0.05 * size:
                continue  # a curve drawn with short pieces
            total += L
            if min(dx, dy) > 0.05 * L:
                slanted += L
    return total > 0 and slanted > 0.5 * total


LABEL_SCALE_RE = re.compile(r"\(\s*(\d+(?:[.,]\d+)?)\s*:\s*(\d+(?:[.,]\d+)?)\s*\)")


def _area(b) -> float:
    return (b[2] - b[0]) * (b[3] - b[1])


def _contains(outer, inner) -> bool:
    return outer[0] <= inner[0] and outer[1] <= inner[1] and inner[2] <= outer[2] \
        and inner[3] <= outer[3]


def _frame_format(box):
    """(format, landscape, W, H) when ``box`` is a sheet's frame: 5 mm off
    the right, top and bottom edges of the sheet (ГОСТ 2.104)."""
    for name, (a, b) in FORMATS.items():
        for land, (W, H) in ((True, (a, b)), (False, (b, a))):
            # the left edge may take in the extra columns left of the frame
            if abs(box[2] - (W - 5)) < 3 and abs(box[3] - (H - 5)) < 3 \
                    and abs(box[1] - 5) < 3 and box[0] <= 23:
                return name, land, W, H
    return None


def _view_scale(v: View, dims, default: float, texts=()) -> float:
    """The scale of a view: its label's («Б (10:1)» over it), else what its
    sizes say (sheet length over the number written), else the sheet's."""
    for t in texts:
        m = LABEL_SCALE_RE.search(t.text)
        x, y = t.position
        if m and v.box[3] - 2 <= y <= v.box[3] + 25 and v.box[0] - 30 <= x <= v.box[2] + 10:
            return float(m.group(1).replace(",", ".")) / float(m.group(2).replace(",", "."))
    ratios = []
    for d in dims:
        if d.dim_type != "linear" or not d.p1 or not d.p2 or not d.measured:
            continue
        if not (_inside(d.p1, v.box, 1.0) and _inside(d.p2, v.box, 1.0)):
            continue
        m = re.search(r"\d+(?:[.,]\d+)?", d.text or "")
        if not m:
            continue
        value = float(m.group(0).replace(",", "."))
        if value > 0:
            ratios.append(d.measured / value)
    if not ratios:
        return default
    ratios.sort()
    mid = ratios[len(ratios) // 2]
    for s in (10, 5, 4, 2.5, 2, 1, 0.5, 0.4, 0.25, 0.2, 0.1):
        if abs(mid - s) < 0.03 * s:
            return float(s)
    return default


def _inside(p, box, tol=0.0) -> bool:
    return box[0] - tol <= p[0] <= box[2] + tol and box[1] - tol <= p[1] <= box[3] + tol


# --- what a view is ---------------------------------------------------------------------------

def _revolve_axis(v: View):
    """("h", y) or ("v", x): an axial line through the whole view, the
    contour symmetric about it."""
    best = None
    for e in v.others:
        if not isinstance(e, ir.Line) or e.style != ir.STYLE_AXIAL:
            continue
        dx, dy = abs(e.p2[0] - e.p1[0]), abs(e.p2[1] - e.p1[1])
        if dy < 0.01 * max(dx, 1e-9) and dx >= 0.6 * v.width:
            cand = ("h", (e.p1[1] + e.p2[1]) / 2, dx / max(v.width, 1e-9))
        elif dx < 0.01 * max(dy, 1e-9) and dy >= 0.6 * v.height:
            cand = ("v", (e.p1[0] + e.p2[0]) / 2, dy / max(v.height, 1e-9))
        else:
            continue
        if best is None or cand[2] > best[2]:
            best = cand
    if best is None:
        return None
    kind, a, _ = best
    k = 1 if kind == "h" else 0
    # the outline the same on both sides of it (a boss or a flat may break it
    # here and there; inside, a half section differs from a half view)
    to, _ = _uv(kind)
    up, down = [], []
    for e in v.entities:
        if isinstance(e, ir.Line):
            (u1, w1), (u2, w2) = to(e.p1), to(e.p2)
            if abs(w2 - w1) < 1e-3 and abs(u2 - u1) > 0.2:
                (up if w1 > a else down).append((min(u1, u2), max(u1, u2), abs(w1 - a)))
    if not up or not down:
        return None
    u0 = min(x[0] for x in up + down)
    u1 = max(x[1] for x in up + down)
    same = total = 0
    for k in range(1, 60):
        u = u0 + (u1 - u0) * k / 60
        r_up = max([r for p, q, r in up if p <= u <= q] or [0.0])
        r_dn = max([r for p, q, r in down if p <= u <= q] or [0.0])
        if r_up or r_dn:
            total += 1
            same += abs(r_up - r_dn) < 0.3
    return (kind, a) if total and same >= 0.6 * total else None


# --- sizes ------------------------------------------------------------------------------------

def _uv(kind):
    """Sheet ↔ (along the axis, across it) for an axis ("h"|"v")."""
    if kind == "h":
        return (lambda p: (p[0], p[1])), (lambda u, w: (u, w))
    return (lambda p: (p[1], p[0])), (lambda u, w: (w, u))


def revolve_sizes(v: View, nid) -> list[ir.Dimension]:
    """The diameters (across the view) and the step lengths (an open chain
    and the overall length) of a body of revolution."""
    kind, a = v.axis
    to, back = _uv(kind)
    s = v.scale
    along: list[tuple[float, float, float]] = []  # u1, u2, |w - a|
    across: list[tuple[float, float, float]] = []  # u, w1, w2 (offsets from the axis)
    for e in v.entities:
        if not isinstance(e, ir.Line):
            continue
        (u1, w1), (u2, w2) = to(e.p1), to(e.p2)
        if abs(w2 - w1) < 1e-3 and abs(u2 - u1) > 0.2:
            along.append((min(u1, u2), max(u1, u2), abs(w1 - a)))
        elif abs(u2 - u1) < 1e-3 and abs(w2 - w1) > 0.2:
            across.append((u1, min(w1, w2) - a, max(w1, w2) - a))
    if not along:
        return []
    u_min = min(min(x[0] for x in along), min((x[0] for x in across), default=1e9))
    u_max = max(max(x[1] for x in along), max((x[0] for x in across), default=-1e9))
    radii: dict[float, tuple[float, float]] = {}  # r → (u of the middle, length) longest
    for u1, u2, r in along:
        if r < 0.3:
            continue
        key = round(r, 2)
        if u2 - u1 >= 1.0 and (key not in radii or u2 - u1 > radii[key][1]):
            radii[key] = ((u1 + u2) / 2, u2 - u1)
    # a radius seen on one side only (a flat, a hex's edge) is no diameter,
    # unless it borders a section
    hatched = [h for h in v.others if isinstance(h, ir.Hatch)]
    sides = {}
    for e in v.entities:
        if isinstance(e, ir.Line):
            (u1, w1), (u2, w2) = to(e.p1), to(e.p2)
            if abs(w2 - w1) < 1e-3:
                sides.setdefault(round(abs(w1 - a), 2), set()).add(1 if w1 > a else -1)
    out = []
    used: list[float] = []

    def free(u):
        for step in [0.0] + [k * sg for k in (1, 2, 3, 4) for sg in (1, -1)]:
            x = u + step * DIA_GAP
            if all(abs(x - y) >= DIA_GAP for y in used):
                used.append(x)
                return x
        used.append(u)
        return u

    envelope = max(radii) if radii else 0.0
    for r, (um, length) in sorted(radii.items()):
        both = len(sides.get(r, ())) == 2
        cut = any(_near_hatch(back(um, a + r), h) or _near_hatch(back(um, a - r), h)
                  for h in hatched)
        if not both and not cut:
            continue
        u = free(um)
        p1, p2 = back(u, a - r), back(u, a + r)
        value = round(2 * r / s, 2)
        lp = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
        out.append(ir.Dimension(nid(), 0.9, ["авто", "диаметр"], dim_type="linear",
                                text="Ø" + _num(value), nominal=value,
                                measured=round(2 * r, 4), p1=p1, p2=p2, line_point=lp,
                                orientation="vertical" if kind == "h" else "horizontal"))

    def outer_at(u):
        return max([r for u1, u2, r in along if u1 - 1e-3 <= u <= u2 + 1e-3] or [envelope])

    # shoulders: faces square to the axis reaching the outline (the outer
    # chain) or not (the bore's steps)
    outer_u, inner_u = set(), set()
    for u, w1, w2 in across:
        reach = max(abs(w1), abs(w2))
        if abs(u - u_min) < 0.2 or abs(u - u_max) < 0.2:
            continue
        neighbours = max(outer_at(u - 0.3), outer_at(u + 0.3))
        (outer_u if reach >= neighbours - 0.3 or reach >= min(outer_at(u - 0.3),
                                                               outer_at(u + 0.3)) - 0.05
         else inner_u).add(round(u, 2))
    side = -1  # the lengths under (left of) the view

    def length(u1, u2, r1, r2, tag, sign):
        p1, p2 = back(u1, a + sign * r1), back(u2, a + sign * r2)
        value = round((u2 - u1) / s, 2)
        return ir.Dimension(nid(), 0.9, ["авто", tag], dim_type="linear", text=_num(value),
                            nominal=value, measured=round(u2 - u1, 4), p1=p1, p2=p2,
                            line_point=p1, orientation="horizontal" if kind == "h"
                            else "vertical")

    chain = sorted(_merge_close(outer_u | {u_min, u_max}))
    links = list(zip(chain, chain[1:]))
    if len(links) >= 2:
        longest = max(range(len(links)), key=lambda i: links[i][1] - links[i][0])
        links = links[:longest] + links[longest + 1:]  # the chain left open (ГОСТ 2.307 п. 1.9)
        for u1, u2 in links:
            out.append(length(u1, u2, outer_at(u1 + 0.01), outer_at(u2 - 0.01), "длина", side))
    out.append(length(u_min, u_max, outer_at(u_min + 0.01), outer_at(u_max - 0.01),
                      "габарит", side))
    if inner_u:
        # the bore's steps from the nearer end face, over the view
        inner = sorted(_merge_close(inner_u))
        start = u_min if inner[0] - u_min <= u_max - inner[-1] else u_max
        for u in inner:
            r = outer_at(u)
            out.append(length(min(start, u), max(start, u), r, r, "глубина", 1))
    return out


def _merge_close(values, tol: float = 0.3) -> list:
    out: list[float] = []
    for x in sorted(values):
        if not out or x - out[-1] > tol:
            out.append(x)
    return out


def _near_hatch(p, h: ir.Hatch, tol: float = 0.4) -> bool:
    for ring in h.contours:
        for a, b in zip(ring, ring[1:] + ring[:1]):
            if _seg_dist(p, a, b) < tol:
                return True
    return False


def _seg_dist(p, a, b) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = dx * dx + dy * dy
    t = 0.0 if L < 1e-12 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L))
    return math.dist(p, (a[0] + t * dx, a[1] + t * dy))


def prismatic_sizes(v: View, nid) -> list[ir.Dimension]:
    """Overall sizes, hole diameters (with their count), rounding radii and
    the hole centres' places from the left and the bottom edge."""
    s = v.scale
    x0, y0, x1, y1 = v.box
    out = []
    w, h = round((x1 - x0) / s, 2), round((y1 - y0) / s, 2)
    out.append(ir.Dimension(nid(), 0.9, ["авто", "габарит"], dim_type="linear", text=_num(w),
                            nominal=w, measured=x1 - x0, p1=(x0, y0), p2=(x1, y0),
                            line_point=(x0, y0), orientation="horizontal"))
    out.append(ir.Dimension(nid(), 0.9, ["авто", "габарит"], dim_type="linear", text=_num(h),
                            nominal=h, measured=y1 - y0, p1=(x0, y0), p2=(x0, y1),
                            line_point=(x0, y0), orientation="vertical"))
    circles = [e for e in v.entities if isinstance(e, ir.Circle)]
    full_arcs = {}
    for e in v.entities:  # a circle drawn as arcs
        if isinstance(e, ir.Arc):
            key = (round(e.center[0], 2), round(e.center[1], 2), round(e.radius, 2))
            full_arcs[key] = full_arcs.get(key, 0.0) + _sweep(e)
    for (cx, cy, r), sweep in full_arcs.items():
        if sweep >= 359.0:
            circles.append(ir.Circle("", center=(cx, cy), radius=r))
    count: dict[float, int] = {}
    for c in circles:
        key = round(2 * c.radius / s, 2)
        count[key] = count.get(key, 0) + 1
    seen = set()
    for c in sorted(circles, key=lambda c: -c.radius):
        d = round(2 * c.radius / s, 2)
        if d in seen:
            continue
        seen.add(d)
        many = f"{count[d]} отв. " if count[d] > 1 else ""
        p = (c.center[0] + c.radius * math.cos(math.radians(45)),
             c.center[1] + c.radius * math.sin(math.radians(45)))
        out.append(ir.Dimension(nid(), 0.9, ["авто", "отверстие"], dim_type="diameter",
                                text=many + "Ø" + _num(d), nominal=d, measured=2 * c.radius,
                                p1=p, center=c.center, radius=c.radius))
    radii = {}
    for e in v.entities:
        if isinstance(e, ir.Arc) and _sweep(e) < 359.0 and e.radius / s >= 0.5:
            key = (round(e.center[0], 2), round(e.center[1], 2), round(e.radius, 2))
            if full_arcs.get(key, 0.0) >= 359.0:
                continue
            r = round(e.radius / s, 2)
            r = next((q for q in radii if abs(q - r) <= max(0.05, 0.005 * r)), r)
            if r not in radii or _sweep(e) > _sweep(radii[r]):
                radii[r] = e
    for r, e in sorted(radii.items(), key=lambda kv: -kv[0])[:MAX_RADII]:
        mid = e.start_angle + _sweep(e) / 2
        out.append(ir.Dimension(nid(), 0.9, ["авто", "скругление"], dim_type="radius",
                                text="R" + _num(r), nominal=r, measured=e.radius,
                                p1=_arc_point(e, mid), center=e.center, radius=e.radius))
    # the hole centres from the left and the bottom edge (one size per line of centres)
    centres = []
    for c in sorted(circles, key=lambda c: (c.center[0], c.center[1])):
        if not any(math.dist(c.center, q) < 0.05 for q in centres):
            centres.append(c.center)
    xs = _merge_close([q[0] for q in centres if q[0] - x0 > 0.5 and x1 - q[0] > 0.5], 0.05)
    ys = _merge_close([q[1] for q in centres if q[1] - y0 > 0.5 and y1 - q[1] > 0.5], 0.05)
    for x in xs[:MAX_HOLE_PLACES]:
        q = next(c for c in centres if abs(c[0] - x) <= 0.05)
        value = round((x - x0) / s, 2)
        out.append(ir.Dimension(nid(), 0.9, ["авто", "положение"], dim_type="linear",
                                text=_num(value), nominal=value, measured=x - x0,
                                p1=(x0, y1), p2=(x, q[1]), line_point=(x0, y1),
                                orientation="horizontal"))
    for y in ys[:MAX_HOLE_PLACES]:
        q = next(c for c in centres if abs(c[1] - y) <= 0.05)
        value = round((y - y0) / s, 2)
        out.append(ir.Dimension(nid(), 0.9, ["авто", "положение"], dim_type="linear",
                                text=_num(value), nominal=value, measured=y - y0,
                                p1=(x1, y0), p2=(q[0], y), line_point=(x1, y0),
                                orientation="vertical"))
    return out


# --- laying the sizes out ---------------------------------------------------------------------

def text_width(text: str) -> float:
    return CHAR_W * len(text) + 1.0


def _span(d: ir.Dimension, axis: int):
    """The extent of a linear size along its dimension line, with its value
    (centred on it, or beside it when it does not fit between the arrows)."""
    lo, hi = sorted((d.p1[axis], d.p2[axis]))
    need = text_width(d.text) + ARROWS
    if hi - lo < need:  # the value goes beside: count it on the wider side
        mid = (lo + hi) / 2
        return min(lo, mid - need / 2) - 1.0, max(hi, mid + need / 2) + 1.0
    return lo - 1.0, hi + 1.0


def _owner(d: ir.Dimension, views: list[View]) -> View | None:
    pts = [q for q in (d.p1, d.p2, d.center) if q]
    for v in views:
        if pts and all(_inside(q, v.box, 1.5) for q in pts):
            return v
    best = None
    for v in views:
        if pts and any(_inside(q, v.box, 1.5) for q in pts):
            best = best or v
    return best


def arrange(dims: list[ir.Dimension], views: list[View], fixed=(), room=None) -> int:
    """Dimension lines of the linear sizes off the contour, smaller sizes
    nearer, none closer than LINE_GAP to another over the same stretch;
    ``fixed`` sizes (there already) are not moved but kept clear of. Returns
    how many sizes were placed."""
    placed: dict[tuple, list] = {}  # (view id, axis, side) → [(level, lo, hi)]
    others = [v.box for v in views]

    def taken(key, level, lo, hi, gap=LINE_GAP):
        # parallel lines of any view: those of two views next to each other meet too
        return any(abs(level - L) < gap - 1e-6 and min(hi, h2) - max(lo, l2) > 0
                   for k, lines in placed.items() if k[1] == key[1] for L, l2, h2 in lines)

    def blocked(axis, edge, level, lo, hi, own):
        """The size's extension lines and its line (the band from the view's
        ``edge`` out to ``level`` over [lo, hi]) run through another view, or
        the line is off the sheet."""
        a0, a1 = sorted((edge, level))
        a0, a1 = a0 - 2.0, a1 + 2.0
        for box in others:
            if box is own:
                continue
            if axis == 1:  # horizontal lines: the band spans y a0..a1, x lo..hi
                if min(a1, box[3]) - max(a0, box[1]) > 0 and min(hi, box[2]) - max(lo, box[0]) > 0:
                    return True
            elif min(a1, box[2]) - max(a0, box[0]) > 0 and min(hi, box[3]) - max(lo, box[1]) > 0:
                return True
        if room is not None:  # inside the frame, off the title block
            x0, y0, x1, y1 = room
            if axis == 1:
                if not (y0 + 4.0 <= level <= y1 - 4.0) or lo < x0 or hi > x1:
                    return True
                if level < y0 + TITLE_H + 4.0 and hi > x1 - TITLE_W:
                    return True
            else:
                if not (x0 + 4.0 <= level <= x1 - 4.0) or lo < y0 or hi > y1:
                    return True
                if level > x1 - TITLE_W - 4.0 and lo < y0 + TITLE_H:
                    return True
        return False

    for d in fixed:
        if d.dim_type != "linear" or not d.p1 or not d.p2 or not d.line_point:
            continue
        axis = 1 if d.orientation == "horizontal" else 0 if d.orientation == "vertical" else None
        v = _owner(d, views)
        if axis is None or v is None:
            continue
        lo, hi = _span(d, 1 - axis)
        mid = (v.box[axis] + v.box[axis + 2]) / 2
        side = 1 if d.line_point[axis] > mid else -1
        placed.setdefault((id(v), axis, side), []).append((d.line_point[axis], lo, hi))

    todo = [d for d in dims if d.dim_type == "linear" and d.p1 and d.p2
            and d.orientation in ("horizontal", "vertical") and "диаметр" not in d.notes]
    todo.sort(key=lambda d: abs(d.p2[1 - _axis(d)] - d.p1[1 - _axis(d)]))
    count = 0
    for d in todo:
        axis = _axis(d)
        v = _owner(d, views)
        if v is None:
            continue
        lo, hi = _span(d, 1 - axis)
        mid = (v.box[axis] + v.box[axis + 2]) / 2
        want = 1 if d.line_point[axis] > mid else -1
        done = False
        # ГОСТ's 10 and 7 mm first; where a view stands too close to another
        # or to the frame, closer lines rather than a size lost
        for first, gap in ((FIRST_GAP, LINE_GAP), (TIGHT_GAP, TIGHT_GAP)):
            for side in (want, -want):
                edge = v.box[axis + 2] if side > 0 else v.box[axis]
                for k in range(12):
                    level = edge + side * (first + gap * k)
                    if taken((id(v), axis, side), level, lo, hi, gap) \
                            or blocked(axis, edge, level, lo, hi, v.box):
                        continue
                    lp = list(d.line_point)
                    lp[axis] = level
                    lp[1 - axis] = (d.p1[1 - axis] + d.p2[1 - axis]) / 2
                    d.line_point = tuple(lp)
                    placed.setdefault((id(v), axis, side), []).append((level, lo, hi))
                    done = True
                    break
                if done:
                    break
            if done:
                if gap != LINE_GAP:
                    d.notes.append("тесно: ближе, чем 10/7 мм по ГОСТ")
                break
        if done:
            count += 1
        else:
            d.notes.append("не нашлось свободного места — проверьте")
    count += _arrange_radial(dims, views)
    return count


def _axis(d: ir.Dimension) -> int:
    return 1 if d.orientation == "horizontal" else 0


def _arrange_radial(dims, views) -> int:
    """The leader of each diameter and radius of a hole or rounding turned
    where its value runs into nothing: no other view, no other value."""
    boxes: list[tuple] = []
    for d in dims:
        if d.dim_type == "linear" and d.line_point and d.p1 and d.p2:
            boxes.append(_linear_text_box(d))
    count = 0
    turned: dict[tuple, list] = {}  # centre → directions its leaders take
    for d in sorted(dims, key=lambda d: -(d.radius or 0.0)):
        if d.dim_type not in ("diameter", "radius") or not d.center or not d.radius:
            continue
        own = _owner(d, views)
        best = None
        key = (round(d.center[0], 1), round(d.center[1], 1))
        used = turned.setdefault(key, [])
        for deg in (45, 135, -45, -135, 30, 150, -30, -150, 60, 120, -60, -120, 15, 165,
                    -15, -165, 75, 105, -75, -105):
            if any(abs((deg - u + 180) % 360 - 180) < 14 for u in used):
                continue  # a leader of a circle round the same centre goes there
            t = math.radians(deg)
            tip = (d.center[0] + d.radius * math.cos(t), d.center[1] + d.radius * math.sin(t))
            reach = d.radius + 6.0
            far = (d.center[0] + reach * math.cos(t), d.center[1] + reach * math.sin(t))
            w = text_width(d.text)
            box = (far[0], far[1], far[0] + w, far[1] + 4.0) if math.cos(t) >= 0 \
                else (far[0] - w, far[1], far[0], far[1] + 4.0)
            hits = sum(1 for b in boxes if _overlap(b, box)) * 3.0
            hits += sum(3.0 for v in views if v is not own and _overlap(v.box, box))
            if own is not None:  # over the part's own lines: readable, but worse
                hits += 0.2 * sum(1 for e in own.entities
                                  if _overlap(_bbox(e) or (0, 0, 0, 0), box))
            if best is None or hits < best[0]:
                best = (hits, tip, box, deg)
            if hits == 0:
                break
        if best is None:
            continue
        d.p1 = best[1]
        boxes.append(best[2])
        used.append(best[3])
        if d.dim_type == "diameter":  # its line runs through the centre to the far side
            used.append(best[3] + 180)
        count += 1
    return count


def _linear_text_box(d):
    axis = _axis(d) if d.orientation in ("horizontal", "vertical") else 1
    mid = ((d.p1[0] + d.p2[0]) / 2, (d.p1[1] + d.p2[1]) / 2)
    w = text_width(d.text)
    if axis == 1:
        y = d.line_point[1]
        return (mid[0] - w / 2, y, mid[0] + w / 2, y + 4.5)
    x = d.line_point[0]
    return (x - 4.5, mid[1] - w / 2, x, mid[1] + w / 2)


def _overlap(a, b) -> bool:
    return min(a[2], b[2]) - max(a[0], b[0]) > 0 and min(a[3], b[3]) - max(a[1], b[1]) > 0


# --- all together -----------------------------------------------------------------------------

def _same_size(a: ir.Dimension, b: ir.Dimension) -> bool:
    if a.nominal is None or b.nominal is None:
        return False
    da, db = a.text.startswith("Ø") or a.dim_type == "diameter", \
        b.text.startswith("Ø") or b.dim_type == "diameter"
    return da == db and abs(a.nominal - b.nominal) < 0.01


def _nominal_of(d: ir.Dimension, scale: float) -> None:
    m = re.search(r"\d+(?:[.,]\d+)?", d.text or "")
    if m:
        d.nominal = float(m.group(0).replace(",", "."))
    elif d.measured:
        d.nominal = round(d.measured / scale, 2)
        d.text = ("Ø" if d.dim_type == "diameter" else "R" if d.dim_type == "radius" else "") \
            + _num(d.nominal)


@dataclass
class Result:
    drawing: ir.Drawing  # the source with the new sizes (the old ones as asked)
    added: list  # the new sizes
    removed: list  # the sizes of the source taken off
    notes: list


def dimension(src: Source, replace: bool = False, scale: float | None = None) -> Result:
    """The sizes of every view, laid out by ГОСТ. ``replace``: the source's
    sizes taken off and all put anew; else they stay and only the missing
    ones are added, clear of them."""
    drawing = src.drawing
    notes = list(src.notes)
    old = [e for e in drawing.entities if isinstance(e, ir.Dimension)]
    views = find_views(drawing)
    sheet_scale = scale or src.scale or 1.0
    if not views:
        return Result(drawing, [], [], notes + ["Видов на листе не найдено: нет линий "
                                                "основного типа (K5LT_BASIC / толстых)"])
    for d in old:
        _nominal_of(d, sheet_scale)
    counter = [0]

    def nid():
        counter[0] += 1
        return f"N{counter[0]}"

    new: list[ir.Dimension] = []
    for k, v in enumerate(views, 1):
        v.scale = scale or _view_scale(v, old, sheet_scale, drawing.of_type(ir.Text))
        v.axis = _revolve_axis(v)
        has_sizes = any(_owner(o, views) is v for o in old if o.dim_type == "linear")
        made = revolve_sizes(v, nid) if v.axis else prismatic_sizes(v, nid)
        what = "тело вращения" if v.axis else "по контуру"
        kept = []
        for d in made:
            if any(_same_size(d, o) for o in new):
                continue  # given in a bigger view already
            if not replace and any(_same_size(d, o) for o in old):
                continue  # on the drawing already
            if not replace and has_sizes and CHAIN & set(d.notes):
                continue  # a view with sizes of its own: its chains are the author's
            kept.append(d)
        new += kept
        notes.append(f"Вид {k} ({v.width:.0f}×{v.height:.0f} мм на листе, масштаб "
                     f"{_scale_text(v.scale)}): {what}, размеров {len(kept)}")
    removed = old if replace else []
    if replace:
        drawing.entities = [e for e in drawing.entities if not isinstance(e, ir.Dimension)]
    room = None
    if drawing.sheet.frame_found:
        W, H = drawing.sheet.width, drawing.sheet.height
        room = (20.0, 5.0, W - 5.0, H - 5.0)  # the frame
    arrange(new, views, fixed=[] if replace else old, room=room)
    tight = [d for d in new if "тесно: ближе, чем 10/7 мм по ГОСТ" in d.notes]
    if tight:
        notes.append(f"Тесно между видами: {len(tight)} размерных линий ближе 10/7 мм — "
                     "раздвиньте виды, если нужно строго по ГОСТ")
    lost = [d for d in new if "не нашлось свободного места — проверьте" in d.notes]
    if lost:
        notes.append(f"Без свободного места остались {len(lost)} размеров — поставлены как "
                     "получилось, проверьте")
    drawing.entities += new
    return Result(drawing, new, removed, notes)


def _scale_text(s: float) -> str:
    if s >= 1:
        return f"{_num(s)}:1"
    return f"1:{_num(1 / s)}"


# --- writing the result -----------------------------------------------------------------------

def write_dxf(src_path: str | Path, result: Result, out_path: str | Path) -> None:
    """The source DXF as it is, its sizes taken off if so asked, the new
    sizes added as DXF dimensions (3,5 mm text, comma decimals)."""
    import ezdxf

    doc = ezdxf.readfile(str(src_path))
    msp = doc.modelspace()
    if result.removed:
        for e in [e for e in msp if e.dxftype() == "DIMENSION"]:
            msp.delete_entity(e)
    if "KOMPAS_AI" not in doc.dimstyles:
        doc.dimstyles.new("KOMPAS_AI", dxfattribs={
            "dimtxt": 3.5, "dimasz": 3.0, "dimexo": 0.0, "dimexe": 2.0, "dimgap": 1.0,
            "dimtad": 1, "dimtih": 0, "dimtoh": 1, "dimdec": 2, "dimdsep": ord(","),
            "dimzin": 8, "dimclrd": 3, "dimclre": 3, "dimclrt": 3})
    attribs = {"layer": "АВТОРАЗМЕРЫ"}
    if "АВТОРАЗМЕРЫ" not in doc.layers:
        doc.layers.add("АВТОРАЗМЕРЫ", color=3)
    for d in result.added:
        text = d.text.replace("Ø", "%%c")
        try:
            if d.dim_type == "linear" and d.p1 and d.p2 and d.line_point:
                angle = 0 if d.orientation == "horizontal" else 90
                dim = msp.add_linear_dim(base=d.line_point, p1=d.p1, p2=d.p2, angle=angle,
                                         text=text, dimstyle="KOMPAS_AI", dxfattribs=attribs)
            elif d.dim_type == "diameter" and d.center and d.radius and d.p1:
                dim = msp.add_diameter_dim(center=d.center, radius=d.radius,
                                           location=_beyond(d, 6.0),
                                           text=text, dimstyle="KOMPAS_AI", dxfattribs=attribs)
            elif d.dim_type == "radius" and d.center and d.radius and d.p1:
                dim = msp.add_radius_dim(center=d.center, radius=d.radius,
                                           location=_beyond(d, 6.0),
                                         text=text, dimstyle="KOMPAS_AI", dxfattribs=attribs)
            else:
                continue
            dim.render()
        except Exception:
            continue
    doc.saveas(str(out_path))


def _beyond(d: ir.Dimension, gap: float):
    """The point ``gap`` mm past the arrow of a diameter or radius, along its leader."""
    t = math.atan2(d.p1[1] - d.center[1], d.p1[0] - d.center[0])
    r = d.radius + gap
    return (d.center[0] + r * math.cos(t), d.center[1] + r * math.sin(t))


def report(result: Result) -> str:
    lines = list(result.notes)
    if result.removed:
        lines.append(f"Снято прежних размеров: {len(result.removed)}")
    lines.append(f"Поставлено размеров: {len(result.added)}")
    lines.append("Размеры поставлены по геометрии листа: допуски, посадки, шероховатость, "
                 "фаски и резьбу допишите сами; проверьте, что базы выбраны как нужно")
    return "\n".join(lines)
