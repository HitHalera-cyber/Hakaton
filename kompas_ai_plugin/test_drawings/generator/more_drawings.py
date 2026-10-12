"""More test drawings: prismatic parts (plate, bracket, gasket), a bush, a
washer with a table. DXF in sheet mm, A3, ГОСТ frame (make_drawings.py)."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from make_drawings import L, dia, dim_lin, new_doc, rad  # noqa: E402

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ".")


def rounded_rect(msp, x0, y0, w, h, r):
    L(msp, (x0 + r, y0), (x0 + w - r, y0))
    L(msp, (x0 + w, y0 + r), (x0 + w, y0 + h - r))
    L(msp, (x0 + w - r, y0 + h), (x0 + r, y0 + h))
    L(msp, (x0, y0 + h - r), (x0, y0 + r))
    for (cx, cy), a in (((x0 + w - r, y0 + r), 270), ((x0 + w - r, y0 + h - r), 0),
                        ((x0 + r, y0 + h - r), 90), ((x0 + r, y0 + r), 180)):
        msp.add_arc((cx, cy), r, a, a + 90, dxfattribs={"layer": "MAIN"})


def hole(msp, c, r, mark=None):
    msp.add_circle(c, r, dxfattribs={"layer": "MAIN"})
    m = mark or r + 4
    L(msp, (c[0] - m, c[1]), (c[0] + m, c[1]), "AXIS")
    L(msp, (c[0], c[1] - m), (c[0], c[1] + m), "AXIS")


def plita():
    """Плита 120×80×12, 1:1: four holes Ø10, a window 40×20 R5, corners R8;
    the side view gives the thickness."""
    doc, msp = new_doc("1:1", 1.0)
    x0, y0, w, h = 60.0, 110.0, 120.0, 80.0
    rounded_rect(msp, x0, y0, w, h, 8.0)
    rounded_rect(msp, x0 + 40, y0 + 30, 40.0, 20.0, 5.0)
    for hx, hy in ((15, 15), (105, 15), (15, 65), (105, 65)):
        hole(msp, (x0 + hx, y0 + hy), 5.0)
    # side view: 12 wide, on the same height
    sx = x0 + w + 40
    for a, b in (((sx, y0), (sx + 12, y0)), ((sx + 12, y0), (sx + 12, y0 + h)),
                 ((sx + 12, y0 + h), (sx, y0 + h)), ((sx, y0 + h), (sx, y0))):
        L(msp, a, b)
    dim_lin(msp, (x0, y0), (x0 + w, y0), (x0, y0 - 15))
    dim_lin(msp, (x0 + w, y0), (x0 + w, y0 + h), (x0 + w + 15, y0), angle=90)
    dim_lin(msp, (sx, y0 + h), (sx + 12, y0 + h), (sx, y0 + h + 12))
    dim_lin(msp, (x0, y0 + 65), (x0 + 15, y0 + 65), (x0, y0 + h + 10))
    dim_lin(msp, (x0 + 15, y0), (x0 + 15, y0 + 15), (x0 - 12, y0), angle=90)
    dim_lin(msp, (x0 + 40, y0 + 50), (x0 + 80, y0 + 50), (x0 + 40, y0 + 60))
    dim_lin(msp, (x0 + 80, y0 + 30), (x0 + 80, y0 + 50), (x0 + 92, y0 + 30), angle=90)
    dia(msp, (x0 + 105, y0 + 65), 5.0, angle=45, dimstyle="GOST", text="4 отв. <>",
        dxfattribs={"layer": "THIN"}).render()
    rad(msp, (x0 + 8, y0 + 8), 8.0, angle=225, dimstyle="GOST",
        dxfattribs={"layer": "THIN"}).render()
    rad(msp, (x0 + 75, y0 + 45), 5.0, angle=45, dimstyle="GOST",
        dxfattribs={"layer": "THIN"}).render()
    return doc


def kronshtein():
    """Кронштейн, 1:1: an L outline 100×60 (legs 20 and 30 thick), inner
    corner R10, holes Ø9 ×2 and Ø12; the top view below gives the width 40."""
    doc, msp = new_doc("1:1", 1.0)
    x0, y0 = 70.0, 150.0
    r = 10.0
    pts = [(x0, y0), (x0 + 100, y0), (x0 + 100, y0 + 20), (x0 + 30 + r, y0 + 20)]
    for a, b in zip(pts, pts[1:]):
        L(msp, a, b)
    msp.add_arc((x0 + 30 + r, y0 + 20 + r), r, 180, 270, dxfattribs={"layer": "MAIN"})
    L(msp, (x0 + 30, y0 + 20 + r), (x0 + 30, y0 + 60))
    L(msp, (x0 + 30, y0 + 60), (x0, y0 + 60))
    L(msp, (x0, y0 + 60), (x0, y0))
    for hx in (60.0, 85.0):
        hole(msp, (x0 + hx, y0 + 10), 4.5)
    hole(msp, (x0 + 15, y0 + 45), 6.0)
    # top view below: 100 × 40
    ty = y0 - 70
    for a, b in (((x0, ty), (x0 + 100, ty)), ((x0 + 100, ty), (x0 + 100, ty + 40)),
                 ((x0 + 100, ty + 40), (x0, ty + 40)), ((x0, ty + 40), (x0, ty))):
        L(msp, a, b)
    L(msp, (x0 + 30, ty), (x0 + 30, ty + 40))
    dim_lin(msp, (x0, y0 + 60), (x0 + 100, y0 + 20), (x0, y0 + 75))
    dim_lin(msp, (x0, y0), (x0, y0 + 60), (x0 - 15, y0), angle=90)
    dim_lin(msp, (x0 + 100, y0), (x0 + 100, y0 + 20), (x0 + 112, y0), angle=90)
    dim_lin(msp, (x0, y0 + 60), (x0 + 30, y0 + 60), (x0, y0 + 67))
    dim_lin(msp, (x0 + 100, ty), (x0 + 100, ty + 40), (x0 + 112, ty), angle=90)
    dim_lin(msp, (x0 + 60, y0 + 10), (x0 + 85, y0 + 10), (x0 + 60, y0 - 12))
    dia(msp, (x0 + 85, y0 + 10), 4.5, angle=45, dimstyle="GOST", text="2 отв. <>",
        dxfattribs={"layer": "THIN"}).render()
    dia(msp, (x0 + 15, y0 + 45), 6.0, angle=45, dimstyle="GOST",
        dxfattribs={"layer": "THIN"}).render()
    rad(msp, (x0 + 30 + r, y0 + 20 + r), r, angle=225, dimstyle="GOST",
        dxfattribs={"layer": "THIN"}).render()
    return doc


def prokladka():
    """Прокладка 90×50 R5, Ø30 in the middle, four holes Ø6; thickness by
    the note «s2»."""
    doc, msp = new_doc("1:1", 1.0)
    x0, y0 = 80.0, 140.0
    rounded_rect(msp, x0, y0, 90.0, 50.0, 5.0)
    hole(msp, (x0 + 45, y0 + 25), 15.0, 19.0)
    for hx, hy in ((10, 10), (80, 10), (10, 40), (80, 40)):
        hole(msp, (x0 + hx, y0 + hy), 3.0)
    dim_lin(msp, (x0, y0), (x0 + 90, y0), (x0, y0 - 15))
    dim_lin(msp, (x0 + 90, y0), (x0 + 90, y0 + 50), (x0 + 105, y0), angle=90)
    dim_lin(msp, (x0 + 10, y0 + 40), (x0 + 80, y0 + 40), (x0 + 10, y0 + 62))
    dim_lin(msp, (x0 + 10, y0 + 10), (x0 + 10, y0 + 40), (x0 - 12, y0 + 10), angle=90)
    dia(msp, (x0 + 45, y0 + 25), 15.0, angle=45, dimstyle="GOST",
        dxfattribs={"layer": "THIN"}).render()
    dia(msp, (x0 + 80, y0 + 10), 3.0, angle=-45, dimstyle="GOST", text="4 отв. <>",
        dxfattribs={"layer": "THIN"}).render()
    msp.add_text("s2", height=5, dxfattribs={"layer": "THIN"}).set_placement((x0 + 100, y0 + 70))
    return doc


def hatch_rect(msp, pts):
    h = msp.add_hatch(dxfattribs={"layer": "THIN"})
    h.set_pattern_fill("ANSI31", scale=1.0)
    h.paths.add_polyline_path(pts)


def vtulka():
    """Втулка Ø40/Ø25 × 50, chamfers 1×45°, 2:1, in full section."""
    doc, msp = new_doc("2:1", 2.0)
    k = 2.0
    x0, y = 80.0, 160.0
    R, r, Lg, c = 20.0 * k, 12.5 * k, 50.0 * k, 1.0 * k
    for s in (1, -1):
        out = [(x0, y + s * (R - c)), (x0 + c, y + s * R), (x0 + Lg - c, y + s * R),
               (x0 + Lg, y + s * (R - c))]
        for a, b in zip(out, out[1:]):
            L(msp, a, b)
        L(msp, (x0, y + s * r), (x0 + Lg, y + s * r))
        L(msp, (x0, y + s * r), (x0, y + s * (R - c)))
        L(msp, (x0 + Lg, y + s * r), (x0 + Lg, y + s * (R - c)))
        L(msp, (x0 + c, y + s * r), (x0 + c, y + s * R))
        L(msp, (x0 + Lg - c, y + s * r), (x0 + Lg - c, y + s * R))
        hatch_rect(msp, [(x0, y + s * r), (x0 + Lg, y + s * r), (x0 + Lg, y + s * (R - c)),
                         (x0 + Lg - c, y + s * R), (x0 + c, y + s * R), (x0, y + s * (R - c))])
    L(msp, (x0 - 6, y), (x0 + Lg + 6, y), "AXIS")
    dim_lin(msp, (x0 + 70, y + R), (x0 + 70, y - R), (x0 + 70, y), angle=90, text="%%c<>")
    dim_lin(msp, (x0 + 30, y + r), (x0 + 30, y - r), (x0 + 30, y), angle=90, text="%%c<>")
    dim_lin(msp, (x0, y - R + c), (x0 + Lg, y - R + c), (x0, y - R - 15))
    return doc


def shaiba():
    """Шайба Ø36/Ø17 × 3, 2:1, in section, and a table of its parameters."""
    doc, msp = new_doc("2:1", 2.0)
    k = 2.0
    x0, y = 100.0, 170.0
    R, r, t = 18.0 * k, 8.5 * k, 3.0 * k
    for s in (1, -1):
        pts = [(x0, y + s * r), (x0 + t, y + s * r), (x0 + t, y + s * R), (x0, y + s * R)]
        for a, b in zip(pts, pts[1:] + pts[:1]):
            L(msp, a, b)
        hatch_rect(msp, pts)
    L(msp, (x0 - 6, y), (x0 + t + 6, y), "AXIS")
    dim_lin(msp, (x0 + t, y + R), (x0 + t, y - R), (x0 + t + 20, y), angle=90, text="%%c<>")
    dim_lin(msp, (x0, y + r), (x0, y - r), (x0 - 15, y), angle=90, text="%%c<>")
    dim_lin(msp, (x0, y + R), (x0 + t, y + R), (x0, y + R + 12))
    # the table: 3 columns × 4 rows, 25 × 8
    tx, ty, cw, rh = 230.0, 250.0, (40.0, 25.0, 25.0), 8.0
    rows = [("Параметр", "Знач.", "Ед."), ("Диаметр", "36", "мм"), ("Отверстие", "17", "мм"),
            ("Толщина", "3", "мм")]
    xs = [tx]
    for wdt in cw:
        xs.append(xs[-1] + wdt)
    for i in range(len(rows) + 1):
        L(msp, (xs[0], ty - i * rh), (xs[-1], ty - i * rh))
    for x in xs:
        L(msp, (x, ty), (x, ty - len(rows) * rh))
    for i, row in enumerate(rows):
        for j, text in enumerate(row):
            msp.add_text(text, height=3.5, dxfattribs={"layer": "THIN"}).set_placement(
                (xs[j] + 1.5, ty - (i + 1) * rh + 2.2))
    return doc


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, f in (("plita", plita), ("kronshtein", kronshtein), ("prokladka", prokladka),
                    ("vtulka", vtulka), ("shaiba", shaiba)):
        f().saveas(OUT / f"{name}.dxf")
        print("written", name)
