"""Preview: the source drawing (faded) with the recognised objects on top.

Colours: blue — main lines, green — circles and arcs, orange — axial lines,
light blue — thin lines, magenta — dimensions, brown — texts, cyan — hatch
boundaries, red rings — objects that need review.
"""

from __future__ import annotations

import math
from pathlib import Path

import pymupdf

from .. import ir
from ..pdf.vector_extractor import PT_TO_MM

COLORS = {
    ir.STYLE_MAIN: (0.0, 0.3, 1.0),
    ir.STYLE_THIN: (0.35, 0.7, 1.0),
    ir.STYLE_AXIAL: (1.0, 0.5, 0.0),
    ir.STYLE_DASHED: (0.6, 0.3, 1.0),
    "curve": (0.0, 0.65, 0.0),
    "dim": (0.85, 0.0, 0.85),
    "text": (0.6, 0.35, 0.0),
    "hatch": (0.0, 0.75, 0.75),
    "review": (1.0, 0.0, 0.0),
}
FONT_FILES = [  # first one found is used for Cyrillic labels
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
]
FONT = "ui"

LEGEND = [("Основные линии", ir.STYLE_MAIN), ("Окружности и дуги", "curve"),
          ("Осевые", ir.STYLE_AXIAL), ("Тонкие", ir.STYLE_THIN), ("Размеры", "dim"),
          ("Текст", "text"), ("Штриховка", "hatch"), ("Требуют проверки", "review")]


def render_preview(drawing: ir.Drawing, pdf_path: str | Path, out_png: str | Path,
                   page_number: int = 0, dpi: int = 200) -> None:
    src = pymupdf.open(str(pdf_path))
    doc = pymupdf.open()
    doc.insert_pdf(src, from_page=page_number, to_page=page_number)
    page = doc[0]
    _register_font(page)
    height = page.rect.height
    ox, oy = drawing.sheet.offset

    def pt(p):
        return pymupdf.Point((p[0] + ox) / PT_TO_MM, height - (p[1] + oy) / PT_TO_MM)

    fade = page.new_shape()
    fade.draw_rect(page.rect)
    fade.finish(color=None, fill=(1, 1, 1), fill_opacity=0.65)
    fade.commit()

    shape = page.new_shape()
    for e in drawing.entities:
        _draw_entity(shape, e, pt)
    shape.commit()
    _legend(page, drawing)
    page.get_pixmap(dpi=dpi).save(str(out_png))
    doc.close()
    src.close()


def _polyline(shape, points, color, width):
    for a, b in zip(points, points[1:]):
        shape.draw_line(a, b)
    shape.finish(color=color, width=width, closePath=False)


def _arc_points(center, radius, start, sweep, pt):
    steps = max(8, int(sweep / 4))
    return [pt((center[0] + radius * math.cos(math.radians(start + sweep * i / steps)),
                center[1] + radius * math.sin(math.radians(start + sweep * i / steps))))
            for i in range(steps + 1)]


def _draw_entity(shape, e: ir.Entity, pt) -> None:
    review = e.confidence < ir.REVIEW_THRESHOLD
    if isinstance(e, ir.Line):
        _polyline(shape, [pt(e.p1), pt(e.p2)], COLORS.get(e.style), 1.6 if e.style == "main" else 0.9)
        anchor = ((e.p1[0] + e.p2[0]) / 2, (e.p1[1] + e.p2[1]) / 2)
    elif isinstance(e, (ir.Circle, ir.Arc)):
        start, sweep = (0.0, 360.0) if isinstance(e, ir.Circle) else \
            (e.start_angle, (e.end_angle - e.start_angle) % 360.0 or 360.0)
        color = COLORS[ir.STYLE_AXIAL] if e.style == ir.STYLE_AXIAL else COLORS["curve"]
        _polyline(shape, _arc_points(e.center, e.radius, start, sweep, pt), color, 1.6)
        anchor = e.center
    elif isinstance(e, ir.Dimension):
        color = COLORS["dim"]
        pts = [p for p in (e.p1, e.p2) if p]
        for p in pts:
            shape.draw_circle(pt(p), 1.6)
            shape.finish(color=color, width=1.0)
        if len(pts) == 2:
            _polyline(shape, [pt(pts[0]), pt(pts[1])], color, 0.8)
        anchor = e.line_point or (pts[0] if pts else e.center)
        label = f"{e.id}: {e.text}"
        shape.insert_text(pt(anchor) + (3, -3), label, fontsize=6, color=color, fontname=FONT)
    elif isinstance(e, ir.Text):
        p = pt(e.position)
        shape.draw_rect(pymupdf.Rect(p.x - 1, p.y - e.height / PT_TO_MM - 1, p.x + 4, p.y + 1))
        shape.finish(color=COLORS["text"], width=0.8)
        anchor = e.position
    elif isinstance(e, ir.Hatch):
        for ring in e.contours:
            _polyline(shape, [pt(p) for p in ring], COLORS["hatch"], 1.2)
        anchor = e.contours[0][0] if e.contours else None
    else:
        return
    if review and anchor is not None:
        shape.draw_circle(pt(anchor), 6)
        shape.finish(color=COLORS["review"], width=1.5)


def _legend(page, drawing: ir.Drawing) -> None:
    x, y = page.rect.width - 165, 30
    box = pymupdf.Rect(x - 6, y - 12, x + 150, y + 12 * len(LEGEND) + 18)
    page.draw_rect(box, color=(0.4, 0.4, 0.4), fill=(1, 1, 1), width=0.5)
    page.insert_text((x, y), f"Распознано: {Path(drawing.source).name}", fontsize=7,
                     fontname=FONT)
    for i, (label, key) in enumerate(LEGEND):
        yy = y + 12 * (i + 1)
        page.draw_line((x, yy - 2.5), (x + 16, yy - 2.5), color=COLORS[key], width=2)
        page.insert_text((x + 22, yy), label, fontsize=7, fontname=FONT)


def _register_font(page) -> None:
    """Register a font with Cyrillic and Ø glyphs (the base-14 fonts have none)."""
    for path in FONT_FILES:
        if Path(path).exists():
            page.insert_font(fontname=FONT, fontfile=path)
            return
    page.insert_font(fontname=FONT, fontbuffer=pymupdf.Font("china-s").buffer)
