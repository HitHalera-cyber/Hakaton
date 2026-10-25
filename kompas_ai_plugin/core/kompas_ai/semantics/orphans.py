"""Sizes written on the drawing whose dimension line was not found.

The recogniser keeps such a number (Ø23-0,2 with arrows around it, but no
line it could tie it to) as plain text, so it would silently not hold. Here
each one gets the objects it may measure — circles and arcs of its radius or
diameter, pairs of parallel contour lines and lines as far apart or as long
as the number says — nearest to the number first. The user picks one (or
says it is just text) and the drawing is recognised again with that choice
(``recognize_pdf(..., attach=...)``): a real dimension is made of it before
the outline is fitted to the sizes, so the size holds like any other.
"""

from __future__ import annotations

import math
import re

from .. import ir

NOTE = "Похоже на размер, но собран как текст"
ATTACHED = "привязан вручную"
MATCH = 0.15  # of the value: how far the lines may be off the number written
LIMIT = 4  # candidates offered per number


def orphan_texts(drawing: ir.Drawing) -> list[ir.Text]:
    return [t for t in drawing.of_type(ir.Text) if NOTE in t.notes]


def parse(text: str) -> tuple[str, float | None]:
    """(kind, value) of a size text: «Ø23-0,2» → diameter 23, «R5» → radius 5,
    «M10» → diameter 10, «45» → linear 45, «30°» → angular 30."""
    s = text.strip().replace(" ", "")
    kind = "linear"
    if s[:1] in "Ø⌀∅" or s[:1] in "Mм" and s[1:2].isdigit():
        kind = "diameter"
    elif s[:1] in "RrРр" and s[1:2].isdigit():
        kind = "radius"
    m = re.search(r"\d+(?:[.,]\d+)?", s)
    value = float(m.group(0).replace(",", ".")) if m else None
    if value is not None and "°" in s[m.end():m.end() + 2]:
        kind = "angular"
    return kind, value


def text_center(t: ir.Text) -> tuple[float, float]:
    a = math.radians(t.angle)
    along = 0.3 * t.height * len(t.text)
    return (t.position[0] + along * math.cos(a) - 0.5 * t.height * math.sin(a),
            t.position[1] + along * math.sin(a) + 0.5 * t.height * math.cos(a))


def _dist_to_segment(p, a, b) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.dist(p, (a[0] + dx * t, a[1] + dy * t))


def _num(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def candidates(drawing: ir.Drawing, t: ir.Text, limit: int = LIMIT) -> list[dict]:
    """What the number may measure, best first: right size, then nearest."""
    kind, value = parse(t.text)
    if value is None or value <= 0 or kind == "angular":
        return []
    scale = drawing.scale.value or 1.0
    at = text_center(t)
    out = []

    def offer(c: dict, where_dist: float) -> None:
        off = abs(c["measured"] - value) / value
        if off <= MATCH or abs(c["measured"] - value) <= 0.3:
            c["score"] = (off > 0.02, round(where_dist, 1))
            out.append(c)

    curves = [e for e in drawing.entities if isinstance(e, (ir.Circle, ir.Arc))
              and e.style != ir.STYLE_AXIAL]
    for c in curves:
        name = "окружность" if isinstance(c, ir.Circle) else "дуга"
        d = abs(math.dist(at, c.center) - c.radius)
        if kind in ("diameter", "linear"):
            offer({"kind": "diameter", "refs": [c.id], "measured": 2 * c.radius / scale,
                   "label": f"{name} {c.id}: Ø{_num(2 * c.radius / scale)}",
                   "short": f"{name.capitalize()} Ø{_num(2 * c.radius / scale)}",
                   "where": c.center}, d)
        if kind in ("radius", "linear") or isinstance(c, ir.Arc) and kind == "diameter":
            offer({"kind": "radius", "refs": [c.id], "measured": c.radius / scale,
                   "label": f"{name} {c.id}: R{_num(c.radius / scale)}",
                   "short": f"{name.capitalize()} R{_num(c.radius / scale)}",
                   "where": c.center}, d)

    if kind in ("diameter", "linear"):
        lines = [e for e in drawing.of_type(ir.Line) if e.style == ir.STYLE_MAIN
                 and math.dist(e.p1, e.p2) > 0.5]
        for i, a in enumerate(lines):
            ua = _unit(a)
            for b in lines[i + 1:]:
                ub = _unit(b)
                if abs(ua[0] * ub[1] - ua[1] * ub[0]) > 0.01:
                    continue  # not parallel
                n = (-ua[1], ua[0])
                gap = abs((b.p1[0] - a.p1[0]) * n[0] + (b.p1[1] - a.p1[1]) * n[1])
                if gap < 0.3:
                    continue
                lo, hi = _overlap(a, b, ua)
                if hi - lo < 0.3:
                    continue
                # across both lines at the number's place along them (clamped)
                s = max(lo, min(hi, at[0] * ua[0] + at[1] * ua[1]))
                p1 = _at(a, ua, s)
                p2 = (p1[0] + n[0] * _side(a, b, n) * gap, p1[1] + n[1] * _side(a, b, n) * gap)
                sign = "Ø" if kind == "diameter" else ""
                offer({"kind": "linear", "refs": [a.id, b.id], "measured": gap / scale,
                       "p1": p1, "p2": p2,
                       "label": f"между линиями {a.id} и {b.id}: {sign}{_num(gap / scale)}",
                       "short": f"Между линиями {sign}{_num(gap / scale)}",
                       "where": ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)},
                      _dist_to_segment(at, p1, p2))
        if kind == "linear":
            for a in lines:
                length = math.dist(a.p1, a.p2)
                offer({"kind": "linear", "refs": [a.id], "measured": length / scale,
                       "p1": a.p1, "p2": a.p2,
                       "label": f"длина линии {a.id}: {_num(length / scale)}",
                       "short": f"Длина линии {_num(length / scale)}",
                       "where": ((a.p1[0] + a.p2[0]) / 2, (a.p1[1] + a.p2[1]) / 2)},
                      _dist_to_segment(at, a.p1, a.p2))
    out.sort(key=lambda c: c["score"])
    seen, best = set(), []
    for c in out:
        key = (c["kind"], tuple(sorted(c["refs"])))
        if key not in seen:
            seen.add(key)
            best.append({k: v for k, v in c.items() if k != "score"})
        if len(best) == limit:
            break
    return best


