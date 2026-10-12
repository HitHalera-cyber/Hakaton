"""Test drawings as DXF (sheet mm, A3 landscape, ГОСТ frame and title block).

Each part is drawn at its sheet scale; dimensions show model values
(dimlfac = 1/scale). The DXF is the exact reference for the evaluation.
"""
import math
import sys
from pathlib import Path

import ezdxf
from ezdxf.enums import TextEntityAlignment

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
W, H = 420.0, 297.0


def new_doc(scale_text, scale):
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.MM
    for name, w in (("MAIN", 50), ("THIN", 18), ("AXIS", 18)):
        doc.layers.add(name, lineweight=w)
    ds = doc.dimstyles.new("GOST")
    ds.dxf.dimtxt = 3.5
    ds.dxf.dimasz = 3.0
    ds.dxf.dimexe = 2.0
    ds.dxf.dimexo = 0.0
    ds.dxf.dimgap = 1.0
    ds.dxf.dimtad = 1
    ds.dxf.dimtih = 0
    ds.dxf.dimtoh = 0
    ds.dxf.dimdec = 2
    ds.dxf.dimzin = 8
    ds.dxf.dimadec = 0
    ds.dxf.dimdsep = ord(",")
    ds.dxf.dimlfac = 1.0 / scale
    ds.dxf.dimclrd = 0
    ds.dxf.dimlwd = 18
    ds.dxf.dimlwe = 18
    ds.dxf.dimblk = ""
    msp = doc.modelspace()
    frame(msp, scale_text)
    return doc, msp


def L(msp, a, b, layer="MAIN"):
    kw = {"layer": layer}
    if layer == "AXIS":
        kw["linetype"] = "CENTER"
    msp.add_line(a, b, dxfattribs=kw)


def frame(msp, scale_text):
    t = {"layer": "THIN"}
    msp.add_lwpolyline([(0, 0), (W, 0), (W, H), (0, H)], close=True, dxfattribs=t)
    msp.add_lwpolyline([(20, 5), (W - 5, 5), (W - 5, H - 5), (20, H - 5)], close=True,
                       dxfattribs={"layer": "MAIN"})
    x0, y0 = W - 5 - 185, 5
    msp.add_lwpolyline([(x0, y0), (x0 + 185, y0), (x0 + 185, y0 + 55), (x0, y0 + 55)],
                       close=True, dxfattribs={"layer": "MAIN"})
    for y in (15, 25, 40):
        L(msp, (x0 + 120, y0 + y), (x0 + 185, y0 + y))
    L(msp, (x0 + 120, y0), (x0 + 120, y0 + 55))
    L(msp, (x0 + 170, y0 + 25), (x0 + 170, y0 + 40))
    msp.add_text("Масштаб", height=2.5, dxfattribs={"layer": "THIN"}).set_placement(
        (x0 + 171, y0 + 41))
    msp.add_text(scale_text, height=5, dxfattribs={"layer": "THIN"}).set_placement(
        (x0 + 172, y0 + 30))
    msp.add_text("Тестовая деталь", height=5, dxfattribs={"layer": "THIN"}).set_placement(
        (x0 + 10, y0 + 20))


def rad(msp, c, r, **kw):
    return msp.add_radius_dim(c, radius=r, **kw)


def dia(msp, c, r, **kw):
    return msp.add_diameter_dim(c, radius=r, **kw)


def dim_lin(msp, p1, p2, base, angle=0, text="<>", **ov):
    msp.add_linear_dim(base=base, p1=p1, p2=p2, angle=angle, dimstyle="GOST", text=text,
                       override=ov or None, dxfattribs={"layer": "THIN"}).render()


