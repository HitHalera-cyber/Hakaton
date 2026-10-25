"""A clean drawing redrawn the way AutoCAD and its clones plot lines, its
text kept:

  filled  — main lines as filled bands (wide polylines, plotted lineweights),
            thin lines as hairlines
  outline — main lines as the band's outline stroked with a hairline
  bundle  — main lines as 3 parallel hairlines across the width
  hair    — every line a hairline of one width (lineweights not plotted)
  chords  — curves as chords, every straight line cut into 2–3 pieces
"""
import math

import pymupdf

VARIANTS = ("filled", "outline", "bundle", "hair", "chords")
def flatten(path):
    """Polylines (lists of points) of a drawing path; curves as chords."""
    polys, cur = [], []

    def push(pts):
        nonlocal cur
        if cur and abs(cur[-1].x - pts[0].x) < 1e-6 and abs(cur[-1].y - pts[0].y) < 1e-6:
            cur += pts[1:]
        else:
            if len(cur) > 1:
                polys.append(cur)
            cur = list(pts)

    for it in path["items"]:
        if it[0] == "l":
            push([it[1], it[2]])
        elif it[0] == "c":
            p0, p1, p2, p3 = it[1:5]
            n = 8
            pts = []
            for i in range(n + 1):
                t = i / n
                x = (1-t)**3*p0.x + 3*(1-t)**2*t*p1.x + 3*(1-t)*t*t*p2.x + t**3*p3.x
                y = (1-t)**3*p0.y + 3*(1-t)**2*t*p1.y + 3*(1-t)*t*t*p2.y + t**3*p3.y
                pts.append(pymupdf.Point(x, y))
            push(pts)
        elif it[0] == "re":
            r = it[1]
            push([r.tl, r.tr, r.br, r.bl, r.tl])
        elif it[0] == "qu":
            q = it[1]
            push([q.ul, q.ur, q.lr, q.ll, q.ul])
    if len(cur) > 1:
        polys.append(cur)
    return polys


def offset(poly, d):
    """The polyline moved sideways by d (mitred joints)."""
    out = []
    n = len(poly)
    for i in range(n):
        p = poly[i]
        normals = []
        for a, b in ((poly[i - 1], p) if i > 0 else (None, None), (p, poly[i + 1]) if i < n - 1 else (None, None)):
            if a is None:
                continue
            dx, dy = b.x - a.x, b.y - a.y
            L = math.hypot(dx, dy) or 1.0
            normals.append((-dy / L, dx / L))
        nx = sum(v[0] for v in normals) / len(normals)
        ny = sum(v[1] for v in normals) / len(normals)
        L = math.hypot(nx, ny) or 1.0
        cos = L if len(normals) == 2 else 1.0  # true mitre: d / cos(half turn)
        k = d / max(cos, 0.25)
        out.append(pymupdf.Point(p.x + nx / L * k, p.y + ny / L * k))
    return out


def band(poly, w):
    """Closed outline of a polyline stroked w wide (flat caps)."""
    return offset(poly, w / 2) + list(reversed(offset(poly, -w / 2)))


def split(poly, k):
    """Every straight piece cut into k collinear pieces."""
    out = []
    for a, b in zip(poly, poly[1:]):
        for i in range(k):
            t0, t1 = i / k, (i + 1) / k
            out.append([pymupdf.Point(a.x + (b.x - a.x) * t0, a.y + (b.y - a.y) * t0),
                        pymupdf.Point(a.x + (b.x - a.x) * t1, a.y + (b.y - a.y) * t1)])
    return out


def variant(src_pdf, name, out_pdf):
    """Write ``src_pdf`` redrawn the ``name`` way to ``out_pdf``."""
    src = pymupdf.open(str(src_pdf))
    doc = pymupdf.open()
    doc.insert_pdf(src)
    page = doc[0]
    drawings = page.get_drawings()
    # the vector art away, the text stays
    page.add_redact_annot(page.rect)
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE,
                          graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED,
                          text=pymupdf.PDF_REDACT_TEXT_NONE)
    shape = page.new_shape()
    for path in drawings:
        color = path.get("color") or (0, 0, 0)
        w = path.get("width") or 0.0
        fill = path.get("fill")
        polys = flatten(path)
        if fill is not None:  # arrowheads and the like stay fills
            for poly in polys:
                shape.draw_polyline(poly)
            shape.finish(fill=fill, color=None, closePath=True)
            continue
        if path.get("color") is None:
            continue
        dashes = path.get("dashes")
        wide = w > 1.0  # pt: main lines; thin ones plotted as hairlines
        if name in ("filled", "outline", "bundle") and not wide:
            for poly in polys:
                shape.draw_polyline(poly)
            shape.finish(color=color, width=0.1, dashes=dashes, closePath=False)
            continue
        if name == "filled" and wide:
            for poly in polys:
                shape.draw_polyline(band(poly, w))
                shape.finish(fill=color, color=None, closePath=True)
            continue
        if name == "outline" and wide:
            for poly in polys:
                shape.draw_polyline(band(poly, w) + [band(poly, w)[0]])
                shape.finish(color=color, width=0.1, closePath=False)
            continue
        if name == "bundle" and wide:
            for d in (-w / 3, 0.0, w / 3):
                for poly in polys:
                    shape.draw_polyline(offset(poly, d))
                shape.finish(color=color, width=0.1, dashes=dashes, closePath=False)
            continue
        if name == "hair":
            for poly in polys:
                shape.draw_polyline(poly)
            shape.finish(color=color, width=0.1, dashes=dashes, closePath=False)
            continue
        if name == "chords":
            for poly in polys:
                pieces = split(poly, 2 + (len(poly) % 2)) if len(poly) == 2 else [poly]
                for piece in pieces:
                    shape.draw_polyline(piece)
            shape.finish(color=color, width=w, dashes=dashes, closePath=False)
            continue
        for poly in polys:
            shape.draw_polyline(poly)
        shape.finish(color=color, width=w, dashes=dashes, closePath=False)
    shape.commit()
    doc.save(str(out_pdf))
    return out_pdf

