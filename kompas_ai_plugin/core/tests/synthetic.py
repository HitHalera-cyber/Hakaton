"""Generate small vector PDFs with known geometry, in the style KOMPAS exports.

Circles are written as chord polylines (like KOMPAS) or Bézier curves (like
most other CAD systems); dimension arrows are filled triangles; axial lines
are separate dashes. Every value of the ground truth is known exactly.
"""

from __future__ import annotations

import math
from pathlib import Path

import pymupdf

MM = 72 / 25.4
PAGE_W, PAGE_H = 210.0, 297.0
MAIN, THIN = 0.6, 0.18  # stroke widths, mm


class Sheet:
    def __init__(self):
        self.doc = pymupdf.open()
        self.page = self.doc.new_page(width=PAGE_W * MM, height=PAGE_H * MM)

    def p(self, x, y):
        return pymupdf.Point(x * MM, (PAGE_H - y) * MM)

    def line(self, a, b, width=MAIN):
        self.page.draw_line(self.p(*a), self.p(*b), color=(0, 0, 0), width=width * MM)

    def polyline_circle(self, c, r, width=MAIN, chords=48, start=0.0, sweep=360.0):
        pts = [(c[0] + r * math.cos(math.radians(start + sweep * i / chords)),
                c[1] + r * math.sin(math.radians(start + sweep * i / chords)))
               for i in range(chords + 1)]
        for a, b in zip(pts, pts[1:]):
            self.line(a, b, width)

    def bezier_circle(self, c, r, width=MAIN):
        self.page.draw_circle(self.p(*c), r * MM, color=(0, 0, 0), width=width * MM)

    def dashed(self, a, b, pattern=(7.2, 1.5, 1.5, 1.5)):
        """Axial line written dash by dash."""
        length = math.dist(a, b)
        ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
        t, i = 0.0, 0
        while t < length:
            seg = pattern[i % len(pattern)]
            if i % 2 == 0:
                e = min(t + seg, length)
                self.line((a[0] + ux * t, a[1] + uy * t), (a[0] + ux * e, a[1] + uy * e), THIN)
            t += seg
            i += 1

    def arrow(self, tip, direction, length=5.0, width=1.0):
        dx, dy = direction
        n = math.hypot(dx, dy)
        dx, dy = dx / n, dy / n
        base = (tip[0] - dx * length, tip[1] - dy * length)
        left = (base[0] - dy * width / 2, base[1] + dx * width / 2)
        right = (base[0] + dy * width / 2, base[1] - dx * width / 2)
        self.page.draw_polyline([self.p(*tip), self.p(*left), self.p(*right), self.p(*tip)],
                                color=None, fill=(0, 0, 0), closePath=True)

    def text(self, origin, text, size_mm=5.0, angle=0.0):
        """Text with its baseline at ``origin`` turned ``angle`` degrees CCW."""
        at = self.p(*origin)
        self.page.insert_text(at, text, fontsize=size_mm / 0.7 * MM, fontname="helv",
                              morph=(at, pymupdf.Matrix(angle)))

    def save(self, path: Path) -> Path:
        self.doc.save(str(path))
        self.doc.close()
        return path


def plate_with_hole(path: Path, bezier: bool = False, width_text: str = "60") -> dict:
    """Rectangle 60×40 with a Ø20 hole, axes, a width dimension and a diameter.

    Returns the ground truth in sheet mm.
    """
    s = Sheet()
    x0, y0, w, h = 50.0, 150.0, 60.0, 40.0
    c, r = (80.0, 170.0), 10.0
    corners = [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)]
    for a, b in zip(corners, corners[1:] + corners[:1]):
        s.line(a, b)
    (s.bezier_circle if bezier else s.polyline_circle)(c, r)
    s.dashed((c[0] - 15, c[1]), (c[0] + 15, c[1]))
    s.dashed((c[0], c[1] - 15), (c[0], c[1] + 15))

    # Horizontal dimension of the width, 12 mm above the plate.
    dim_y = y0 + h + 12
    s.line((x0, y0 + h + 1), (x0, dim_y + 2), THIN)
    s.line((x0 + w, y0 + h + 1), (x0 + w, dim_y + 2), THIN)
    s.line((x0, dim_y), (x0 + w, dim_y), THIN)
    s.arrow((x0, dim_y), (-1, 0))
    s.arrow((x0 + w, dim_y), (1, 0))
    s.text((x0 + w / 2 - 3, dim_y + 1.2), width_text)

    # Diameter dimension through the centre at 45°.
    a = math.radians(45)
    t1 = (c[0] - r * math.cos(a), c[1] - r * math.sin(a))
    t2 = (c[0] + r * math.cos(a), c[1] + r * math.sin(a))
    far = (c[0] + (r + 12) * math.cos(a), c[1] + (r + 12) * math.sin(a))
    s.line(t1, far, THIN)
    s.arrow(t1, (-math.cos(a), -math.sin(a)))
    s.arrow(t2, (math.cos(a), math.sin(a)))
    s.text((far[0] - 9.0 * math.cos(a) - 1.0 * math.sin(a), far[1] - 9.0 * math.sin(a) + 1.0 * math.cos(a)),
           "Ø20", angle=45.0)

    s.save(path)
    return {
        "lines": [(a, b) for a, b in zip(corners, corners[1:] + corners[:1])],
        "circle": (c, r),
        "dims": {"60": ("linear", 60.0), "Ø20": ("diameter", 20.0)},
    }
