"""Arrowheads: filled triangles at the ends of dimension lines.

KOMPAS rasterises arrowheads into staircase polygons and splits each into two
halves, so touching fills are merged first. The tip is the end of the
principal axis where the polygon is narrow.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from ..pdf.vector_extractor import RawFill

TOUCH_TOLERANCE = 0.2  # mm between halves of one arrow
MIN_LENGTH, MAX_LENGTH = 1.0, 12.0  # mm
MIN_ELONGATION = 1.8  # length / width


@dataclass
class Arrow:
    tip: tuple[float, float]
    direction: tuple[float, float]  # unit vector from the base to the tip
    length: float
    points: list[tuple[float, float]]


def _bbox(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def _touch(b1, b2, tol=TOUCH_TOLERANCE) -> bool:
    return not (b1[2] + tol < b2[0] or b2[2] + tol < b1[0] or
                b1[3] + tol < b2[1] or b2[3] + tol < b1[1])


def find_arrows(fills: list[RawFill]) -> list[Arrow]:
    groups: list[list[tuple[float, float]]] = []
    boxes: list[tuple] = []
    arrows = []
    for f in fills:
        # A clean filled triangle (AutoCAD, SolidWorks…) is a whole arrow; it
        # must not be merged with the arrow of a neighbouring chain dimension
        # touching it tip to tip.
        whole = _arrow_from_triangle(f.points)
        if whole is not None:
            arrows.append(whole)
            continue
        box = _bbox(f.points)
        for i, b in enumerate(boxes):
            if _touch(b, box):
                groups[i].extend(f.points)
                boxes[i] = _bbox(groups[i])
                break
        else:
            groups.append(list(f.points))
            boxes.append(box)
    for pts in groups:
        arrow = _arrow_from_points(pts)
        if arrow is not None:
            arrows.append(arrow)
    return arrows


def _arrow_from_triangle(points) -> Arrow | None:
    """An isosceles triangle with a sharp apex. (The halves KOMPAS splits its
    arrows into are right triangles, so they are left to be merged.)"""
    corners = []
    for p in points:
        if all(math.dist(p, q) > 0.02 for q in corners):
            corners.append(p)
    if len(corners) != 3:
        return None
    for i in range(3):
        tip, b1, b2 = corners[i], corners[i - 1], corners[(i + 1) % 3]
        s1, s2 = math.dist(tip, b1), math.dist(tip, b2)
        base = math.dist(b1, b2)
        if not s1 or not s2 or abs(s1 - s2) > 0.1 * max(s1, s2) or base >= 0.6 * min(s1, s2):
            continue
        mid = ((b1[0] + b2[0]) / 2, (b1[1] + b2[1]) / 2)
        length = math.dist(tip, mid)
        if not MIN_LENGTH <= length <= MAX_LENGTH:
            return None
        d = ((tip[0] - mid[0]) / length, (tip[1] - mid[1]) / length)
        return Arrow(tip=(float(tip[0]), float(tip[1])), direction=d, length=length,
                     points=[tuple(c) for c in corners])
    return None


def _arrow_from_points(points) -> Arrow | None:
    pts = np.asarray(points, dtype=float)
    centroid = pts.mean(axis=0)
    _, _, vt = np.linalg.svd(pts - centroid)
    axis, normal = vt[0], vt[1]
    t = (pts - centroid) @ axis
    w = (pts - centroid) @ normal
    length = float(t.max() - t.min())
    width = float(w.max() - w.min())
    if not (MIN_LENGTH <= length <= MAX_LENGTH) or width <= 0 or length / width < MIN_ELONGATION:
        return None
    # Width near each end of the axis: the tip end is the narrow one.
    span = length * 0.25
    lo = w[t <= t.min() + span]
    hi = w[t >= t.max() - span]
    lo_w = lo.max() - lo.min() if len(lo) else 0.0
    hi_w = hi.max() - hi.min() if len(hi) else 0.0
    if hi_w < lo_w:
        tip_t, direction = t.max(), axis
    else:
        tip_t, direction = t.min(), -axis
    # Along the axis the tip is the extreme point; across it, the mean of the
    # vertices near that end (the staircase makes single vertices jittery).
    near = np.abs(t - tip_t) < 0.15
    across = w[near].mean() if near.any() else 0.0
    tip = centroid + axis * tip_t + normal * across
    d = direction / np.linalg.norm(direction)
    return Arrow(tip=(float(tip[0]), float(tip[1])), direction=(float(d[0]), float(d[1])),
                 length=length, points=[tuple(p) for p in points])


def arrow_angle(arrow: Arrow) -> float:
    return math.degrees(math.atan2(arrow.direction[1], arrow.direction[0])) % 360.0


def arrows_from_chains(chains) -> tuple[list[Arrow], list]:
    """Find arrowheads drawn as small closed outlines (tip–side–notch–side).

    Returns the arrows and the chains that are not arrow outlines. Outline
    vertices are exact (unlike the rasterised fill), so these arrows give the
    precise tip position.
    """
    arrows, rest = [], []
    for chain in chains:
        arrow = _arrow_from_outline(chain) if chain.closed else None
        if arrow is None:
            rest.append(chain)
        else:
            arrows.append(arrow)
    return arrows, rest


def _arrow_from_outline(chain) -> Arrow | None:
    pts = chain.points[:-1] if chain.points[0] == chain.points[-1] else chain.points
    if not 3 <= len(pts) <= 4:
        return None
    perimeter = sum(math.dist(a, b) for a, b in zip(chain.points, chain.points[1:]))
    if not 2 * MIN_LENGTH <= perimeter <= 3 * MAX_LENGTH:
        return None
    # The tip is the vertex with the sharpest interior angle.
    best, best_angle = None, 181.0
    n = len(pts)
    for i in range(n):
        p_prev, p, p_next = pts[i - 1], pts[i], pts[(i + 1) % n]
        a1 = math.atan2(p_prev[1] - p[1], p_prev[0] - p[0])
        a2 = math.atan2(p_next[1] - p[1], p_next[0] - p[0])
        ang = abs(math.degrees((a2 - a1 + math.pi) % (2 * math.pi) - math.pi))
        if ang < best_angle:
            best, best_angle = i, ang
    if best_angle > 35.0:
        return None
    tip = pts[best]
    others = [p for j, p in enumerate(pts) if j != best]
    far = max(others, key=lambda p: math.dist(p, tip))
    length = math.dist(far, tip)
    base = (sum(p[0] for p in others) / len(others), sum(p[1] for p in others) / len(others))
    dx, dy = tip[0] - base[0], tip[1] - base[1]
    norm = math.hypot(dx, dy)
    if norm < 1e-9 or not MIN_LENGTH <= length <= MAX_LENGTH:
        return None
    return Arrow(tip=tip, direction=(dx / norm, dy / norm), length=length, points=list(pts))


def merge_arrow_sources(outline_arrows: list[Arrow], fill_arrows: list[Arrow]) -> list[Arrow]:
    """Prefer exact outline arrows; keep fill arrows that have no outline twin."""
    out = list(outline_arrows)
    for fa in fill_arrows:
        if all(math.dist(fa.tip, oa.tip) > 0.6 for oa in outline_arrows):
            out.append(fa)
    return out
