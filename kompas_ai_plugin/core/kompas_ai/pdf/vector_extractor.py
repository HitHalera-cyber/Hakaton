"""Extract raw vector primitives from a PDF page.

Everything is converted to sheet millimetres with the origin in the
bottom-left corner of the page and Y up. Curves are flattened to polylines:
KOMPAS already exports arcs as chords, other CAD systems use Bézier curves,
and the geometry fitter treats both the same way.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

PT_TO_MM = 25.4 / 72.0

# GOST cap height / font em size, measured on KOMPAS output (5 mm text has a
# 7.31 mm em box).
CAP_HEIGHT_RATIO = 0.684
STANDARD_TEXT_HEIGHTS = (1.8, 2.5, 3.5, 5.0, 7.0, 10.0, 14.0, 20.0)

# Characters of KOMPAS' symbol fonts mapped to Unicode.
SYMBOL_FONT_MAP = {
    "Ç": "Ø",
    "Å": "°",
    "±": "±",
}
SYMBOL_FONTS = ("symbol_a", "symbol_b", "symbol")

BEZIER_STEPS = 16


@dataclass
class RawSegment:
    a: tuple[float, float]
    b: tuple[float, float]
    width: float  # stroke width, mm

    @property
    def length(self) -> float:
        return math.dist(self.a, self.b)


@dataclass
class RawFill:
    """A filled (non-white) polygon — arrowheads, filled points, solid fills."""

    points: list[tuple[float, float]]
    color: tuple[float, float, float]


@dataclass
class RawText:
    text: str
    origin: tuple[float, float]  # baseline start, mm
    angle: float  # degrees CCW
    height: float  # cap height, mm
    font: str
    bbox: tuple[float, float, float, float]  # x0, y0, x1, y1 in mm (axis aligned)
    last_origin: tuple[float, float] | None = None  # origin of the last character


@dataclass
class PageContent:
    width: float
    height: float
    segments: list[RawSegment] = field(default_factory=list)
    fills: list[RawFill] = field(default_factory=list)
    texts: list[RawText] = field(default_factory=list)
    images: int = 0
    unknown_symbols: set[str] = field(default_factory=set)

    @property
    def is_vector(self) -> bool:
        return len(self.segments) > 20

    def translate(self, dx: float, dy: float) -> None:
        """Shift every primitive by (dx, dy) — used to align with the sheet origin."""
        def mv(p):
            return (p[0] + dx, p[1] + dy)

        for s in self.segments:
            s.a, s.b = mv(s.a), mv(s.b)
        for f in self.fills:
            f.points = [mv(p) for p in f.points]
        for t in self.texts:
            t.origin = mv(t.origin)
            t.last_origin = mv(t.last_origin) if t.last_origin else None
            t.bbox = (t.bbox[0] + dx, t.bbox[1] + dy, t.bbox[2] + dx, t.bbox[3] + dy)


def _bezier(p0, p1, p2, p3, steps: int = BEZIER_STEPS):
    pts = []
    for i in range(steps + 1):
        t = i / steps
        mt = 1 - t
        pts.append((
            mt ** 3 * p0[0] + 3 * mt * mt * t * p1[0] + 3 * mt * t * t * p2[0] + t ** 3 * p3[0],
            mt ** 3 * p0[1] + 3 * mt * mt * t * p1[1] + 3 * mt * t * t * p2[1] + t ** 3 * p3[1],
        ))
    return pts


class _Converter:
    def __init__(self, page_height_pt: float):
        self.h = page_height_pt

    def pt(self, p) -> tuple[float, float]:
        return (p.x * PT_TO_MM, (self.h - p.y) * PT_TO_MM)

    def path_polylines(self, path: dict) -> list[list[tuple[float, float]]]:
        """Split a PyMuPDF path into polylines of sheet points."""
        polylines: list[list[tuple[float, float]]] = []
        current: list[tuple[float, float]] = []

        def push(points):
            nonlocal current
            if current and math.dist(current[-1], points[0]) < 1e-6:
                current.extend(points[1:])
            else:
                if len(current) > 1:
                    polylines.append(current)
                current = list(points)

        for item in path["items"]:
            op = item[0]
            if op == "l":
                push([self.pt(item[1]), self.pt(item[2])])
            elif op == "c":
                push(_bezier(*(self.pt(p) for p in item[1:5])))
            elif op == "re":
                r = item[1]
                corners = [r.tl, r.tr, r.br, r.bl, r.tl]
                push([self.pt(p) for p in corners])
            elif op == "qu":
                q = item[1]
                push([self.pt(p) for p in (q.ul, q.ur, q.lr, q.ll, q.ul)])
        if len(current) > 1:
            polylines.append(current)
        if path.get("closePath") and polylines and polylines[-1][0] != polylines[-1][-1]:
            polylines[-1].append(polylines[-1][0])
        return polylines


def _is_white(color) -> bool:
    return color is not None and all(c > 0.95 for c in color)


def _extract_geometry(page: pymupdf.Page, conv: _Converter, content: PageContent) -> None:
    seen: set[tuple] = set()
    for path in page.get_drawings():
        polylines = conv.path_polylines(path)
        fill = path.get("fill")
        if fill is not None and not _is_white(fill):
            # A filled path is one area even when its items are not chained.
            points = [p for poly in polylines for p in poly]
            if len(points) >= 3:
                content.fills.append(RawFill(points=points, color=tuple(fill)))
        if path["type"] in ("s", "fs") and path.get("color") is not None and fill is None:
            width = (path.get("width") or 0.0) * PT_TO_MM
            for poly in polylines:
                for a, b in zip(poly, poly[1:]):
                    if math.dist(a, b) < 1e-6:
                        continue
                    key = tuple(sorted((tuple(round(v, 3) for v in a),
                                        tuple(round(v, 3) for v in b))))
                    if key in seen:  # KOMPAS draws every chord there and back
                        continue
                    seen.add(key)
                    content.segments.append(RawSegment(a, b, width))


def _normalise_text(text: str, font: str, unknown: set[str]) -> str:
    if not font.lower().startswith(SYMBOL_FONTS):
        return text
    out = []
    for ch in text:
        if ch in SYMBOL_FONT_MAP:
            out.append(SYMBOL_FONT_MAP[ch])
        else:
            unknown.add(ch)
            out.append(ch)
    return "".join(out)


def _snap_height(h: float) -> float:
    best = min(STANDARD_TEXT_HEIGHTS, key=lambda s: abs(s - h))
    return best if abs(best - h) / best < 0.12 else round(h, 2)


def _extract_text(page: pymupdf.Page, conv: _Converter, content: PageContent) -> None:
    raw = page.get_text("rawdict")
    spans: list[RawText] = []
    for block in raw["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            dx, dy = line["dir"]
            angle = math.degrees(math.atan2(-dy, dx))
            for span in line["spans"]:
                text = "".join(ch["c"] for ch in span["chars"])
                if not text.strip():
                    continue
                text = _normalise_text(text, span["font"], content.unknown_symbols)
                x0, y0, x1, y1 = span["bbox"]
                last = span["chars"][-1]["origin"]
                spans.append(RawText(
                    text=text,
                    origin=conv.pt(pymupdf.Point(span["origin"])),
                    angle=round(angle, 2),
                    height=_snap_height(span["size"] * PT_TO_MM * CAP_HEIGHT_RATIO),
                    font=span["font"],
                    bbox=(x0 * PT_TO_MM, (conv.h - y1) * PT_TO_MM,
                          x1 * PT_TO_MM, (conv.h - y0) * PT_TO_MM),
                    last_origin=conv.pt(pymupdf.Point(last)),
                ))
    content.texts = merge_text_runs(spans)


def merge_text_runs(spans: list[RawText]) -> list[RawText]:
    """Join spans that continue each other on one baseline (e.g. 'Ø' + '2,68').

    Glyph boxes overlap, so continuity is judged by character origins: the
    next span must start on the same baseline less than ~1.3 text heights
    after the origin of the previous span's last character.
    """
    def along_across(origin, ref, angle):
        a = math.radians(angle)
        ux, uy = math.cos(a), math.sin(a)
        vx, vy = origin[0] - ref[0], origin[1] - ref[1]
        return vx * ux + vy * uy, -vx * uy + vy * ux

    def key(span):
        along, across = along_across(span.origin, (0.0, 0.0), span.angle)
        return (round(span.angle), round(across, 1), along)

    merged: list[RawText] = []
    for span in sorted(spans, key=key):
        for i, prev in enumerate(merged):
            if abs(prev.angle - span.angle) > 1.0:
                continue
            along, across = along_across(span.origin, prev.last_origin or prev.origin, prev.angle)
            if abs(across) < 0.3 * prev.height and 0.0 < along < 1.3 * prev.height:
                sep = " " if along > 0.9 * prev.height and not span.text.startswith(" ") else ""
                merged[i] = RawText(
                    text=prev.text + sep + span.text,
                    origin=prev.origin, angle=prev.angle,
                    height=max(prev.height, span.height), font=prev.font,
                    bbox=(min(prev.bbox[0], span.bbox[0]), min(prev.bbox[1], span.bbox[1]),
                          max(prev.bbox[2], span.bbox[2]), max(prev.bbox[3], span.bbox[3])),
                    last_origin=span.last_origin,
                )
                break
        else:
            merged.append(span)
    for t in merged:
        t.text = " ".join(t.text.split())
    return merged


def extract_page(pdf_path: str | Path, page_number: int = 0) -> PageContent:
    """Read one PDF page into raw primitives (sheet mm, origin bottom-left)."""
    with pymupdf.open(str(pdf_path)) as doc:
        page = doc[page_number]
        conv = _Converter(page.rect.height)
        content = PageContent(width=page.rect.width * PT_TO_MM,
                              height=page.rect.height * PT_TO_MM)
        _extract_geometry(page, conv, content)
        _extract_text(page, conv, content)
        content.images = len(page.get_images())
    return content
