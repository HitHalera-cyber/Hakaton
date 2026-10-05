"""Sheet layout: format, origin calibration, frame, title block, drawing scale.

The frame and the title block (основная надпись, ГОСТ 2.104) are part of
the KOMPAS sheet template, so their graphics are not recreated as geometry;
their texts are read as title-block data (the scale "5:1" among them).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..ir import Scale, Sheet
from ..pdf.vector_extractor import PageContent

# (name, short side, long side), mm
FORMATS = [("A0", 841, 1189), ("A1", 594, 841), ("A2", 420, 594), ("A3", 297, 420),
           ("A4", 210, 297), ("A5", 148, 210)]
FORMAT_TOLERANCE = 3.0

FRAME_LEFT, FRAME_OTHER = 20.0, 5.0  # ГОСТ 2.104 frame margins
TITLE_BLOCK_W, TITLE_BLOCK_H = 185.0, 55.0
GRAPH26_W, GRAPH26_H = 70.0, 14.0  # rotated designation box, top-left corner
LEFT_STRIP_X = 8.0  # additional columns left of the frame

SCALE_RE = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*:\s*(\d+(?:[.,]\d+)?)\s*$")
EDGE_TOLERANCE = 1.5  # mm, segment on a frame/sheet edge


@dataclass
class SheetLayout:
    sheet: Sheet
    zones: list[tuple[float, float, float, float]] = field(default_factory=list)

    def in_zone(self, x: float, y: float) -> bool:
        return any(x0 - 0.2 <= x <= x1 + 0.2 and y0 - 0.2 <= y <= y1 + 0.2
                   for x0, y0, x1, y1 in self.zones)

    def frame_box(self) -> tuple[float, float, float, float]:
        s = self.sheet
        return (FRAME_LEFT, FRAME_OTHER, s.width - FRAME_OTHER, s.height - FRAME_OTHER)

    def is_sheet_graphic(self, points) -> bool:
        """True for strokes of the frame, the title block or outside the frame."""
        if all(self.in_zone(*p) for p in points):
            return True
        x0, y0, x1, y1 = self.frame_box()
        for edge in ((x0, None), (x1, None), (None, y0), (None, y1)):
            ex, ey = edge
            if ex is not None and all(abs(p[0] - ex) < EDGE_TOLERANCE for p in points):
                return True
            if ey is not None and all(abs(p[1] - ey) < EDGE_TOLERANCE for p in points):
                return True
        return False


def _match_format(w: float, h: float):
    short, long_ = sorted((w, h))
    for name, fs, fl in FORMATS:
        if abs(short - fs) <= FORMAT_TOLERANCE and abs(long_ - fl) <= FORMAT_TOLERANCE:
            return name, fs, fl
    return None


def _sheet_outline(content: PageContent):
    """Find the thin rectangle KOMPAS draws along the sheet edge, if present."""
    xs = [s.a[0] for s in content.segments if abs(s.a[0] - s.b[0]) < 0.05 and s.length > 100]
    ys = [s.a[1] for s in content.segments if abs(s.a[1] - s.b[1]) < 0.05 and s.length > 100]
    if not xs or not ys:
        return None
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    fmt = _match_format(x1 - x0, y1 - y0)
    return (x0, y0, x1, y1, fmt) if fmt else None


def analyse_sheet(content: PageContent) -> SheetLayout:
    """Detect the format and shift ``content`` so the sheet corner is (0, 0)."""
    outline = _sheet_outline(content)
    if outline:
        x0, y0, x1, y1, fmt = outline
        content.translate(-x0, -y0)
        offset = (x0, y0)
        w, h = x1 - x0, y1 - y0
    else:
        fmt = _match_format(content.width, content.height)
        offset = (0.0, 0.0)
        w, h = content.width, content.height
    if fmt:
        name, fs, fl = fmt
        w, h = (fs, fl) if w < h else (fl, fs)
    else:
        name = "custom"
    sheet = Sheet(format=name, orientation="portrait" if h >= w else "landscape",
                  width=float(w), height=float(h), offset=(round(offset[0], 3), round(offset[1], 3)))

    layout = SheetLayout(sheet)
    sheet.frame_found = _has_frame(content, layout)
    if sheet.frame_found:
        fx0, fy0, fx1, fy1 = layout.frame_box()
        layout.zones = [
            (-1.0, -1.0, w + 1, fy0),  # bottom margin
            (-1.0, fy1, w + 1, h + 1),  # top margin
            (-1.0, -1.0, fx0, h + 1),  # left margin with the additional columns
            (fx1, -1.0, w + 1, h + 1),  # right margin
            (fx1 - TITLE_BLOCK_W, fy0, fx1, fy0 + TITLE_BLOCK_H),  # main title block
            (fx0, fy1 - GRAPH26_H, fx0 + GRAPH26_W, fy1),  # graph 26
        ]
    return layout


def _has_frame(content: PageContent, layout: SheetLayout) -> bool:
    x0, y0, x1, y1 = layout.frame_box()
    thick = max((s.width for s in content.segments), default=0.0)
    hits = 0
    for s in content.segments:
        if s.width < thick * 0.8 or s.length < 50:
            continue
        if (abs(s.a[0] - x0) < 1 and abs(s.b[0] - x0) < 1) or \
                (abs(s.a[1] - y0) < 1 and abs(s.b[1] - y0) < 1) or \
                (abs(s.a[0] - x1) < 1 and abs(s.b[0] - x1) < 1) or \
                (abs(s.a[1] - y1) < 1 and abs(s.b[1] - y1) < 1):
            hits += 1
    return hits >= 3


def read_title_block(content: PageContent, layout: SheetLayout) -> Scale:
    """Collect title-block texts and return the drawing scale written there."""
    scale = Scale()
    if not layout.sheet.frame_found:
        return scale
    for t in content.texts:
        cx = (t.bbox[0] + t.bbox[2]) / 2
        cy = (t.bbox[1] + t.bbox[3]) / 2
        if not layout.in_zone(cx, cy):
            continue
        key = f"text@{cx:.0f},{cy:.0f}"
        layout.sheet.title_block[key] = t.text
        m = SCALE_RE.match(t.text)
        if m and scale.source == "default":
            a, b = (float(v.replace(",", ".")) for v in m.groups())
            if a > 0 and b > 0:
                scale = Scale(value=a / b, text=t.text.strip(), source="title_block")
    return scale


def is_title_block_text(t, layout: SheetLayout) -> bool:
    return layout.in_zone((t.bbox[0] + t.bbox[2]) / 2, (t.bbox[1] + t.bbox[3]) / 2)
