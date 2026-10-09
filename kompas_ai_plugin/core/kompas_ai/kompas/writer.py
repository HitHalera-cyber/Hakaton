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


class DrawingWriter:
    def __init__(self, backend: Backend, mode: str = "sheet", with_dimensions: bool = True):
        self.b = backend
        self.mode = mode
        # False: a plain drawing (lines, arcs, texts, hatches) without dimensions
        self.with_dimensions = with_dimensions
        self.scale = 1.0
        self.origin = (0.0, 0.0)  # sheet point of the view origin (view mode)

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

        order = (ir.Hatch, ir.Line, ir.Circle, ir.Arc, ir.PointMark, ir.Text) \
            + ((ir.Dimension,) if self.with_dimensions else ())
        for cls in order:
            for e in drawing.of_type(cls):
                try:
                    ref = self._write(e, drawing)
                except Exception as exc:  # one bad object must not stop the drawing
                    ref = None
                    report.notes.append(f"{e.id}: {exc!r}")
                if ref:
                    report.count(e.kind)
                elif ref is not False:  # False = intentionally skipped
                    report.failed.append(e.id)
        return report

    # --- entities ----------------------------------------------------------------------

    def _write(self, e: ir.Entity, drawing: ir.Drawing):
        if isinstance(e, ir.Line):
            return self.b.line(self._p(e.p1), self._p(e.p2), STYLE_IDS.get(e.style, 1))
        if isinstance(e, ir.Circle):
            return self.b.circle(self._p(e.center), self._len(e.radius), STYLE_IDS.get(e.style, 1))
        if isinstance(e, ir.Arc):
            return self.b.arc(self._p(e.center), self._len(e.radius), e.start_angle, e.end_angle,
                              STYLE_IDS.get(e.style, 1))
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
            line = self._p(d.line_point or d.p1)
            if d.orientation == "horizontal":
                kind, offset = LINEAR_HORIZONTAL, (0.0, line[1] - p1[1])
            elif d.orientation == "vertical":
                kind, offset = LINEAR_VERTICAL, (line[0] - p1[0], 0.0)
            else:
                kind, offset = LINEAR_PARALLEL, (line[0] - p1[0], line[1] - p1[1])
            return self.b.linear_dim(p1, p2, offset, kind, text)
        if d.dim_type in ("diameter", "radius") and d.center and d.radius:
            angle = 45.0
            if d.p1:
                angle = math.degrees(math.atan2(d.p1[1] - d.center[1], d.p1[0] - d.center[0]))
            if d.dim_type == "radius" and not text.auto:
                text.value = "R" + text.value.lstrip("R")
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
            return self.b.angular_dim(self._p(d.center), a1, a2, self._len(d.radius or 20.0), text)
        return None


def _polar(center, p) -> float:
    return math.degrees(math.atan2(p[1] - center[1], p[0] - center[0])) % 360.0
