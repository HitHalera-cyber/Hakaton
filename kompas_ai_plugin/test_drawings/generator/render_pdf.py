"""Plot a DXF (sheet mm) to a vector PDF like a CAD 'print to PDF' with TTF text.

Options mimic different exporters:
  --dash array|pieces   centre lines as a PDF dash array (SolidWorks/AutoCAD)
                        or as separate dash strokes (KOMPAS)
  --curves bezier|poly  circles/arcs as Bezier curves or short chords
  --arrows fill|outline filled triangles or closed outlines
"""
import argparse
import math

import ezdxf
import pymupdf
from ezdxf.render import hatching

PT = 72 / 25.4
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
CENTER = [12.0, -3.0, 0.0, -3.0]  # dash, gap, dot, gap (mm)


def xy(v):
    return (float(v[0]), float(v[1]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dxf")
    ap.add_argument("pdf")
    ap.add_argument("--dash", default="array")
    ap.add_argument("--curves", default="bezier")
    ap.add_argument("--arrows", default="fill")
    ap.add_argument("--rotate-text", action="store_true")
    a = ap.parse_args()
    doc = ezdxf.readfile(a.dxf)
    W, H = 420.0, 297.0
    out = pymupdf.open()
    page = out.new_page(width=W * PT, height=H * PT)
    page.insert_font(fontname="dv", fontfile=FONT)
    font = pymupdf.Font(fontfile=FONT)

    def P(p):
        return pymupdf.Point(p[0] * PT, (H - p[1]) * PT)

    def width_of(e):
        return 0.5 if e.dxf.layer == "MAIN" else 0.25

    def is_axis(e):
        return (e.dxf.get("linetype") or "").upper() == "CENTER"

    def stroke(points, w, axis=False, closed=False):
        sh = page.new_shape()
        if axis and a.dash == "pieces":
            for seg in dash_pieces(points):
                sh.draw_polyline([P(p) for p in seg])
            sh.finish(color=(0, 0, 0), width=w * PT, closePath=False, lineCap=1)
        else:
            if a.curves == "bezier" and isinstance(points, tuple):  # ("arc", c, r, a0, a1)
                arc_bezier(sh, *points[1:])
            else:
                sh.draw_polyline([P(p) for p in points])
            dashes = None
            if axis:
                dashes = "[%g %g %g %g] 0" % (12 * PT, 3 * PT, 0.5 * PT, 3 * PT)
            sh.finish(color=(0, 0, 0), width=w * PT, closePath=closed, dashes=dashes, lineCap=1)
        sh.commit()

    def arc_bezier(sh, c, r, a0, a1):
        sweep = (a1 - a0) % 360 or 360
        n = max(1, math.ceil(sweep / 90))
        step = math.radians(sweep / n)
        k = 4 / 3 * math.tan(step / 4)
        t = math.radians(a0)
        for _ in range(n):
            p0 = (c[0] + r * math.cos(t), c[1] + r * math.sin(t))
            p3 = (c[0] + r * math.cos(t + step), c[1] + r * math.sin(t + step))
            p1 = (p0[0] - k * r * math.sin(t), p0[1] + k * r * math.cos(t))
            p2 = (p3[0] + k * r * math.sin(t + step), p3[1] - k * r * math.cos(t + step))
            sh.draw_bezier(P(p0), P(p1), P(p2), P(p3))
            t += step

    def arc_points(c, r, a0, a1):
        sweep = (a1 - a0) % 360 or 360
        n = max(8, int(sweep / 3))
        return [(c[0] + r * math.cos(math.radians(a0 + sweep * i / n)),
                 c[1] + r * math.sin(math.radians(a0 + sweep * i / n))) for i in range(n + 1)]

    def curve(c, r, a0, a1):
        return ("arc", c, r, a0, a1) if a.curves == "bezier" else arc_points(c, r, a0, a1)

    def dash_pieces(points):
        if isinstance(points, tuple):
            points = arc_points(*points[1:])
        pattern = [12.0, 3.0, 0.5, 3.0]
        total = sum(math.dist(p, q) for p, q in zip(points, points[1:]))
        # centre the pattern: start with a long dash
        pieces, i, pos, on = [], 0, 0.0, True
        cur = [points[0]]
        seg_i, seg_pos = 0, 0.0
        dist_left = pattern[0]
        state = 0

        def walk(points):
            for p, q in zip(points, points[1:]):
                yield p, q, math.dist(p, q)
        acc = []
        cur = [points[0]]
        for p, q, d in walk(points):
            t = 0.0
            while d - t > dist_left:
                t += dist_left
                f = t / d
                x = (p[0] + (q[0] - p[0]) * f, p[1] + (q[1] - p[1]) * f)
                if state % 2 == 0:
                    cur.append(x)
                    acc.append(cur)
                cur = [x]
                state = (state + 1) % 4
                dist_left = pattern[state]
            dist_left -= d - t
            if state % 2 == 0:
                cur.append(q)
            else:
                cur = [q]
        if state % 2 == 0 and len(cur) > 1:
            acc.append(cur)
        return acc

    def text(value, ins, h, rot, halign="left", valign="baseline"):
        if not value.strip():
            return
        size = h / 0.72
        wdt = font.text_length(value, fontsize=size) / PT
        dx = {"left": 0, "center": -wdt / 2, "right": -wdt}[halign]
        dy = {"baseline": 0, "bottom": h * 0.25, "middle": -h / 2, "top": -h}[valign]
        ang = math.radians(rot)
        x = ins[0] + dx * math.cos(ang) - dy * math.sin(ang)
        y = ins[1] + dx * math.sin(ang) + dy * math.cos(ang)
        p = P((x, y))
        page.insert_text(p, value, fontsize=size * PT, fontname="dv",
                         morph=(p, pymupdf.Matrix(rot)) if rot else None)

    def draw(e, w=None):
        t = e.dxftype()
        lw = w or width_of(e)
        if t == "LINE":
            stroke([xy(e.dxf.start), xy(e.dxf.end)], lw, is_axis(e))
        elif t == "CIRCLE":
            stroke(curve(xy(e.dxf.center), e.dxf.radius, 0, 360), lw, is_axis(e))
        elif t == "ARC":
            stroke(curve(xy(e.dxf.center), e.dxf.radius, e.dxf.start_angle, e.dxf.end_angle), lw,
                   is_axis(e))
        elif t == "LWPOLYLINE":
            pts = [p[:2] for p in e.get_points()]
            if e.closed:
                pts.append(pts[0])
            stroke(pts, lw)
        elif t in ("SOLID", "TRACE"):
            v = [e.dxf.vtx0, e.dxf.vtx1, e.dxf.vtx3, e.dxf.vtx2]
            pts = []
            for q in v:
                if not pts or math.dist(pts[-1], xy(q)) > 1e-9:
                    pts.append(xy(q))
            sh = page.new_shape()
            sh.draw_polyline([P(p) for p in pts] + [P(pts[0])])
            if a.arrows == "fill":
                sh.finish(color=None, fill=(0, 0, 0), closePath=True)
            else:
                sh.finish(color=(0, 0, 0), width=0.25 * PT, closePath=True)
            sh.commit()
        elif t == "TEXT":
            text(e.dxf.text, xy(e.dxf.insert), e.dxf.height, e.dxf.get("rotation", 0))
        elif t == "MTEXT":
            ap_ = e.dxf.get("attachment_point", 1)
            hal = {0: "left", 1: "center", 2: "right"}[(ap_ - 1) % 3]
            val = {0: "top", 1: "middle", 2: "bottom"}[(ap_ - 1) // 3]
            text(e.plain_text().replace("\n", " "), xy(e.dxf.insert), e.dxf.char_height,
                 e.dxf.get("rotation", 0), hal, val)
        elif t == "HATCH":
            sh = page.new_shape()
            for s0, s1 in hatching.hatch_entity(e):
                sh.draw_line(P(xy(s0)), P(xy(s1)))
            sh.finish(color=(0, 0, 0), width=0.25 * PT)
            sh.commit()
        elif t == "INSERT":
            for sub in e.virtual_entities():
                draw(sub, lw)
        elif t == "DIMENSION":
            for sub in e.virtual_entities():
                draw(sub, 0.25)

    for e in doc.modelspace():
        draw(e)
    out.save(a.pdf)


if __name__ == "__main__":
    main()
