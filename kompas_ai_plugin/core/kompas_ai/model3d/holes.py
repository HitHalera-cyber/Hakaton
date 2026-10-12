"""Holes along the axis of a turned part (the bolt holes of a flange): small
circles off the centre of the end view. The revolve makes a solid ring
there (the section's gap is bridged, revolve._bridge_holes); each hole is
drilled through along the axis.

Coordinates of the result are those of the 3D part: Y in the plane of the
revolve profile (away from the axis on the profile's side), Z square to it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .. import ir


@dataclass
class AxialHole:
    y: float
    z: float
    radius: float

    def text(self) -> str:
        return f"Ø{2 * self.radius:g} на радиусе {math.hypot(self.y, self.z):g}"


def find_axial_holes(drawing: ir.Drawing, profile) -> list[AxialHole]:
    from .channels import _end_views

    scale = drawing.scale.value or 1.0
    (x1, y1), (x2, y2) = profile.axis
    n = math.hypot(x2 - x1, y2 - y1) or 1.0
    ux, uy = (x2 - x1) / n, (y2 - y1) / n
    nx, ny = -uy * profile.side, ux * profile.side  # towards the profile: model Y
    largest = max(y for ring in profile.rings for _, y in ring)
    out = []
    for centre, outer in _end_views(drawing, profile.axis):
        if abs(outer / scale - largest) > max(0.5, 0.05 * largest):
            continue  # not the end view of this part
        for c in drawing.of_type(ir.Circle):
            if c.style != ir.STYLE_MAIN:
                continue
            dx, dy = c.center[0] - centre[0], c.center[1] - centre[1]
            off = math.hypot(dx, dy)
            if off < 0.5 or off + c.radius > outer + 0.1 or c.radius > 0.4 * outer:
                continue
            out.append(AxialHole(round((dx * nx + dy * ny) / scale, 4),
                                 round((dx * -ny + dy * nx) / scale, 4),
                                 round(c.radius / scale, 4)))
        if out:
            break
    return _regular(out)


def _regular(holes: list[AxialHole]) -> list[AxialHole]:
    """Holes of one size on one circle: one pitch radius (its round value),
    equally spaced when they are about so (6 holes every 60°) — the PDF's
    positions are a tenth of a millimetre off."""
    from ..geometry.regularize import _nice

    groups: dict[float, list] = {}
    for h in holes:
        key = next((k for k in groups if abs(k - h.radius) <= 0.02 * k), h.radius)
        groups.setdefault(key, []).append(h)
    out = []
    for size, group in groups.items():
        radii = [math.hypot(h.y, h.z) for h in group]
        mean = sum(radii) / len(radii)
        if len(group) < 2 or max(abs(r - mean) for r in radii) > 0.03 * mean:
            out += group
            continue
        pitch = _nice(mean, 1.0) or mean
        angles = sorted(math.degrees(math.atan2(h.z, h.y)) % 360.0 for h in group)
        step = 360.0 / len(angles)
        even = all(abs(((b - a) % 360.0) - step) <= 1.5
                   for a, b in zip(angles, angles[1:] + angles[:1]))
        if even:
            first = round(angles[0] % step * 2) / 2  # to half a degree
            angles = [first + k * step for k in range(len(angles))]
        for a in angles:
            t = math.radians(a)
            out.append(AxialHole(round(pitch * math.cos(t), 6), round(pitch * math.sin(t), 6),
                                 size))
    return out
