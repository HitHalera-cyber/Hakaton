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


SHORT = 2.5  # sheet mm: pieces this short may be a fillet broken into chords


def chords_to_arcs(drawing: ir.Drawing, new_id) -> int:
    """A fillet sometimes comes out as a few short lines. A chain of short
    main lines turning one way whose ends lie on a circle with a radius of
    the drawing (R1, R0,5 — times the scale) becomes that arc."""
    scale = drawing.scale.value or 1.0
    radii = sorted({d.nominal * scale for d in drawing.of_type(ir.Dimension)
                    if d.dim_type == "radius" and d.nominal})
    if not radii:
        return 0
    lines = [e for e in drawing.of_type(ir.Line) if e.style == ir.STYLE_MAIN]
    short = [l for l in lines if math.dist(l.p1, l.p2) <= SHORT]
    used, made = set(), 0

    def neighbours(l, p):
        return [o for o in short if o is not l and o.id not in used
                and min(math.dist(p, o.p1), math.dist(p, o.p2)) <= 0.05]

    for start in short:
        if start.id in used:
            continue
        # grow a chain both ways through ends shared by exactly one short line
        chain = [start]
        for end_pt in (start.p2, start.p1):
            cur, p = start, end_pt
            while True:
                nb = [o for o in neighbours(cur, p) if o not in chain]
                if len(nb) != 1:
                    break
                o = nb[0]
                p = o.p2 if math.dist(p, o.p1) <= 0.05 else o.p1
                chain.append(o) if end_pt is start.p2 else chain.insert(0, o)
                cur = o
        if len(chain) < 2:
            continue
        pts = []
        for l in chain:
            pts += [tuple(l.p1), tuple(l.p2)]
        P = np.array(pts)
        # circle through the points (algebraic least squares)
        A = np.column_stack([2 * P[:, 0], 2 * P[:, 1], np.ones(len(P))])
        b = (P ** 2).sum(axis=1)
        (cx, cy, k), *_ = np.linalg.lstsq(A, b, rcond=None)
        r = math.sqrt(max(k + cx * cx + cy * cy, 0.0))
        err = float(np.abs(np.hypot(P[:, 0] - cx, P[:, 1] - cy) - r).max())
        near = [q for q in radii if abs(q - r) <= 0.25 * q]
        # the solver puts the ends on the circle afterwards: a fillet's first
        # chord often starts a little along the straight line
        if err > 0.3 or not near:
            continue
        # the chain's two free ends, in counter-clockwise order around the centre
        ends = [p for p in pts if sum(math.dist(p, q) <= 0.05 for q in pts) == 1]
        if len(ends) != 2:
            continue
        a1, a2 = (math.degrees(math.atan2(p[1] - cy, p[0] - cx)) % 360.0 for p in ends)
        if (a2 - a1) % 360.0 > 180.0:
            a1, a2 = a2, a1
        used.update(l.id for l in chain)
        drawing.entities = [e for e in drawing.entities if e.id not in {l.id for l in chain}]
        # the fitted circle keeps the ends where they are; the radius of the
        # drawing is set with the other radii and the solver joins the ends
        drawing.entities.append(ir.Arc(new_id("A"), min(l.confidence for l in chain),
                                       [f"Дуга из отрезков {', '.join(l.id for l in chain)}"],
                                       center=(round(cx, 4), round(cy, 4)), radius=round(r, 4),
                                       start_angle=round(a1, 3), end_angle=round(a2, 3)))
        made += 1
    return made



