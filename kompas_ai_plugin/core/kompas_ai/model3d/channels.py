"""Drilled channels across the axis of a turned part (the swirl channels of
an injector): a pair of parallel lines across the wall in the end view, and
the same diameter as a small circle in the main view.

The end view is a set of concentric circles off the part's axis; inside its
outer circle every two parallel straight lines a hole's width apart (along
the view's axes) are the walls of one channel: its axis runs between them,
from the side nearer the centre out through the outside. The main view
shows where along the part the channels are: a circle of the channel's
diameter inside the part (the channel cut by the section).

Coordinates of the result are those of the 3D part: X along the axis (the
profile's x), the end view's horizontal as Y and its vertical as Z.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .. import ir

PARALLEL = 0.02  # sheet mm: lines this close to horizontal/vertical count as such
CONCENTRIC = 0.3


@dataclass
class ChannelSpec:
    x: float  # along the part's axis, model mm
    along: int  # 1: the channel runs along Y, 2: along Z
    sign: int  # +1 / -1: outwards along that axis
    offset: float  # the other coordinate of its axis (Z for a Y channel, Y for a Z one)
    radius: float
    length: float  # from the plane through the part's axis out past the outside

    def text(self) -> str:
        return (f"канал Ø{2 * self.radius:g} вдоль {'Y' if self.along == 1 else 'Z'}"
                f"{'+' if self.sign > 0 else '−'}, смещение {self.offset:+.2f}, x = {self.x:.2f}")


def _end_views(drawing, axis):
    """(centre, outer radius) of the concentric circle sets off the axis."""
    circles = [c for c in drawing.of_type(ir.Circle) if c.style == ir.STYLE_MAIN]
    out = []
    for c in circles:
        same = [d for d in circles if math.dist(d.center, c.center) <= CONCENTRIC]
        if len(same) < 2 or any(math.dist(c.center, o[0]) <= CONCENTRIC for o in out):
            continue
        along = _along_axis(c.center, axis)
        if _off_axis(c.center, axis) < 5.0 and -5.0 <= along <= math.dist(*axis) + 5.0:
            continue  # on the part's axis itself: a hole seen along it, not the end view
        out.append((tuple(c.center), max(d.radius for d in same)))
    return out


def _off_axis(p, axis):
    (x1, y1), (x2, y2) = axis
    n = math.dist(axis[0], axis[1]) or 1.0
    return abs((p[0] - x1) * (y2 - y1) - (p[1] - y1) * (x2 - x1)) / n


def _along_axis(p, axis):
    (x1, y1), (x2, y2) = axis
    n = math.dist(axis[0], axis[1]) or 1.0
    return ((p[0] - x1) * (x2 - x1) + (p[1] - y1) * (y2 - y1)) / n


def find_channels(drawing: ir.Drawing, profile) -> list[ChannelSpec]:
    scale = drawing.scale.value or 1.0
    out: list[ChannelSpec] = []
    for centre, outer in _end_views(drawing, profile.axis):
        cx, cy = centre
        lines = []
        for l in drawing.of_type(ir.Line):
            if l.style != ir.STYLE_MAIN or math.dist(l.p1, l.p2) < 0.2 * outer:
                continue
            if any(math.dist(p, centre) > outer + 0.5 for p in (l.p1, l.p2)):
                continue
            if abs(l.p1[0] - l.p2[0]) <= PARALLEL:  # vertical: runs along the view's Z
                lines.append((2, (l.p1[0] + l.p2[0]) / 2 - cx, l.p1[1] - cy, l.p2[1] - cy))
            elif abs(l.p1[1] - l.p2[1]) <= PARALLEL:  # horizontal: along Y
                lines.append((1, (l.p1[1] + l.p2[1]) / 2 - cy, l.p1[0] - cx, l.p2[0] - cx))
        used = set()
        for i, (k1, o1, a1, b1) in enumerate(lines):
            for j, (k2, o2, a2, b2) in enumerate(lines):
                if j <= i or k1 != k2 or i in used or j in used:
                    continue
                gap = abs(o1 - o2)
                lo, hi = max(min(a1, b1), min(a2, b2)), min(max(a1, b1), max(a2, b2))
                if not (0.05 * outer < gap < 0.4 * outer) or hi - lo < 0.2 * outer:
                    continue
                # the channel leaves through the outside at the far ends
                far = max((a1, b1, a2, b2), key=abs)
                used |= {i, j}
                out.append(ChannelSpec(
                    x=0.0, along=k1, sign=1 if far > 0 else -1, offset=(o1 + o2) / 2 / scale,
                    radius=gap / 2 / scale, length=outer / scale + 1.0))
    if not out:
        return []
    # where along the part: circles of the channels' size inside the main view
    radius = _written_radius(drawing, out[0].radius)
    r_sheet = out[0].radius * scale
    span = math.dist(*profile.axis)
    top = max(y for ring in profile.rings for _, y in ring) * scale
    spots = [c.center for c in drawing.of_type(ir.Circle)
             if c.style == ir.STYLE_MAIN and abs(c.radius - r_sheet) <= 0.2 * r_sheet
             and 0 <= _along_axis(c.center, profile.axis) <= span
             and _off_axis(c.center, profile.axis) <= top]
    # the profile of the model starts at x = 0 (revolve.profile_segments puts
    # the part's end there, on its grid): measure from the part's end
    x0 = min(x for ring in profile.rings for x, _ in ring)
    xs = sorted({round(round((_written_x(drawing, profile, c) - x0) / 0.005) * 0.005, 3)
                 for c in spots})
    return [ChannelSpec(x, c.along, c.sign, c.offset, radius, c.length)
            for x in xs for c in out]


def _written_radius(drawing, measured: float) -> float:
    """The channel's diameter as written (Ø0,8), when one is close."""
    for d in drawing.of_type(ir.Dimension):
        if (d.text or "").lstrip().startswith("Ø") and d.nominal \
                and abs(d.nominal / 2 - measured) <= 0.05 * measured:
            return d.nominal / 2
    return measured


def _written_x(drawing, profile, centre) -> float:
    """Where along the part the channel is (model mm from the axis' start):
    by a size along the axis from the channel's centre, when there is one —
    the number wins over the lines."""
    scale = drawing.scale.value or 1.0
    at = _along_axis(centre, profile.axis)
    for d in drawing.of_type(ir.Dimension):
        if d.dim_type != "linear" or not d.p1 or not d.p2 or not d.nominal:
            continue
        a1, a2 = _along_axis(d.p1, profile.axis), _along_axis(d.p2, profile.axis)
        if abs(_off_axis(d.p1, profile.axis) - _off_axis(d.p2, profile.axis)) > 0.5:
            continue  # not along the axis
        for here, there in ((a1, a2), (a2, a1)):
            if abs(here - at) <= 0.3 and abs(abs(here - there) / scale - d.nominal) <= 0.1:
                return there / scale + d.nominal * (1 if here > there else -1)
    return at / scale
