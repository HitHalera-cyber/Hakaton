"""Detect hatching: families of thin parallel lines with regular spacing."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import median

from ..geometry.fitting import angle_diff, direction_deg
from ..geometry.segmentation import Primitive

MIN_LINES = 4
ANGLE_BIN = 1.0  # deg
AXIS_EXCLUSION = 2.0  # deg; lines near 0/90 are left to dimensions and axes


@dataclass
class HatchGroup:
    angle: float
    spacing: float
    lines: list[Primitive] = field(default_factory=list)


def detect_hatches(thin_lines: list[Primitive]) -> tuple[list[HatchGroup], list[Primitive]]:
    """Split thin lines into hatch groups and the remaining (non-hatch) lines."""
    families: dict[int, list[Primitive]] = {}
    for line in thin_lines:
        ang = direction_deg(line.p1, line.p2)
        if min(angle_diff(ang, 0.0), angle_diff(ang, 90.0)) <= AXIS_EXCLUSION:
            continue
        families.setdefault(round(ang / ANGLE_BIN) % round(180 / ANGLE_BIN), []).append(line)

    hatches: list[HatchGroup] = []
    used: set[int] = set()
    for key, lines in families.items():
        if len(lines) < MIN_LINES:
            continue
        angle = median(direction_deg(l.p1, l.p2) for l in lines)
        for component in _components(lines, angle):
            if len(component) < MIN_LINES:
                continue
            spacing = _spacing(component, angle)
            if spacing is None:
                continue
            hatches.append(HatchGroup(angle=angle, spacing=spacing, lines=component))
            used.update(id(l) for l in component)

    rest = [l for l in thin_lines if id(l) not in used]
    rest = _absorb_strays(hatches, rest)
    return hatches, rest


def _absorb_strays(hatches: list[HatchGroup], rest: list[Primitive]) -> list[Primitive]:
    """Attach short hatch strokes (clipped in narrow corners) to the matching group.

    A stray belongs to a group when it has the group's angle, lies on the
    group's line lattice (offset is a multiple of the spacing) and is near the
    group's strokes.
    """
    remaining = []
    for line in rest:
        ang = direction_deg(line.p1, line.p2)
        target = None
        for g in hatches:
            if angle_diff(ang, g.angle) > ANGLE_BIN:
                continue
            u, n = _frame(g.angle)
            ref = _offset(g.lines[0], n)
            k = (_offset(line, n) - ref) / g.spacing
            if abs(k - round(k)) > 0.12:
                continue
            mid = ((line.p1[0] + line.p2[0]) / 2, (line.p1[1] + line.p2[1]) / 2)
            near = min(min(math.dist(mid, l.p1), math.dist(mid, l.p2)) for l in g.lines)
            if near <= 3 * g.spacing + 5.0:
                target = g
                break
        if target is None:
            remaining.append(line)
        else:
            target.lines.append(line)
    return remaining


def _frame(angle: float):
    a = math.radians(angle)
    u = (math.cos(a), math.sin(a))
    n = (-u[1], u[0])
    return u, n


def _offset(line: Primitive, n) -> float:
    mx, my = (line.p1[0] + line.p2[0]) / 2, (line.p1[1] + line.p2[1]) / 2
    return mx * n[0] + my * n[1]


def _extent(line: Primitive, u) -> tuple[float, float]:
    a = line.p1[0] * u[0] + line.p1[1] * u[1]
    b = line.p2[0] * u[0] + line.p2[1] * u[1]
    return min(a, b), max(a, b)


def _nominal_spacing(lines, n) -> float:
    offsets = sorted({round(_offset(l, n), 2) for l in lines})
    diffs = [b - a for a, b in zip(offsets, offsets[1:]) if b - a > 0.3]
    return median(diffs) if diffs else 0.0


def _components(lines: list[Primitive], angle: float) -> list[list[Primitive]]:
    u, n = _frame(angle)
    s = _nominal_spacing(lines, n)
    if s <= 0:
        return []
    offsets = [_offset(l, n) for l in lines]
    extents = [_extent(l, u) for l in lines]
    parent = list(range(len(lines)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(lines)):
        for j in range(i + 1, len(lines)):
            if abs(offsets[i] - offsets[j]) > 1.5 * s:
                continue
            gap = max(extents[i][0], extents[j][0]) - min(extents[i][1], extents[j][1])
            if gap <= 2 * s:
                parent[find(i)] = find(j)

    groups: dict[int, list[Primitive]] = {}
    for i, line in enumerate(lines):
        groups.setdefault(find(i), []).append(line)
    return list(groups.values())


def _spacing(lines: list[Primitive], angle: float) -> float | None:
    """Regular spacing of the group, or None when spacing is irregular."""
    _, n = _frame(angle)
    offsets = sorted({round(_offset(l, n), 2) for l in lines})
    diffs = [b - a for a, b in zip(offsets, offsets[1:]) if b - a > 0.3]
    if len(diffs) < MIN_LINES - 2:
        return None
    s = median(diffs)
    regular = [d for d in diffs if abs(d / s - round(d / s)) < 0.15]
    return s if len(regular) >= 0.8 * len(diffs) else None
