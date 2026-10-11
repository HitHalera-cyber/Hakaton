"""Tables on a drawing: a grid of horizontal and vertical lines with text in
its cells (parameters, a spiral's radii, velocities of a pump stage).

A table is a set of horizontal and vertical lines joined into one grid: the
horizontals at a few heights all running across it, the verticals at a few
places all running down it, the outer ones its frame. Most of its cells hold
a text; a chart's grid (lines of a graph with a curve over them, the numbers
outside) holds next to none, so it is not a table.
"""

from __future__ import annotations

import math

from .. import ir

STRAIGHT = 0.05  # sheet mm off horizontal/vertical
TOUCH = 0.3  # sheet mm: a line ending this near another meets it
LEVEL = 0.3  # sheet mm: lines this close are one row/column border
MIN_CELL = 2.5  # sheet mm: a cell is at least as big as a small text
FILLED = 0.6  # share of the cells that hold text


def find_tables(drawing: ir.Drawing, new_id) -> int:
    """Add a Table entity for every table found; its lines and texts stay
    (named in ``members``). Returns how many were found."""
    hs, vs = [], []
    for e in drawing.of_type(ir.Line):
        if e.style not in (ir.STYLE_MAIN, ir.STYLE_THIN):
            continue
        (x1, y1), (x2, y2) = e.p1, e.p2
        if abs(y1 - y2) <= STRAIGHT and abs(x2 - x1) > MIN_CELL:
            hs.append(e)
        elif abs(x1 - x2) <= STRAIGHT and abs(y2 - y1) > MIN_CELL:
            vs.append(e)
    if len(hs) < 3 or len(vs) < 3:
        return 0
    lines = hs + vs
    parent = list(range(len(lines)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    # horizontals and verticals that cross or touch belong to one grid
    from ..geometry.constraints import Grid

    grid = Grid(10.0)
    for j, v in enumerate(vs):
        grid.add_rect(v.p1[0] - TOUCH, min(v.p1[1], v.p2[1]) - TOUCH,
                      v.p1[0] + TOUCH, max(v.p1[1], v.p2[1]) + TOUCH, len(hs) + j)
    for i, h in enumerate(hs):
        y = h.p1[1]
        lo, hi = sorted((h.p1[0], h.p2[0]))
        cands = set()
        for x in _steps(lo, hi, 10.0):
            cands |= grid.at((x, y))
        for k in cands:
            v = lines[k]
            vlo, vhi = sorted((v.p1[1], v.p2[1]))
            if lo - TOUCH <= v.p1[0] <= hi + TOUCH and vlo - TOUCH <= y <= vhi + TOUCH:
                a, b = find(i), find(k)
                if a != b:
                    parent[a] = b
    groups: dict[int, list] = {}
    for i, l in enumerate(lines):
        groups.setdefault(find(i), []).append(l)

    texts = drawing.of_type(ir.Text)
    taken: set = set()
    made = 0
    for group in groups.values():
        table = _table(group, texts, taken)
        if table is None:
            continue
        top_left, widths, heights, cells, members, height = table
        drawing.entities.append(ir.Table(
            new_id("TB"), 0.9, [f"Таблица {len(heights)}×{len(widths)}"], top_left=top_left,
            widths=widths, heights=heights, cells=cells, text_height=height, members=members))
        made += 1
    return made


def _steps(lo, hi, step):
    x = lo
    while x < hi:
        yield x
        x += step
    yield hi


def _levels(values) -> list[float]:
    out: list[list[float]] = []
    for v in sorted(values):
        if out and v - out[-1][-1] <= LEVEL:
            out[-1].append(v)
        else:
            out.append([v])
    return [sum(c) / len(c) for c in out]


def _table(group, texts, taken):
    hs = [l for l in group if abs(l.p1[1] - l.p2[1]) <= STRAIGHT]
    vs = [l for l in group if abs(l.p1[0] - l.p2[0]) <= STRAIGHT]
    ys = _levels(l.p1[1] for l in hs)
    xs = _levels(l.p1[0] for l in vs)
    if len(ys) < 2 or len(xs) < 2 or len(ys) * len(xs) < 6:
        return None
    x0, x1, y0, y1 = xs[0], xs[-1], ys[0], ys[-1]
    # the frame: outer lines run all round; every line stays inside it
    if not any(min(l.p1[0], l.p2[0]) <= x0 + TOUCH and max(l.p1[0], l.p2[0]) >= x1 - TOUCH
               for l in hs if abs(l.p1[1] - y1) <= LEVEL):
        return None
    if not any(min(l.p1[0], l.p2[0]) <= x0 + TOUCH and max(l.p1[0], l.p2[0]) >= x1 - TOUCH
               for l in hs if abs(l.p1[1] - y0) <= LEVEL):
        return None
    for l in group:
        if min(l.p1[0], l.p2[0]) < x0 - TOUCH or max(l.p1[0], l.p2[0]) > x1 + TOUCH \
                or min(l.p1[1], l.p2[1]) < y0 - TOUCH or max(l.p1[1], l.p2[1]) > y1 + TOUCH:
            return None
    widths = [b - a for a, b in zip(xs, xs[1:])]
    heights = [b - a for a, b in zip(ys, ys[1:])][::-1]  # top row first
    if min(widths) < MIN_CELL or min(heights) < MIN_CELL:
        return None
    rows, cols = len(heights), len(widths)
    cells = [[[] for _ in range(cols)] for _ in range(rows)]  # (y, x, value) each
    members_t = []

    def column(x):
        return next((k for k in range(cols) if x < xs[k + 1]), cols - 1)

    for t in texts:
        if id(t) in taken or abs(t.angle) > 1.0:
            continue
        cx, cy = _centre(t)
        if not (x0 < cx < x1 and y0 < cy < y1):
            continue
        row = rows - 1 - next(k for k in range(rows) if cy < ys[k + 1])
        members_t.append(t)
        words = _words(t.text)
        first, last = column(t.position[0] + 0.3), column(t.position[0] + _width(t) - 0.3)
        if t.parts or len(words) < 2 or last == first:
            value = [[p[0], p[1]] for p in t.parts] if t.parts else t.text
            cells[row][column(cx)].append((t.position[1], t.position[0], value))
            continue
        # one text of the PDF over several cells (a row of values): a word a cell
        for k, word in enumerate(words):
            cells[row][min(first + k, cols - 1)].append((t.position[1], t.position[0] + k, word))
    filled = sum(1 for r in cells for c in r if c)
    if filled < FILLED * rows * cols:
        return None  # a chart's grid, not a table
    for t in members_t:
        taken.add(id(t))
    out = [[_join([v for _, _, v in sorted(c, key=lambda e: (-e[0], e[1]))]) for c in r]
           for r in cells]
    height = sorted(t.height for t in members_t)[len(members_t) // 2]
    members = [l.id for l in group] + [t.id for t in members_t]
    return (x0, y1), widths, heights, out, members, height


def _words(text: str) -> list[str]:
    """The values of a row written as one text: by spaces, and "11,33,81,60"
    (two decimals with a comma between) as two."""
    import re

    out = []
    for w in text.split():
        m = re.fullmatch(r"(\d+,\d+),(\d+,\d+)", w)
        out += list(m.groups()) if m else [w.rstrip(",;")]
    return [w for w in out if w]


def _join(values):
    """A cell's content: plain text, or [text, kind] parts when it has indices."""
    if not values:
        return ""
    if all(isinstance(v, str) for v in values):
        return " ".join(values)
    parts = []
    for v in values:
        if parts:
            parts.append([" ", "normal"])
        parts += v if isinstance(v, list) else [[v, "normal"]]
    return parts


def _width(t: ir.Text) -> float:
    if t.parts:
        return max(p[2] + 0.6 * p[4] * len(p[0]) for p in t.parts) - t.position[0]
    return 0.6 * t.height * len(t.text)


def _centre(t: ir.Text):
    """Middle of a text: halfway along it (by its parts when it has indices),
    half its height up."""
    if t.parts:
        xs = [p[2] for p in t.parts]
        right = max(p[2] + 0.6 * p[4] * len(p[0]) for p in t.parts)
        return ((min(xs) + right) / 2, t.position[1] + t.height / 2)
    width = 0.6 * t.height * len(t.text)
    a = math.radians(t.angle)
    return (t.position[0] + width / 2 * math.cos(a), t.position[1] + t.height / 2)
