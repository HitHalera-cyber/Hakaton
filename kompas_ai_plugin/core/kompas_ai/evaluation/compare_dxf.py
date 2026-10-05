"""Compare a recognised drawing with a reference DXF exported from KOMPAS.

The reference holds exact geometry (true circles, real dimensions), so it
measures how well the PDF was reconstructed: matched objects, coordinate,
radius and dimension errors. Errors are given in sheet mm and in model mm
(divided by the drawing scale).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median

import ezdxf

from .. import ir
from ..geometry.fitting import point_segment_distance

AXIAL_LINETYPE_HINTS = ("AXL", "CENTER", "AXIS", "DASHDOT")
CURVE_MATCH = 0.5  # mm
LINE_MATCH = 0.5  # mm


@dataclass
class Metric:
    name: str
    reference: int
    matched: int
    max_error: float | None = None  # sheet mm (or degrees)
    mean_error: float | None = None
    details: list[str] = field(default_factory=list)

    @property
    def recall(self) -> float:
        return self.matched / self.reference if self.reference else 1.0


@dataclass
class Report:
    shift: tuple[float, float]
    scale: float
    metrics: list[Metric]
    extra: list[str]

    def text(self) -> str:
        out = [f"Сдвиг эталона относительно листа: ({self.shift[0]:+.3f}, {self.shift[1]:+.3f}) мм",
               ""]
        for m in self.metrics:
            line = f"{m.name:<22} найдено {m.matched:>3} из {m.reference:<3} ({m.recall:.0%})"
            if m.max_error is not None:
                unit = "°" if m.name.startswith("Угл") else " мм"
                line += f"; ошибка макс {m.max_error:.3f}{unit}, средн {m.mean_error:.3f}{unit}"
                if unit == " мм" and self.scale != 1.0:
                    line += f" (на детали ≈{m.max_error / self.scale:.3f} мм)"
            out.append(line)
            out.extend("    " + d for d in m.details)
        if self.extra:
            out.append("")
            out.extend(self.extra)
        return "\n".join(out)


def _is_axial(entity) -> bool:
    lt = (entity.dxf.get("linetype") or "").upper()
    return any(h in lt for h in AXIAL_LINETYPE_HINTS)


def compare(drawing: ir.Drawing, reference_dxf: str | Path) -> Report:
    doc = ezdxf.readfile(str(reference_dxf))
    msp = doc.modelspace()
    ref_circles = [(tuple(e.dxf.center)[:2], e.dxf.radius) for e in msp.query("CIRCLE")]
    ref_arcs = [(tuple(e.dxf.center)[:2], e.dxf.radius) for e in msp.query("ARC")]
    ref_lines = [((e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y), _is_axial(e))
                 for e in msp.query("LINE")]
    ref_dims = []
    for e in msp.query("DIMENSION"):
        try:
            value = e.get_measurement()
        except Exception:
            continue
        if hasattr(value, "x"):
            continue
        ref_dims.append((e.dimtype & 0x0F, float(value), e.dxf.get("text") or ""))
    ref_hatches = len(msp.query("HATCH"))

    ours_curves = drawing.of_type(ir.Circle) + drawing.of_type(ir.Arc)
    shift = _estimate_shift([c for c, _ in ref_circles + ref_arcs], [c.center for c in ours_curves])

    def moved(p):
        return (p[0] + shift[0], p[1] + shift[1])

    metrics = [
        _curves("Окружности", ref_circles, drawing.of_type(ir.Circle), moved),
        _curves("Дуги", ref_arcs, drawing.of_type(ir.Arc), moved),
        _lines("Отрезки (основные)", [l for l in ref_lines if not l[2]],
               [l for l in drawing.of_type(ir.Line) if l.style != ir.STYLE_AXIAL], moved),
        _lines("Осевые линии", [l for l in ref_lines if l[2]],
               [l for l in drawing.of_type(ir.Line) if l.style == ir.STYLE_AXIAL], moved),
        _dimensions("Размеры (линейные, Ø)", [r for r in ref_dims if r[0] not in (2, 5)],
                    [d for d in drawing.of_type(ir.Dimension) if d.dim_type != "angular"]),
        _dimensions("Угловые размеры", [r for r in ref_dims if r[0] in (2, 5)],
                    [d for d in drawing.of_type(ir.Dimension) if d.dim_type == "angular"]),
    ]
    extra = [f"Штриховки: в эталоне {ref_hatches} объект(а), распознано "
             f"{len(drawing.of_type(ir.Hatch))} областей "
             "(в эталоне одна штриховка может включать несколько контуров)."]
    return Report(shift, drawing.scale.value, metrics, extra)


def _estimate_shift(ref_centers, our_centers) -> tuple[float, float]:
    """Median offset between nearest circle centres (reference - ours)."""
    dx, dy = [], []
    for c in our_centers:
        if not ref_centers:
            break
        r = min(ref_centers, key=lambda q: math.dist(q, c))
        if math.dist(r, c) < 3.0:
            dx.append(r[0] - c[0])
            dy.append(r[1] - c[1])
    return (median(dx), median(dy)) if dx else (0.0, 0.0)


def _curves(name, refs, ours, moved) -> Metric:
    errors, matched, used = [], 0, set()
    details = []
    for center, radius in refs:
        best = None
        for i, c in enumerate(ours):
            if i in used:
                continue
            err = max(math.dist(moved(c.center), center), abs(c.radius - radius))
            if err <= CURVE_MATCH and (best is None or err < best[0]):
                best = (err, i)
        if best is None:
            details.append(f"не найдена: центр ({center[0]:.2f}, {center[1]:.2f}), R{radius:.3f}")
            continue
        used.add(best[1])
        matched += 1
        errors.append(best[0])
    m = Metric(name, len(refs), matched, details=details)
    if errors:
        m.max_error, m.mean_error = max(errors), sum(errors) / len(errors)
    extra = len(ours) - len(used)
    if extra > 0:
        m.details.append(f"лишних (нет в эталоне): {extra}")
    return m


def _lines(name, refs, ours, moved) -> Metric:
    """A reference line is matched when one of ours covers it end to end."""
    errors, matched, details = [], 0, []
    for a, b, _ in refs:
        best = None
        for i, l in enumerate(ours):
            p1, p2 = moved(l.p1), moved(l.p2)
            # distance of the reference ends to our segment, and of ours to the reference
            err = max(point_segment_distance(a, p1, p2), point_segment_distance(b, p1, p2))
            if err <= LINE_MATCH and (best is None or err < best[0]):
                best = (err, i)
        if best is None:
            details.append(f"не найден: ({a[0]:.2f}, {a[1]:.2f}) – ({b[0]:.2f}, {b[1]:.2f})")
            continue
        matched += 1
        errors.append(best[0])
    m = Metric(name, len(refs), matched, details=details)
    if errors:
        m.max_error, m.mean_error = max(errors), sum(errors) / len(errors)
    return m


def _dimensions(name, refs, ours: list[ir.Dimension]) -> Metric:
    errors, matched, used, details = [], 0, set(), []
    for dimtype, value, text in refs:
        angular = dimtype in (2, 5)
        best = None
        for i, d in enumerate(ours):
            if i in used or (d.dim_type == "angular") != angular or d.measured is None:
                continue
            measured = d.measured
            ref_value = value
            if angular:
                ref_value = min(value % 360, 360 - value % 360)
            err = abs(measured - ref_value)
            if err <= (1.0 if angular else 0.3) and (best is None or err < best[0]):
                best = (err, i)
        if best is None:
            details.append(f"не найден размер {text!r} = {value:.3f}")
            continue
        used.add(best[1])
        matched += 1
        errors.append(best[0])
    m = Metric(name, len(refs), matched, details=details)
    if errors:
        m.max_error, m.mean_error = max(errors), sum(errors) / len(errors)
    return m
