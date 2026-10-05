"""Least-squares fitting of lines and circles to point sets."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass
class LineFit:
    p1: tuple[float, float]
    p2: tuple[float, float]
    max_error: float


@dataclass
class CircleFit:
    center: tuple[float, float]
    radius: float
    max_error: float
    rms_error: float


def fit_line(points) -> LineFit:
    """Total least squares line; endpoints are the extreme projections."""
    pts = np.asarray(points, dtype=float)
    centroid = pts.mean(axis=0)
    _, _, vt = np.linalg.svd(pts - centroid)
    direction = vt[0]
    normal = vt[1]
    t = (pts - centroid) @ direction
    dist = np.abs((pts - centroid) @ normal)
    p1 = centroid + direction * t.min()
    p2 = centroid + direction * t.max()
    # Keep the endpoint order of the input.
    if np.linalg.norm(p1 - pts[0]) > np.linalg.norm(p2 - pts[0]):
        p1, p2 = p2, p1
    return LineFit((float(p1[0]), float(p1[1])), (float(p2[0]), float(p2[1])),
                   float(dist.max()))


def fit_circle(points, iterations: int = 10) -> CircleFit | None:
    """Algebraic (Kåsa) fit refined by Gauss–Newton on geometric distance."""
    pts = np.asarray(points, dtype=float)
    if len(pts) < 3:
        return None
    x, y = pts[:, 0], pts[:, 1]
    a = np.column_stack([x, y, np.ones_like(x)])
    b = x * x + y * y
    try:
        sol, *_ = np.linalg.lstsq(a, b, rcond=None)
    except np.linalg.LinAlgError:
        return None
    cx, cy = sol[0] / 2, sol[1] / 2
    r2 = sol[2] + cx * cx + cy * cy
    if r2 <= 0:
        return None
    r = math.sqrt(r2)
    for _ in range(iterations):
        dx, dy = x - cx, y - cy
        d = np.hypot(dx, dy)
        if np.any(d < 1e-12):
            break
        residual = d - r
        jac = np.column_stack([-dx / d, -dy / d, -np.ones_like(d)])
        step, *_ = np.linalg.lstsq(jac, -residual, rcond=None)
        cx, cy, r = cx + step[0], cy + step[1], r + step[2]
        if np.abs(step).max() < 1e-10:
            break
    residual = np.hypot(x - cx, y - cy) - r
    return CircleFit((float(cx), float(cy)), float(abs(r)),
                     float(np.abs(residual).max()), float(np.sqrt((residual ** 2).mean())))


def point_line_distance(p, a, b) -> float:
    ax, ay = a
    bx, by = b
    length = math.hypot(bx - ax, by - ay)
    if length < 1e-12:
        return math.dist(p, a)
    return abs((bx - ax) * (ay - p[1]) - (ax - p[0]) * (by - ay)) / length


def point_segment_distance(p, a, b) -> float:
    ax, ay = a
    bx, by = b
    vx, vy = bx - ax, by - ay
    length2 = vx * vx + vy * vy
    if length2 < 1e-12:
        return math.dist(p, a)
    t = max(0.0, min(1.0, ((p[0] - ax) * vx + (p[1] - ay) * vy) / length2))
    return math.dist(p, (ax + t * vx, ay + t * vy))


def turning_angles(points) -> list[float]:
    """Signed turning angle (degrees) at every interior vertex of a polyline."""
    out = []
    for p0, p1, p2 in zip(points, points[1:], points[2:]):
        a1 = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
        a2 = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
        d = math.degrees(a2 - a1)
        out.append((d + 180.0) % 360.0 - 180.0)
    return out


def angle_of(center, p) -> float:
    """Polar angle of ``p`` around ``center`` in degrees, 0..360."""
    return math.degrees(math.atan2(p[1] - center[1], p[0] - center[0])) % 360.0


def direction_deg(a, b) -> float:
    """Undirected line direction, degrees in [0, 180)."""
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180.0


def angle_diff(a: float, b: float, period: float = 180.0) -> float:
    d = (a - b) % period
    return min(d, period - d)