def key_of(c: dict) -> dict:
    """What identifies a choice between two recognitions of one file."""
    return {"kind": c["kind"], "refs": list(c["refs"])}


def _unit(l: ir.Line):
    dx, dy = l.p2[0] - l.p1[0], l.p2[1] - l.p1[1]
    n = math.hypot(dx, dy) or 1.0
    ux, uy = dx / n, dy / n
    if ux < -1e-9 or abs(ux) <= 1e-9 and uy < 0:  # one direction for parallel lines
        ux, uy = -ux, -uy
    return ux, uy


def _overlap(a: ir.Line, b: ir.Line, u):
    def span(l):
        t1, t2 = (l.p1[0] * u[0] + l.p1[1] * u[1], l.p2[0] * u[0] + l.p2[1] * u[1])
        return min(t1, t2), max(t1, t2)

    (a0, a1), (b0, b1) = span(a), span(b)
    return max(a0, b0), min(a1, b1)


def _at(l: ir.Line, u, s):
    t0 = l.p1[0] * u[0] + l.p1[1] * u[1]
    return (l.p1[0] + u[0] * (s - t0), l.p1[1] + u[1] * (s - t0))


def _side(a: ir.Line, b: ir.Line, n) -> float:
    return 1.0 if (b.p1[0] - a.p1[0]) * n[0] + (b.p1[1] - a.p1[1]) * n[1] > 0 else -1.0


def describe(drawing: ir.Drawing) -> list[dict]:
    """The numbers without a dimension line, each with its candidates."""
    out = []
    for t in orphan_texts(drawing):
        kind, value = parse(t.text)
        out.append({"id": t.id, "text": t.text, "kind": kind, "value": value,
                    "candidates": candidates(drawing, t)})
    return out


def apply(drawing: ir.Drawing, attach: dict) -> tuple[int, int]:
    """The user's choices: text id → {"kind", "refs"} (make that dimension) or
    None (it is just text). Returns (dimensions made, texts kept)."""
    made = kept = 0
    taken = {e.id for e in drawing.entities}
    n = 1 + max([int(i[1:]) for i in taken if i[:1] == "D" and i[1:].isdigit()] or [0])
    for text_id in sorted(attach):
        t = drawing.get(text_id)
        if not isinstance(t, ir.Text) or NOTE not in t.notes:
            continue
        choice = attach[text_id]
        if choice is None:
            t.notes = [x for x in t.notes if x != NOTE] + ["оставлен текстом по выбору"]
            t.confidence = 0.9
            kept += 1
            continue
        c = next((c for c in candidates(drawing, t, limit=1000)
                  if key_of(c) == {"kind": choice.get("kind"), "refs": list(choice.get("refs", []))}),
                 None)
        if c is None:
            t.notes = list(t.notes) + ["выбранный объект не найден — оставлен текстом"]
            continue
        dim = make_dimension(drawing, t, c, f"D{n}")
        n += 1
        drawing.entities[drawing.entities.index(t)] = dim
        made += 1
    return made, kept


def make_dimension(drawing: ir.Drawing, t: ir.Text, c: dict, dim_id: str) -> ir.Dimension:
    _, value = parse(t.text)
    at = text_center(t)
    common = dict(text=t.text, nominal=value, text_pos=t.position, text_center=at)
    if c["kind"] in ("diameter", "radius"):
        e = drawing.get(c["refs"][0])
        ang = math.atan2(at[1] - e.center[1], at[0] - e.center[0])
        on = (e.center[0] + e.radius * math.cos(ang), e.center[1] + e.radius * math.sin(ang))
        size = 2 * e.radius if c["kind"] == "diameter" else e.radius
        return ir.Dimension(dim_id, 0.85, [ATTACHED], dim_type=c["kind"], measured=round(size, 4),
                            p1=on, center=e.center, radius=e.radius, ref=e.id,
                            line_point=at, **common)
    p1, p2 = tuple(c["p1"]), tuple(c["p2"])
    dx, dy = abs(p2[0] - p1[0]), abs(p2[1] - p1[1])
    orientation = "horizontal" if dy < 1e-6 else "vertical" if dx < 1e-6 else "aligned"
    if orientation == "horizontal":
        line_point = ((p1[0] + p2[0]) / 2, at[1])
    elif orientation == "vertical":
        line_point = (at[0], (p1[1] + p2[1]) / 2)
    else:
        line_point = at
    return ir.Dimension(dim_id, 0.85, [ATTACHED], dim_type="linear",
                        measured=round(math.dist(p1, p2), 4), p1=p1, p2=p2,
                        line_point=line_point, orientation=orientation, **common)