def shaft():
    """Stepped shaft 1:1 with chamfers, a keyway and a section."""
    doc, msp = new_doc("1:1", 1.0)
    x, y = 60.0, 170.0
    steps = [(30, 20), (45, 30), (60, 36), (40, 28)]  # (length, diameter)
    profile = []
    cx = x
    for i, (length, d) in enumerate(steps):
        profile.append((cx, d))
        cx += length
    end = cx
    # outline (with 1.5x45 chamfers on the ends)
    c = 1.5
    pts_top, pts_bot = [], []
    cx = x
    for i, (length, d) in enumerate(steps):
        r = d / 2
        a, b = cx, cx + length
        if i == 0:
            pts_top += [(a, y + r - c), (a + c, y + r)]
        else:
            pts_top += [(a, y + r)]
        if i == len(steps) - 1:
            pts_top += [(b - c, y + r), (b, y + r - c)]
        else:
            pts_top += [(b, y + r)]
        cx = b
    for a, b in zip(pts_top, pts_top[1:]):
        L(msp, a, b)
        L(msp, (a[0], 2 * y - a[1]), (b[0], 2 * y - b[1]))
    L(msp, pts_top[0], (pts_top[0][0], 2 * y - pts_top[0][1]))
    L(msp, pts_top[-1], (pts_top[-1][0], 2 * y - pts_top[-1][1]))
    cx = x
    for i, (length, d) in enumerate(steps):  # shoulder lines
        if i:
            r = max(d, steps[i - 1][1]) / 2
            L(msp, (cx, y + r), (cx, y - r))
        cx += length
    L(msp, (x + c, y + 10), (x + c, y - 10))
    L(msp, (end - c, y + 14), (end - c, y - 14))
    L(msp, (x - 5, y), (end + 5, y), "AXIS")
    # keyway on the Ø36 step: slot 25 x 10 with round ends
    kx0, kx1 = x + 75 + 18, x + 75 + 18 + 25
    msp.add_arc((kx0 + 5, y), 5, 90, 270, dxfattribs={"layer": "MAIN"})
    msp.add_arc((kx1 - 5, y), 5, 270, 90, dxfattribs={"layer": "MAIN"})
    L(msp, (kx0 + 5, y + 5), (kx1 - 5, y + 5))
    L(msp, (kx0 + 5, y - 5), (kx1 - 5, y - 5))
    # dimensions: chain of lengths and diameters
    cx = x
    for length, d in steps:
        dim_lin(msp, (cx, y - d / 2), (cx + length, y - d / 2), (cx, y - 32))
        cx += length
    dim_lin(msp, (x, y + 10 - c), (end, y + 14 - c), (x, y + 38))
    cx = x
    for length, d in steps:
        mid = cx + length / 2 + (6 if d == 36 else 0)
        dim_lin(msp, (mid, y + d / 2), (mid, y - d / 2), (mid, y), angle=90, text="%%c<>")
        cx += length
    dim_lin(msp, (kx0, y), (kx1, y), (kx0, y + 26))
    rad(msp, (kx0 + 5, y), 5, angle=135, dimstyle="GOST",
                       dxfattribs={"layer": "THIN"}).render()
    # section A-A of the Ø36 step with a key slot, hatched
    sx, sy, r = 330.0, 170.0, 18.0
    t = 4.0  # key depth
    half = 5.0
    yk = sy + math.sqrt(r * r - half * half)
    ang = math.degrees(math.atan2(yk - sy, half))
    msp.add_arc((sx, sy), r, ang, 180 - ang, dxfattribs={"layer": "MAIN"}) if False else None
    msp.add_arc((sx, sy), r, 180 - ang, 360 + ang, dxfattribs={"layer": "MAIN"})
    L(msp, (sx - half, yk), (sx - half, sy + r - t))
    L(msp, (sx + half, yk), (sx + half, sy + r - t))
    L(msp, (sx - half, sy + r - t), (sx + half, sy + r - t))
    L(msp, (sx - r - 4, sy), (sx + r + 4, sy), "AXIS")
    L(msp, (sx, sy - r - 4), (sx, sy + r + 4), "AXIS")
    h = msp.add_hatch(dxfattribs={"layer": "THIN"})
    h.set_pattern_fill("ANSI31", scale=1.0, angle=0)
    path = h.paths.add_edge_path()
    path.add_arc((sx, sy), r, 180 - ang, 360 + ang)
    path.add_line((sx + half, yk), (sx + half, sy + r - t))
    path.add_line((sx + half, sy + r - t), (sx - half, sy + r - t))
    path.add_line((sx - half, sy + r - t), (sx - half, yk))
    dia(msp, (sx, sy), 18, angle=225, dimstyle="GOST",
                         dxfattribs={"layer": "THIN"}).render()
    dim_lin(msp, (sx - half, sy + r - t), (sx + half, sy + r - t), (sx, sy + r + 12))
    msp.add_text("А-А", height=5, dxfattribs={"layer": "THIN"}).set_placement((sx - 6, sy + 45))
    return doc


