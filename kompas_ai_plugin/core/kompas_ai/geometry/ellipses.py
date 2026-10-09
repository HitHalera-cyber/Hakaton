"""Ellipses drawn as a closed chain of arcs.

A hole seen at an angle is an ellipse; exporters often write it as four
(or more) arcs. A closed loop made only of arcs that join smoothly and lie
on one ellipse is replaced by that ellipse.
"""

from __future__ import annotations

import math

import numpy as np

from .. import ir

JOIN = 0.2  # mm between the ends of neighbouring pieces
SMOOTH = 10.0  # degrees between the tangents at a joint
FIT = 0.05  # mm: the pieces must lie this close to the ellipse
FIT_REL = 0.05  # … or this part of the minor semi-axis: a four-arc oval is not a true ellipse
MIN_RATIO = 1.03  # a/b; rounder loops are left as they are


def _ends(arc):
    if isinstance(arc, ir.Line):
        return [tuple(arc.p1), tuple(arc.p2)]
    out = []
    for a in (arc.start_angle, arc.end_angle):
        t = math.radians(a)
        out.append((arc.center[0] + arc.radius * math.cos(t), arc.center[1] + arc.radius * math.sin(t)))
    return out


def _loops(arcs) -> list[list]:
    """Closed chains of arcs and lines (each joint shared by exactly two)."""
    nodes: list[tuple[float, float]] = []
    touch: list[list[int]] = []
    arc_nodes = []
    for i, arc in enumerate(arcs):
        ids = []
        for p in _ends(arc):
            for k, q in enumerate(nodes):
                if math.dist(p, q) <= JOIN:
                    break
            else:
                k = len(nodes)
                nodes.append(p)
                touch.append([])
            touch[k].append(i)
            ids.append(k)
        arc_nodes.append(ids)
    seen, loops = set(), []
    for i in range(len(arcs)):
        if i in seen:
            continue
        loop, cur, node, ok = [i], i, arc_nodes[i][1], True
        while True:
            if len(touch[node]) != 2:
                ok = False
                break
            nxt = touch[node][0] if touch[node][1] == cur else touch[node][1]
            if nxt == i:
                break
            if nxt in loop:
                ok = False
                break
            loop.append(nxt)
            a, b = arc_nodes[nxt]
            node = b if a == node else a
            cur = nxt
        seen.update(loop)
        if ok and 2 <= len(loop) <= 12:
            loops.append([arcs[k] for k in loop])
    return loops


def _samples(loop, n=24):
    pts = []
    for arc in loop:
        if isinstance(arc, ir.Line):
            pts += [(arc.p1[0] + (arc.p2[0] - arc.p1[0]) * k / 4,
                     arc.p1[1] + (arc.p2[1] - arc.p1[1]) * k / 4) for k in range(5)]
            continue
        sweep = (arc.end_angle - arc.start_angle) % 360.0 or 360.0
        for k in range(n + 1):
            t = math.radians(arc.start_angle + sweep * k / n)
            pts.append((arc.center[0] + arc.radius * math.cos(t), arc.center[1] + arc.radius * math.sin(t)))
    return np.array(pts)


def fit_ellipse(pts: np.ndarray):
    """(center, a, b, angle_deg, max_error) of the conic through the points, or None."""
    c0 = pts.mean(axis=0)
    s = max(np.abs(pts - c0).max(), 1e-9)
    x, y = ((pts - c0) / s).T
    d = np.column_stack([x * x, x * y, y * y, x, y, np.ones_like(x)])
    _, _, vt = np.linalg.svd(d)
    A, B, C, D, E, F = vt[-1]
    det = 4 * A * C - B * B
    if det <= 0:
        return None  # not an ellipse
    x0, y0 = np.linalg.solve([[2 * A, B], [B, 2 * C]], [-D, -E])
    f0 = A * x0 * x0 + B * x0 * y0 + C * y0 * y0 + D * x0 + E * y0 + F
    lam, vec = np.linalg.eigh([[A, B / 2], [B / 2, C]])
    if f0 / lam[0] >= 0 or f0 / lam[1] >= 0:
        return None
    axes = np.sqrt(-f0 / lam)
    k = int(np.argmax(axes))  # the major axis and its direction
    a, b = axes[k] * s, axes[1 - k] * s
    angle = math.degrees(math.atan2(vec[1, k], vec[0, k])) % 180.0
    center = (c0[0] + x0 * s, c0[1] + y0 * s)
    # distance of the points to the ellipse, through the gradient of the conic
    val = d @ vt[-1]
    gx = 2 * A * x + B * y + D
    gy = B * x + 2 * C * y + E
    err = float(np.max(np.abs(val) / np.maximum(np.hypot(gx, gy), 1e-12)) * s)
    return center, float(a), float(b), angle, err


def _smooth(loop) -> bool:
    for arc, nxt in zip(loop, loop[1:] + loop[:1]):
        best = None
        for p in _ends(arc):
            for q in _ends(nxt):
                if math.dist(p, q) <= JOIN:
                    best = p
        if best is None:
            return False
        # tangent directions are square to the radii; the radii must be parallel
        ra = math.atan2(best[1] - arc.center[1], best[0] - arc.center[0])
        rb = math.atan2(best[1] - nxt.center[1], best[0] - nxt.center[0])
        diff = abs((math.degrees(ra - rb) + 90.0) % 180.0 - 90.0)
        if diff > SMOOTH:
            return False
    return True


def merge_ellipses(drawing: ir.Drawing, new_id) -> int:
    """Replace closed loops of arcs (and the short lines some exporters put
    between them) lying on one ellipse by Ellipse entities; returns how many."""
    pieces = [e for e in drawing.of_type(ir.Arc) + drawing.of_type(ir.Line)
              if e.style == ir.STYLE_MAIN]
    made = 0
    for loop in _loops(pieces):
        arcs = [e for e in loop if isinstance(e, ir.Arc)]
        if len(arcs) < 2:
            continue
        fit = fit_ellipse(_samples(loop))
        if fit is None:
            continue
        center, a, b, angle, err = fit
        for square in (0.0, 90.0, 180.0):  # axes along the sheet stay exactly so
            if abs(angle - square) <= 1.5:
                angle = square % 180.0
        if err > max(FIT, FIT_REL * b) or a / b < MIN_RATIO:
            continue
        ids = {e.id for e in loop}
        drawing.entities = [e for e in drawing.entities if e.id not in ids]
        drawing.entities.append(ir.Ellipse(
            new_id("E"), min(e.confidence for e in loop),
            [f"Эллипс из {', '.join(sorted(ids))} (отклонение {err:.3f} мм)"],
            center=(round(center[0], 4), round(center[1], 4)), a=round(a, 4), b=round(b, 4),
            angle=round(angle, 3),
            arcs=[["line", list(e.p1), list(e.p2)] if isinstance(e, ir.Line)
                  else ["arc", list(e.center), e.radius, e.start_angle, e.end_angle] for e in loop]))
        made += 1
    return made
