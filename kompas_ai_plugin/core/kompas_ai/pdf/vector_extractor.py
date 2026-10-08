"""Extract raw vector primitives from a PDF page.

Everything is converted to sheet millimetres with the origin in the
bottom-left corner of the page and Y up. Curves are flattened to polylines:
KOMPAS already exports arcs as chords, other CAD systems use Bézier curves,
and the geometry fitter treats both the same way.
"""

from __future__ import annotations

import math
import re
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
    # Rich text: [(text, kind, x, y, height)], kind "normal" | "sub" | "sup";
    # x, y is where the part starts in the PDF. None = plain text.
    parts: list[tuple] | None = None


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
            pattern = _dash_pattern(path.get("dashes"))
            if pattern:
                polylines = [piece for poly in polylines for piece in _apply_dashes(poly, *pattern)]
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


def _dash_pattern(dashes: str | None):
    """'[ 34 8.5 1.4 8.5 ] 0' → ([mm…], phase mm); None for a solid stroke."""
    if not dashes:
        return None
    m = re.match(r"\s*\[([^\]]*)\]\s*([-\d.]*)", dashes)
    if not m:
        return None
    try:
        lengths = [float(v) * PT_TO_MM for v in m.group(1).split()]
        phase = float(m.group(2) or 0) * PT_TO_MM
    except ValueError:
        return None
    if not lengths or sum(lengths) <= 1e-6 or any(v < 0 for v in lengths):
        return None
    if len(lengths) % 2:
        lengths *= 2
    return lengths, phase


def _apply_dashes(poly, lengths, phase):
    """Split a polyline into the dashes a PDF viewer would draw. Exporters
    (AutoCAD, SolidWorks, Inventor…) give centre and hidden lines as one
    path with a dash array; KOMPAS draws every dash itself. Producing the
    dashes here lets the same dash-merging logic handle both. Zero-length
    dots (drawn with round caps) become 0.1 mm pieces."""
    period = sum(lengths)
    pos = phase % period
    i = 0
    while pos >= lengths[i]:
        pos -= lengths[i]
        i = (i + 1) % len(lengths)
    left = lengths[i] - pos
    pieces, cur = [], [poly[0]] if i % 2 == 0 else None
    for a, b in zip(poly, poly[1:]):
        d = math.dist(a, b)
        t = 0.0
        while d - t > left:
            t += left
            f = t / d
            x = (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
            if i % 2 == 0:
                cur.append(x)
                pieces.append(cur)
                cur = None
            else:
                cur = [x]
            i = (i + 1) % len(lengths)
            left = lengths[i]
        left -= d - t
        if cur is not None:
            cur.append(b)
    if cur is not None and len(cur) > 1:
        pieces.append(cur)
    out = []
    for piece in pieces:
        if sum(math.dist(p, q) for p, q in zip(piece, piece[1:])) < 0.1:
            c = piece[0]
            nxt = next((q for q in poly if math.dist(q, c) > 1e-6), None)
            if nxt is None:
                continue
            k = 0.1 / math.dist(c, nxt)
            piece = [c, (c[0] + (nxt[0] - c[0]) * k, c[1] + (nxt[1] - c[1]) * k)]
        out.append(piece)
    return out


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
            same_size = min(prev.height, span.height) / max(prev.height, span.height) > 0.8
            # Sub/superscripts (smaller, shifted) stay separate texts at their own place.
            if same_size and abs(across) < 0.3 * prev.height and 0.0 < along < 1.3 * prev.height:
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
    return attach_indices(merged)


INDEX_MAX_SIZE = 0.85  # an index is smaller than its base text


def attach_indices(texts: list[RawText]) -> list[RawText]:
    """Join subscripts/superscripts to their base text: P + «кав» + «=3,38» → P_кав=3,38.

    An index is a smaller text starting right after the base, with its
    baseline shifted down (subscript) or up (superscript). Text of the base
    size that continues after an index is joined too.
    """
    def frame(t: RawText, p):
        a = math.radians(t.angle)
        ux, uy = math.cos(a), math.sin(a)
        vx, vy = p[0] - t.origin[0], p[1] - t.origin[1]
        return vx * ux + vy * uy, -vx * uy + vy * ux

    def last_kind(t: RawText) -> str:
        return t.parts[-1][1] if t.parts else "normal"

    def attach(base: RawText, x: RawText) -> str | None:
        if abs(base.angle - x.angle) > 1.0:
            return None
        h = base.height
        along = frame(base, x.origin)[0] - frame(base, base.last_origin or base.origin)[0]
        across = frame(base, x.origin)[1]
        if not 0.0 < along < 1.5 * h:
            return None
        if x.height < INDEX_MAX_SIZE * h and not x.parts and 0.08 * h < abs(across) < 0.8 * h:
            return "sub" if across < 0 else "sup"
        if last_kind(base) != "normal" and x.height >= INDEX_MAX_SIZE * h and abs(across) < 0.3 * h:
            return "normal"
        return None

    def gap(base: RawText, x: RawText) -> float:
        return frame(base, x.origin)[0] - frame(base, base.last_origin or base.origin)[0]

    items = list(texts)
    changed = True
    while changed:
        changed = False
        for x in items:
            # the base an index belongs to is the nearest one before it
            options = [(gap(b, x), b, k) for b in items if b is not x
                       for k in [attach(b, x)] if k is not None]
            if not options:
                continue
            _, base, kind = min(options, key=lambda o: o[0])
            base_parts = base.parts or [(base.text, "normal", *base.origin, base.height)]
            x_parts = [(text, kind if k == "normal" else k, px, py, ph) for text, k, px, py, ph in
                       (x.parts or [(x.text, "normal", *x.origin, x.height)])]
            base.parts = base_parts + x_parts
            base.text = base.text + x.text
            base.bbox = (min(base.bbox[0], x.bbox[0]), min(base.bbox[1], x.bbox[1]),
                         max(base.bbox[2], x.bbox[2]), max(base.bbox[3], x.bbox[3]))
            base.last_origin = x.last_origin
            items.remove(x)
            changed = True
            break
    return items


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