def flange():
    """Flange 1:2: front view with 6 holes on a pitch circle, half section."""
    doc, msp = new_doc("1:2", 0.5)
    k = 0.5
    cx, cy = 130.0, 160.0
    D, Dp, d, dh = 200.0, 160.0, 60.0, 18.0
    msp.add_circle((cx, cy), D / 2 * k, dxfattribs={"layer": "MAIN"})
    msp.add_circle((cx, cy), d / 2 * k, dxfattribs={"layer": "MAIN"})
    msp.add_circle((cx, cy), Dp / 2 * k, dxfattribs={"layer": "AXIS", "linetype": "CENTER"})
    for i in range(6):
        a = math.radians(30 + 60 * i)
        hx, hy = cx + Dp / 2 * k * math.cos(a), cy + Dp / 2 * k * math.sin(a)
        msp.add_circle((hx, hy), dh / 2 * k, dxfattribs={"layer": "MAIN"})
    L(msp, (cx - 58, cy), (cx + 58, cy), "AXIS")
    L(msp, (cx, cy - 58), (cx, cy + 58), "AXIS")
    dia(msp, (cx, cy), D / 2 * k, angle=60, dimstyle="GOST",
                         dxfattribs={"layer": "THIN"}).render()
    dia(msp, (cx, cy), d / 2 * k, angle=200, dimstyle="GOST",
                         dxfattribs={"layer": "THIN"}).render()
    dia(msp, (cx + Dp / 2 * k * math.cos(math.radians(30)),
                          cy + Dp / 2 * k * math.sin(math.radians(30))), dh / 2 * k, angle=30,
                         dimstyle="GOST", text="6 отв. <>", dxfattribs={"layer": "THIN"}).render()
    # angular 60° between two holes
    p30 = (cx + 40 * math.cos(math.radians(30)), cy + 40 * math.sin(math.radians(30)))
    p90 = (cx, cy + 40)
    msp.add_angular_dim_3p(base=(cx + 60 * math.cos(math.radians(60)), cy + 60 * math.sin(math.radians(60))),
                           center=(cx, cy), p1=p30, p2=p90, dimstyle="GOST",
                           dxfattribs={"layer": "THIN"}).render()
    # side view: half section, thickness 20, hub 40 long Ø100
    sx = 250.0
    T, hub, Dh = 20.0, 40.0, 100.0
    top = [(sx, cy + D / 2 * k), (sx + T * k, cy + D / 2 * k), (sx + T * k, cy + Dh / 2 * k),
           (sx + hub * k, cy + Dh / 2 * k), (sx + hub * k, cy - Dh / 2 * k),
           (sx + T * k, cy - Dh / 2 * k), (sx + T * k, cy - D / 2 * k), (sx, cy - D / 2 * k)]
    for a, b in zip(top, top[1:] + top[:1]):
        L(msp, a, b)
    L(msp, (sx, cy + d / 2 * k), (sx + hub * k, cy + d / 2 * k))
    L(msp, (sx, cy - d / 2 * k), (sx + hub * k, cy - d / 2 * k))
    for s in (1, -1):
        hy = cy + s * Dp / 2 * k
        L(msp, (sx, hy + dh / 2 * k), (sx + T * k, hy + dh / 2 * k))
        L(msp, (sx, hy - dh / 2 * k), (sx + T * k, hy - dh / 2 * k))
        L(msp, (sx - 3, hy), (sx + T * k + 3, hy), "AXIS")
    L(msp, (sx - 5, cy), (sx + hub * k + 5, cy), "AXIS")
    # hatch the upper half (section): between d/2 and the hole, and above the hole
    for y0, y1, x1 in ((cy + d / 2 * k, cy + (Dp - dh) / 2 * k, None),
                       (cy + (Dp + dh) / 2 * k, cy + D / 2 * k, sx + T * k)):
        xr = x1 if x1 else None
        h = msp.add_hatch(dxfattribs={"layer": "THIN"})
        h.set_pattern_fill("ANSI31", scale=1.0)
        if x1:
            h.paths.add_polyline_path([(sx, y0), (x1, y0), (x1, y1), (sx, y1)])
        else:
            h.paths.add_polyline_path([(sx, y0), (sx + hub * k, y0), (sx + hub * k, cy + Dh / 2 * k),
                                       (sx + T * k, cy + Dh / 2 * k), (sx + T * k, y1), (sx, y1)])
    dim_lin(msp, (sx, cy - D / 2 * k), (sx + T * k, cy - D / 2 * k), (sx, cy - D / 2 * k - 10))
    dim_lin(msp, (sx, cy - D / 2 * k), (sx + hub * k, cy - Dh / 2 * k), (sx, cy - D / 2 * k - 20))
    dim_lin(msp, (sx + hub * k, cy + Dh / 2 * k), (sx + hub * k, cy - Dh / 2 * k),
            (sx + hub * k + 12, cy), angle=90, text="%%c<>")
    return doc


