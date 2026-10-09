"""Drawing IR → KOMPAS drawing.

Two ways to handle the drawing scale:

* ``sheet`` (default, works without a licence): everything is drawn in sheet
  millimetres in the 1:1 system view, exactly where it is in the PDF. For a
  scale other than 1:1 the dimension values are written as text (the value
  read from the drawing), because KOMPAS would otherwise show sheet sizes.
* ``view``: a view with the drawing scale is created and the geometry is drawn
  in model millimetres, so KOMPAS computes dimension values itself. Needs a
  licence (KOMPAS v22 refuses ksCreateSheetView without one); if the view is
  refused the writer falls back to ``sheet``.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from .. import ir
from .backend import (LINEAR_HORIZONTAL, LINEAR_PARALLEL, LINEAR_VERTICAL, STYLE_IDS, Backend,
                      DimText)

FORMAT_INDEX = {"A0": 0, "A1": 1, "A2": 2, "A3": 3, "A4": 4}


@dataclass
class WriteReport:
    mode: str = "sheet"
    created: dict[str, int] = field(default_factory=dict)
    failed: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def count(self, kind: str) -> None:
        self.created[kind] = self.created.get(kind, 0) + 1

    def text(self) -> str:
        names = {"line": "отрезков", "circle": "окружностей", "arc": "дуг", "text": "текстов",
                 "dimension": "размеров", "hatch": "штриховок", "pointmark": "точек"}
        out = [f"Режим масштаба: {'вид с масштабом' if self.mode == 'view' else 'мм листа'}",
               "Создано в КОМПАС: " + ", ".join(f"{names.get(k, k)} {v}"
                                                for k, v in self.created.items())]
        if self.failed:
            out.append(f"Не создано ({len(self.failed)}): " + ", ".join(self.failed))
        out += [f"  ! {n}" for n in self.notes]
        return "\n".join(out)


PLAIN_VALUE_RE = re.compile(r"^\d+(?:[.,]\d+)?°?$")


MIN_ANGULAR_RADIUS = 12.0  # sheet mm
ANG_TEXT_INSIDE = 2.75  # sheet mm from a KOMPAS angular dimension arc to the middle of its value
ANG_GROWTH = 1.4  # the dimension arc grows at most this much over the source one
EXT_OVERSHOOT = 2.0  # sheet mm an extension line goes past the dimension line


def _params(func) -> set[str]:
    import inspect

    try:
        return set(inspect.signature(func).parameters)
    except (TypeError, ValueError):
        return set()


class DrawingWriter:
    def __init__(self, backend: Backend, mode: str = "sheet", with_dimensions: bool = True):
        self.b = backend
        self.mode = mode
        # False: a plain drawing (lines, arcs, texts, hatches) without dimensions
        self.with_dimensions = with_dimensions
        self.scale = 1.0
        self.origin = (0.0, 0.0)  # sheet point of the view origin (view mode)
        self._drawing: ir.Drawing | None = None

    # --- coordinate handling --------------------------------------------------------

    def _p(self, p):
        """Sheet mm → current drawing space."""
        if self.mode == "view":
            return ((p[0] - self.origin[0]) / self.scale, (p[1] - self.origin[1]) / self.scale)
        return (p[0], p[1])

    def _len(self, v: float) -> float:
        """Sheet mm → view mm for geometry. Text heights and hatch steps are not
        scaled: KOMPAS keeps them in sheet millimetres in any view."""
        return v / self.scale if self.mode == "view" else v

    # --- entry point -------------------------------------------------------------------

    def write(self, drawing: ir.Drawing) -> WriteReport:
        self._drawing = drawing
        report = WriteReport(mode=self.mode)
        sheet = drawing.sheet
        fmt = FORMAT_INDEX.get(sheet.format)
        if fmt is None:
            report.notes.append(f"Формат {sheet.format} не стандартный — создан A4")
            fmt = 4
        self.b.new_sheet(fmt, sheet.orientation == "landscape")

        self.scale = drawing.scale.value or 1.0
        if self.mode == "view" and self.scale != 1.0:
            if not self.b.open_view(self.origin, self.scale, f"Вид {drawing.scale.text}"):
                report.notes.append("КОМПАС не создал вид с масштабом (нужна лицензия) — "
                                    "чертёж построен в мм листа, числа размеров вписаны вручную")
                self.mode = report.mode = "sheet"
        elif self.mode == "view":
            self.mode = report.mode = "sheet"

        order = (ir.Hatch, ir.Line, ir.Circle, ir.Arc, ir.Ellipse, ir.PointMark, ir.Text) \
            + ((ir.Dimension,) if self.with_dimensions else ())
        if self.with_dimensions:
            moved = spread_dimension_lines(drawing.of_type(ir.Dimension))
            if moved:
                report.notes.append(f"Размерные линии разнесены по ГОСТ 2.307 (≥7 мм): {moved}")
        refs: dict[str, object] = {}
        for cls in order:
            for e in drawing.of_type(cls):
                try:
                    ref = self._write(e, drawing)
                except Exception as exc:  # one bad object must not stop the drawing
                    ref = None
                    report.notes.append(f"{e.id}: {exc!r}")
                if ref:
                    report.count(e.kind)
                    refs[e.id] = ref
                elif ref is not False:  # False = intentionally skipped
                    report.failed.append(e.id)
            if cls is ir.Text and getattr(self.b, "parametric", False):
                made, tried = self._constraints(drawing, refs)
                report.notes.append(f"Параметризация: создано связей {made} из {tried}")
        return report

    def _constraints(self, drawing: ir.Drawing, refs) -> tuple[int, int]:
        """Relations found on the drawing → KOMPAS constraints (parametric mode)."""
        jobs = []
        for c in drawing.constraints:
            if c.type == "coincident":
                continue  # set below with the exact end points, lines and arcs alike
            if c.a in refs and (c.b is None or c.b in refs):
                jobs.append((c.type, refs[c.a], refs.get(c.b) if c.b else None, None, None))
        jobs += [("coincident", refs[a], refs[b], ia, ib)
                 for a, ia, b, ib in _shared_ends(drawing) if a in refs and b in refs]
        made = 0
        for kind, a, b, ia, ib in jobs:
            try:
                made += bool(self.b.constrain(kind, a, b, ia, ib))
            except Exception:  # an over-constrained or unsupported pair: keep going
                pass
        return made, len(jobs)

    # --- entities ----------------------------------------------------------------------

    def _write(self, e: ir.Entity, drawing: ir.Drawing):
        if isinstance(e, ir.Line):
            return self.b.line(self._p(e.p1), self._p(e.p2), STYLE_IDS.get(e.style, 1))
        if isinstance(e, ir.Circle):
            return self.b.circle(self._p(e.center), self._len(e.radius), STYLE_IDS.get(e.style, 1))
        if isinstance(e, ir.Arc):
            return self.b.arc(self._p(e.center), self._len(e.radius), e.start_angle, e.end_angle,
                              STYLE_IDS.get(e.style, 1))
        if isinstance(e, ir.Ellipse):
            return self._ellipse(e)
        if isinstance(e, ir.PointMark):
            return self.b.point(self._p(e.position))
        if isinstance(e, ir.Text):
            if e.parts and any(part[1] != "normal" for part in e.parts):
                return self._indexed_text(e)
            return self.b.text(self._p(e.position), e.text, e.height, e.angle)
        if isinstance(e, ir.Hatch):
            if not e.contours:
                return None
            contours = [[self._p(p) for p in ring] for ring in e.contours]
            return self.b.hatch(contours, e.angle, e.spacing)
        if isinstance(e, ir.Dimension):
            return self._dimension(e)
        return False

    def _ellipse(self, e: ir.Ellipse):
        style = STYLE_IDS.get(e.style, 1)
        if hasattr(self.b, "ellipse"):
            try:
                ref = self.b.ellipse(self._p(e.center), self._len(e.a), self._len(e.b), e.angle,
                                     style)
                if ref:
                    return ref
            except Exception:
                pass
        # no ellipse in this KOMPAS: the arcs and lines of the source
        refs = []
        for piece in e.arcs:
            if piece[0] == "line":
                refs.append(self.b.line(self._p(piece[1]), self._p(piece[2]), style))
            else:
                refs.append(self.b.arc(self._p(piece[1]), self._len(piece[2]), piece[3], piece[4],
                                       style))
        return refs[0] if refs and all(refs) else None

    def _indexed_text(self, e: ir.Text):
        """One text with indices if KOMPAS can, else each part at its own place."""
        try:
            ref = self.b.rich_text(self._p(e.position), [(t, k) for t, k, *_ in e.parts],
                                   e.height, e.angle)
            if ref:
                return ref
        except Exception:  # no API7 / no licence / COM error: write the parts separately
            pass
        refs = [self.b.text(self._p((x, y)), t, h, e.angle)
                for t, _, x, y, h in e.parts if t.strip()]
        return refs[0] if refs and all(refs) else None

    def _dim_text(self, d: ir.Dimension) -> DimText:
        """Auto value when KOMPAS can compute it; otherwise the text read from the PDF."""
        written = d.text.strip()
        diameter = written.startswith("Ø")
        if diameter:
            written = written[1:].strip()
        # The value written on the source drawing is exact; KOMPAS' own measure
        # is used only where the geometry is in model units (a scaled view) or
        # for angles (their sides are set to the written value).
        # An automatic value would drop tolerances, fits and thread pitches
        # (R1±0,5*, Ø26h12, M22×1,5): those keep the text of the source.
        plain = PLAIN_VALUE_RE.match(written) is not None
        if plain and (d.dim_type == "angular" or self.mode == "view"):
            return DimText(auto=True, diameter_sign=diameter and d.dim_type != "diameter")
        return DimText(auto=False, value=written, diameter_sign=diameter)

    def _dimension(self, d: ir.Dimension):
        text = self._dim_text(d)
        if d.dim_type == "linear" and d.p1 and d.p2:
            p1, p2 = self._p(d.p1), self._p(d.p2)
            # The offset of the dimension line is in sheet mm even inside a
            # scaled view (like text heights): dividing it by the scale put all
            # dimension lines 4× closer to the part in a 4:1 view.
            line, q1 = d.line_point or d.p1, d.p1
            if d.orientation == "horizontal":
                kind, offset = LINEAR_HORIZONTAL, (0.0, line[1] - q1[1])
            elif d.orientation == "vertical":
                kind, offset = LINEAR_VERTICAL, (line[0] - q1[0], 0.0)
            else:
                kind, offset = LINEAR_PARALLEL, (line[0] - q1[0], line[1] - q1[1])
            if kind == LINEAR_HORIZONTAL and d.text_center and d.line_point \
                    and "text_right" in _params(self.b.linear_dim):
                # a small size whose value stands right of it on the source
                # (0,5×45° next to 3,2H12 and 4,5±0,1): KOMPAS would put it on
                # the left over the neighbours
                right = d.text_center[0] > max(d.p1[0], d.p2[0]) + 1.0
                left = d.text_center[0] < min(d.p1[0], d.p2[0]) - 1.0
                if left and "text_offset" in _params(self.b.linear_dim):
                    # the value left of a small size, as on the source (KOMPAS
                    # would put it on the right, over its neighbours)
                    mid = (d.p1[0] + d.p2[0]) / 2
                    return self.b.linear_dim(p1, p2, offset, kind, text,
                                             text_offset=round(d.text_center[0] - mid, 2))
                return self.b.linear_dim(p1, p2, offset, kind, text, text_right=right,
                                         line_point=self._p(((d.p1[0] + d.p2[0]) / 2, line[1])))
            return self.b.linear_dim(p1, p2, offset, kind, text)
        if d.dim_type in ("diameter", "radius") and d.center and d.radius:
            angle = 45.0
            if d.p1:
                angle = math.degrees(math.atan2(d.p1[1] - d.center[1], d.p1[0] - d.center[0]))
            if d.dim_type == "radius" and not text.auto:
                text.value = "R" + text.value.lstrip("R")
            if d.dim_type == "radius" and d.text_pos and d.p1 \
                    and "text_dist" in _params(self.b.radial_dim):
                # the value goes where the source has it: usually on the far
                # side of the centre, off a small fillet
                # KOMPAS moves the value outwards from the arc for a positive
                # textPos (api_test13); a value written on the centre's side of
                # the arrow gets a negative one
                out = (d.text_pos[0] - d.p1[0]) * (d.p1[0] - d.center[0]) \
                    + (d.text_pos[1] - d.p1[1]) * (d.p1[1] - d.center[1])
                dist = math.dist(d.p1, d.text_pos) * (1 if out >= 0 else -1)
                return self.b.radial_dim(self._p(d.center), self._len(d.radius), angle, False,
                                         text, text_dist=round(dist, 2))
            return self.b.radial_dim(self._p(d.center), self._len(d.radius), angle,
                                     d.dim_type == "diameter", text)
        if d.dim_type == "angular" and d.center and d.p1 and d.p2:
            if min(math.dist(d.center, d.p1), math.dist(d.center, d.p2)) < 1e-3:
                return None  # a side point at the vertex has no direction
            a1 = _polar(d.center, d.p1)
            a2 = _polar(d.center, d.p2)
            if (a2 - a1) % 360.0 > 180.0:  # dimension the angle, not its complement
                a1, a2 = a2, a1
            # KOMPAS writes the angle it measures (45°21' for 45.36°). When the
            # written value agrees with the drawing, the sides are set exactly
            # to it around their bisector so the dimension reads like the source.
            sweep = (a2 - a1) % 360.0
            if d.nominal and abs(sweep - d.nominal) <= 1.0:
                mid = a1 + sweep / 2
                a1, a2 = (mid - d.nominal / 2) % 360.0, (mid + d.nominal / 2) % 360.0
            # the radius of the dimension arc is in sheet mm as well
            # never smaller than MIN_ANGULAR_RADIUS: a tiny arc is unreadable
            radius = max(d.radius or 20.0, MIN_ANGULAR_RADIUS)
            if d.text_center:
                # KOMPAS writes the value inside the arc (api_test12): the arc
                # goes out far enough for the value to stand where the source
                # has it, clear of the dimensions inside the angle.
                wanted = math.dist(d.center, d.text_center) + ANG_TEXT_INSIDE
                # not much past the source arc: two small angles side by side
                # (45° and 45° at a chamfer) would run into each other
                radius = max(radius, min(wanted, ANG_GROWTH * (d.radius or radius)))
            if "extension" not in _params(self.b.angular_dim):
                return self.b.angular_dim(self._p(d.center), a1, a2, radius, text)
            # KOMPAS draws extension lines from the vertex (on a cone they meet
            # at the apex on the axis). They are drawn here instead, from the
            # end of each side on the part out past the arc (ГОСТ 2.307).
            ref = self.b.angular_dim(self._p(d.center), a1, a2, radius, text, extension=False)
            if ref:
                for a in (a1, a2):
                    start = _side_extent(self._drawing, d.center, a)
                    if start < radius - 0.5:
                        u = (math.cos(math.radians(a)), math.sin(math.radians(a)))
                        p = (d.center[0] + u[0] * start, d.center[1] + u[1] * start)
                        q = (d.center[0] + u[0] * (radius + EXT_OVERSHOOT),
                             d.center[1] + u[1] * (radius + EXT_OVERSHOOT))
                        self.b.line(self._p(p), self._p(q), STYLE_IDS["thin"])
            return ref
        return None


DIM_LINE_GAP = 7.0  # mm on the sheet between parallel dimension lines (ГОСТ 2.307)


def spread_dimension_lines(dims) -> int:
    """Move dimension lines apart where two parallel ones on the same side of
    the part overlap along their length and stand closer than DIM_LINE_GAP.
    The outer one goes outwards; a chain (lines one after another on one
    level) is left as it is. Returns how many were moved."""
    moved = 0
    for orient, axis in (("horizontal", 1), ("vertical", 0)):
        group = [d for d in dims if d.dim_type == "linear" and d.orientation == orient
                 and d.p1 and d.p2 and d.line_point]
        for side in (1, -1):
            # dimension lines on this side of their measured points, nearest first
            same = [d for d in group
                    if side * (d.line_point[axis] - min(d.p1[axis], d.p2[axis], key=lambda v: side * v)) > 0]
            same.sort(key=lambda d: side * d.line_point[axis])
            placed = []
            for d in same:
                lo, hi = sorted((d.p1[1 - axis], d.p2[1 - axis]))
                level = d.line_point[axis]
                for other_level, olo, ohi in placed:
                    overlap = min(hi, ohi) - max(lo, olo)
                    if overlap > 0.5 and side * (level - other_level) < DIM_LINE_GAP:
                        level = other_level + side * DIM_LINE_GAP
                if abs(level - d.line_point[axis]) > 1e-6:
                    lp = list(d.line_point)
                    lp[axis] = level
                    d.line_point = tuple(lp)
                    moved += 1
                placed.append((level, lo, hi))
    return moved


def _ends(e) -> list[tuple[int, tuple[float, float]]]:
    """(index, point) of the end points: 0 = start, 1 = end (arcs counter-clockwise)."""
    if isinstance(e, ir.Line):
        return [(0, tuple(e.p1)), (1, tuple(e.p2))]
    if isinstance(e, ir.Arc):
        return [(i, (e.center[0] + e.radius * math.cos(math.radians(a)),
                     e.center[1] + e.radius * math.sin(math.radians(a))))
                for i, a in ((0, e.start_angle), (1, e.end_angle))]
    return []


def _shared_ends(drawing: ir.Drawing, tol: float = 0.01):
    """Pairs of objects whose end points coincide: (id_a, index_a, id_b, index_b).
    Several objects at one node are chained (a–b, b–c), not all pairs."""
    nodes: list[tuple[tuple[float, float], list[tuple[str, int]]]] = []
    for e in drawing.of_type(ir.Line) + drawing.of_type(ir.Arc):
        if getattr(e, "style", None) == ir.STYLE_AXIAL:
            continue
        for i, p in _ends(e):
            for q, members in nodes:
                if math.dist(p, q) <= tol:
                    members.append((e.id, i))
                    break
            else:
                nodes.append((p, [(e.id, i)]))
    out = []
    for _, members in nodes:
        for (a, ia), (b, ib) in zip(members, members[1:]):
            if a != b:
                out.append((a, ia, b, ib))
    return out


def _side_extent(drawing: ir.Drawing, center, angle: float, tol: float = 0.3) -> float:
    """How far from the vertex the drawn side of an angle reaches along the
    ray at ``angle`` (sheet mm); 0 when no line lies on that ray."""
    if drawing is None:
        return 0.0
    u = (math.cos(math.radians(angle)), math.sin(math.radians(angle)))
    reach = 0.0
    for e in drawing.of_type(ir.Line):
        if e.style == ir.STYLE_AXIAL:
            continue
        ts = []
        for q in (e.p1, e.p2):
            dx, dy = q[0] - center[0], q[1] - center[1]
            if abs(-dx * u[1] + dy * u[0]) > tol:
                break
            ts.append(dx * u[0] + dy * u[1])
        else:
            if max(ts) > 0.5 and min(ts) > -0.5:
                reach = max(reach, max(ts))
    return reach


def _polar(center, p) -> float:
    return math.degrees(math.atan2(p[1] - center[1], p[0] - center[0])) % 360.0