def chord_fillets(drawing: ir.Drawing, new_id, max_chord: float = 1.5) -> int:
    """A tiny fillet drawn as one chord between two lines (a chamfer and a
    face): the chord becomes the arc tangent to both, with the drawing's
    radius nearest to what the chord implies."""
    scale = drawing.scale.value or 1.0
    radii = sorted({d.nominal * scale for d in drawing.of_type(ir.Dimension)
                    if d.dim_type == "radius" and d.nominal})
    lines = [e for e in drawing.of_type(ir.Line) if e.style == ir.STYLE_MAIN]
    made = 0
    for chord in list(lines):
        length = math.dist(chord.p1, chord.p2)
        if length > max_chord or length < 1e-6:
            continue
        nbs, shared = [], []
        cdir = math.atan2(chord.p2[1] - chord.p1[1], chord.p2[0] - chord.p1[0])
        for p in (chord.p1, chord.p2):
            hit = [l for l in lines if l is not chord and l.id != chord.id
                   and min(math.dist(p, l.p1), math.dist(p, l.p2)) <= 0.05]
            if not hit:
                break
            # where several lines meet, the fillet joins the one it turns least from
            def turn(l):
                d = math.atan2(l.p2[1] - l.p1[1], l.p2[0] - l.p1[0])
                return abs((math.degrees(d - cdir) + 90.0) % 180.0 - 90.0)
            nbs.append(min(hit, key=turn))
            shared.append(len(hit) > 1)
        if len(nbs) != 2 or nbs[0] is nbs[1]:
            continue
        a, b = nbs
        (ax1, ay1), (ax2, ay2) = a.p1, a.p2
        (bx1, by1), (bx2, by2) = b.p1, b.p2
        den = (ax1 - ax2) * (by1 - by2) - (ay1 - ay2) * (bx1 - bx2)
        if abs(den) < 1e-9:
            continue
        t1 = ax1 * ay2 - ay1 * ax2
        t2 = bx1 * by2 - by1 * bx2
        X = ((t1 * (bx1 - bx2) - (ax1 - ax2) * t2) / den, (t1 * (by1 - by2) - (ay1 - ay2) * t2) / den)

        def away(line):  # unit direction from the corner along the line
            far = line.p1 if math.dist(line.p1, X) > math.dist(line.p2, X) else line.p2
            d = math.dist(far, X) or 1.0
            return ((far[0] - X[0]) / d, (far[1] - X[1]) / d)

        ua, ub = away(a), away(b)
        if any(shared) and not all(shared):
            # the chord starts where a third line meets (a corner that stays):
            # the arc leaves that point along its line and touches the other
            fixed_a = shared[0]
            line_f, line_t = (a, b) if fixed_a else (b, a)
            P = tuple(chord.p1 if fixed_a else chord.p2)
            uf = away(line_f)
            # normal of the fixed line, towards the chord's other end
            nx, ny = -uf[1], uf[0]
            Q = chord.p2 if fixed_a else chord.p1
            if (Q[0] - P[0]) * nx + (Q[1] - P[1]) * ny < 0:
                nx, ny = -nx, -ny
            # centre P + r n at distance r from the other line
            (tx1, ty1), (tx2, ty2) = line_t.p1, line_t.p2
            L = math.hypot(tx2 - tx1, ty2 - ty1) or 1.0
            sd = lambda x, y: ((tx2 - tx1) * (y - ty1) - (ty2 - ty1) * (x - tx1)) / L
            s0, s1 = sd(*P), sd(P[0] + nx, P[1] + ny) - sd(*P)
            sign = 1.0 if s0 > 0 else -1.0
            # |s0 + r s1| = r with the centre staying on P's side
            denom = sign - s1
            if abs(denom) < 1e-9:
                continue
            r = abs(s0 / denom)
            if r <= 0 or r > 10 * length:
                continue
            c = (P[0] + nx * r, P[1] + ny * r)
            ddx, ddy = (tx2 - tx1) / L, (ty2 - ty1) / L
            k2 = (c[0] - tx1) * ddx + (c[1] - ty1) * ddy
            T = (tx1 + ddx * k2, ty1 + ddy * k2)
            if math.dist(line_t.p1, T) < math.dist(line_t.p2, T) and \
                    math.dist(line_t.p1, Q) < math.dist(line_t.p2, Q):
                line_t.p1 = T
            else:
                line_t.p2 = T
            a1 = math.degrees(math.atan2(P[1] - c[1], P[0] - c[0])) % 360.0
            a2 = math.degrees(math.atan2(T[1] - c[1], T[0] - c[0])) % 360.0
            if (a2 - a1) % 360.0 > 180.0:
                a1, a2 = a2, a1
            drawing.entities = [e for e in drawing.entities if e.id != chord.id]
            lines.remove(chord)
            drawing.entities.append(ir.Arc(new_id("A"), chord.confidence,
                                           [f"Скругление вместо хорды {chord.id}"],
                                           center=(round(c[0], 6), round(c[1], 6)),
                                           radius=round(r, 6), start_angle=round(a1, 4),
                                           end_angle=round(a2, 4)))
            made += 1
            continue
        cos_full = max(-1.0, min(1.0, ua[0] * ub[0] + ua[1] * ub[1]))
        full = math.acos(cos_full)  # angle between the lines at the corner
        if not math.radians(20) < full < math.radians(170):
            continue
        half = full / 2
        # the chord spans 2 r sin((π − full)/2) = 2 r cos(half)
        r_est = length / (2 * math.cos(half))
        r = min(radii, key=lambda q: abs(q - r_est)) if radii else r_est
        if radii and not r_est / 2 <= r <= r_est * 2:
            r = r_est
        k = r / math.tan(half)
        ta = (X[0] + ua[0] * k, X[1] + ua[1] * k)
        tb = (X[0] + ub[0] * k, X[1] + ub[1] * k)
        bis = (ua[0] + ub[0], ua[1] + ub[1])
        n = math.hypot(*bis) or 1.0
        dist = r / math.sin(half)
        c = (X[0] + bis[0] / n * dist, X[1] + bis[1] / n * dist)
        for line, t in ((a, ta), (b, tb)):
            if math.dist(line.p1, X) < math.dist(line.p2, X):
                line.p1 = t
            else:
                line.p2 = t
        a1 = math.degrees(math.atan2(ta[1] - c[1], ta[0] - c[0])) % 360.0
        a2 = math.degrees(math.atan2(tb[1] - c[1], tb[0] - c[0])) % 360.0
        if (a2 - a1) % 360.0 > 180.0:
            a1, a2 = a2, a1
        drawing.entities = [e for e in drawing.entities if e.id != chord.id]
        lines.remove(chord)
        drawing.entities.append(ir.Arc(new_id("A"), chord.confidence,
                                       [f"Скругление вместо хорды {chord.id}"],
                                       center=(round(c[0], 6), round(c[1], 6)), radius=round(r, 6),
                                       start_angle=round(a1, 4), end_angle=round(a2, 4)))
        made += 1
    return made