def plate():
    """Bracket plate 2:1: rounded corners, slot, chamfer, angled edge."""
    doc, msp = new_doc("2:1", 2.0)
    k = 2.0
    ox, oy = 80.0, 90.0
    w, h, r = 70.0, 45.0, 6.0
    ch = 10.0  # 30° chamfer at top right: cut 10 along x
    cut_y = ch * math.tan(math.radians(30))
    P = lambda x, y: (ox + x * k, oy + y * k)
    L(msp, P(r, 0), P(w - r, 0))
    msp.add_arc(P(w - r, r), r * k, 270, 360, dxfattribs={"layer": "MAIN"})
    L(msp, P(w, r), P(w, h - cut_y))
    L(msp, P(w, h - cut_y), P(w - ch, h))
    L(msp, P(w - ch, h), P(r, h))
    msp.add_arc(P(r, h - r), r * k, 90, 180, dxfattribs={"layer": "MAIN"})
    L(msp, P(0, h - r), P(0, r))
    msp.add_arc(P(r, r), r * k, 180, 270, dxfattribs={"layer": "MAIN"})
    # holes Ø8 and a slot 20x8
    for hx, hy in ((15, 15), (15, 32)):
        msp.add_circle(P(hx, hy), 4 * k, dxfattribs={"layer": "MAIN"})
        L(msp, P(hx - 7, hy), P(hx + 7, hy), "AXIS")
        L(msp, P(hx, hy - 7), P(hx, hy + 7), "AXIS")
    sx0, sx1, sy = 35.0, 55.0, 20.0
    msp.add_arc(P(sx0, sy), 4 * k, 90, 270, dxfattribs={"layer": "MAIN"})
    msp.add_arc(P(sx1, sy), 4 * k, 270, 90, dxfattribs={"layer": "MAIN"})
    L(msp, P(sx0, sy + 4), P(sx1, sy + 4))
    L(msp, P(sx0, sy - 4), P(sx1, sy - 4))
    L(msp, P(sx0 - 7, sy), P(sx1 + 7, sy), "AXIS")
    dim_lin(msp, P(0, r), P(w, r), P(0, -12))
    dim_lin(msp, P(w, r), P(w, h - cut_y), P(w + 12, 0), angle=90)
    dim_lin(msp, P(0, h - r), P(r, h), P(0, h + 10)) if False else None
    dim_lin(msp, P(0, 0), P(15, 15), P(0, -6) if False else P(0, 54), text="<>")
    dim_lin(msp, P(15, 15), P(15, 32), P(-10, 15), angle=90)
    dim_lin(msp, P(sx0, sy), P(sx1, sy), P(sx0, 31))
    dia(msp, P(15, 15), 4 * k, angle=-45, dimstyle="GOST", text="2 отв. <>",
                         dxfattribs={"layer": "THIN"}).render()
    rad(msp, P(w - r, r), r * k, angle=-45, dimstyle="GOST",
                       dxfattribs={"layer": "THIN"}).render()
    rad(msp, P(sx1, sy), 4 * k, angle=45, dimstyle="GOST",
                       dxfattribs={"layer": "THIN"}).render()
    # angular 30° of the chamfer: between the top edge and the chamfer
    v = P(w - ch, h)
    L(msp, v, (v[0] + 22, v[1]), "THIN")  # extension of the top edge
    msp.add_angular_dim_2l(base=(v[0] + 18 * math.cos(math.radians(-15)),
                                 v[1] + 18 * math.sin(math.radians(-15))),
                           line1=(v, P(w, h - cut_y)), line2=(v, (v[0] + 22, v[1])),
                           dimstyle="GOST", dxfattribs={"layer": "THIN"}).render()
    # aligned dimension of the chamfer length
    a = P(w, h - cut_y)
    b = P(w - ch, h)
    msp.add_aligned_dim(p1=a, p2=b, distance=-8, dimstyle="GOST",
                        dxfattribs={"layer": "THIN"}).render()
    return doc


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, f in (("shaft", shaft), ("flange", flange), ("plate", plate)):
        doc = f()
        doc.saveas(OUT / f"{name}.dxf")
        print("written", name)
