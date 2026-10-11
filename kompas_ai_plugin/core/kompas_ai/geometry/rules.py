"""Rules a drawing must keep before it goes to KOMPAS.

1. A main line is horizontal or vertical, or runs at a standard angle
   (15°, 30°, 45°, 60°, 75°) — a chamfer or a cone; anything else is listed.
2. The contour is closed: every end of a main line or arc meets another end
   exactly (or rests on another line), no gaps of a few hundredths.
Each broken rule is reported with the object, so it can be found on the sheet.
"""

from __future__ import annotations

import math

from .. import ir

STANDARD_ANGLES = (0.0, 15.0, 30.0, 45.0, 60.0, 75.0, 90.0)
EXACT = 1e-6


def check(drawing: ir.Drawing) -> list[str]:
    out = []
    pieces = [e for e in drawing.entities if isinstance(e, (ir.Line, ir.Arc))
              and e.style == ir.STYLE_MAIN]
    for line in (e for e in pieces if isinstance(e, ir.Line)):
        (x1, y1), (x2, y2) = line.p1, line.p2
        if math.hypot(x2 - x1, y2 - y1) < 1e-9:
            continue
        ang = math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180.0
        a = min(ang, 180.0 - ang)  # 0…90 from horizontal
        if min(abs(a - s) for s in STANDARD_ANGLES) > 1e-3:
            out.append(f"{line.id}: наклон {a:.3f}° — не горизонталь, не вертикаль и не "
                       f"стандартный угол")

    ends = []
    for e in pieces:
        if isinstance(e, ir.Line):
            ends += [(e, tuple(e.p1)), (e, tuple(e.p2))]
        else:
            for t in (e.start_angle, e.end_angle):
                r = math.radians(t)
                ends.append((e, (e.center[0] + e.radius * math.cos(r),
                                 e.center[1] + e.radius * math.sin(r))))
    lines = [e for e in pieces if isinstance(e, ir.Line)] + [
        e for e in drawing.of_type(ir.Line) if e.style == ir.STYLE_AXIAL]
    for e, p in ends:
        if any(o is not e and math.dist(p, q) <= EXACT for o, q in ends):
            continue
        gap = min((math.dist(p, q) for o, q in ends if o is not e), default=math.inf)
        on_line = any(o is not e and _on_segment(p, o) for o in lines)
        if on_line:
            continue
        if gap < 0.3:
            out.append(f"{e.id}: конец ({p[0]:.3f}; {p[1]:.3f}) не сходится с соседним "
                       f"на {gap:.3f} мм")
        else:
            out.append(f"{e.id}: свободный конец ({p[0]:.3f}; {p[1]:.3f})")
    return out


def _on_segment(p, line, tol: float = 1e-6) -> bool:
    (ax, ay), (bx, by) = line.p1, line.p2
    dx, dy = bx - ax, by - ay
    n2 = dx * dx + dy * dy
    if n2 < 1e-18:
        return False
    t = ((p[0] - ax) * dx + (p[1] - ay) * dy) / n2
    if not -1e-9 <= t <= 1 + 1e-9:
        return False
    return math.dist(p, (ax + t * dx, ay + t * dy)) <= tol
