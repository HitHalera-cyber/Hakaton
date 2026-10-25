"""Bring lines drawn "not like KOMPAS" back to one stroke of a width.

KOMPAS writes every line as one stroke with its width. Other CAD systems
(AutoCAD and its clones above all) often plot a line some other way:

  * a wide polyline or a plotted lineweight as a filled band (a thin
    polygon around the line);
  * the band's outline stroked with a hairline;
  * several parallel hairlines across the width;
  * every line a hairline of one width (lineweights not plotted).

The first three are turned back into one centre line whose width is the
band's width, so the rest of the recognizer sees what KOMPAS would have
written. The last one is handled in the pipeline (main and thin lines told
apart by their role, see ``pipeline._infer_thin``).
"""

from __future__ import annotations

import math
from collections import defaultdict

from .vector_extractor import PageContent, RawSegment

HAIR = 0.15  # mm: a stroke this thin may be one edge of a band
MAX_W = 1.6  # mm: the widest line a band can stand for (GOST: S ≤ 1.4)
ANGLE = math.radians(3.0)
PAIR_GAP = 0.8  # mm: two lone hairlines further apart are two lines
SAME = 0.02  # mm: two edges this close lie on one line
MIN_SHARE = 0.3  # of the hairline length in bands: the page is drawn that way


def normalise(content: PageContent) -> None:
    """Fill bands → edges, then edge pairs/bundles → centre lines (in place)."""
    fills = len(content.fills)
    _bands_to_edges(content)
    if _merge_edges(content) or len(content.fills) != fills:
        _two_widths(content)


def _two_widths(content: PageContent) -> None:
    """Widths measured off bands scatter; the recognizer wants KOMPAS' two
    (thin and main). Split at the widest ratio between the widths that carry
    a fair share of the drawing, snap each side to its typical width."""
    total: dict[float, float] = defaultdict(float)
    for s in content.segments:
        total[round(s.width, 2)] += s.length
    whole = sum(total.values()) or 1.0
    major = sorted(w for w, L in total.items() if L >= 0.05 * whole and w > 0)
    if len([w for w in major if w > HAIR]) >= 2:
        major = [w for w in major if w > HAIR]  # edges left over (arrowheads) are thin
    if len(major) < 2:
        return
    lo, hi = max(zip(major, major[1:]), key=lambda p: p[1] / p[0])
    split = math.sqrt(lo * hi)

    def typical(side):
        rows = sorted((w, L) for w, L in total.items() if side(w))
        half, acc = sum(L for _, L in rows) / 2, 0.0
        for w, L in rows:
            acc += L
            if acc >= half:
                return w
        return rows[-1][0]

    thin, main = typical(lambda w: w < split), typical(lambda w: w >= split)
    for s in content.segments:
        s.width = thin if s.width < split else main


# --- filled bands ---------------------------------------------------------

def _area(poly) -> float:
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(poly, poly[1:] + poly[:1]))) / 2


def _perimeter(poly) -> float:
    return sum(math.dist(a, b) for a, b in zip(poly, poly[1:] + poly[:1]))


def _is_band(poly) -> bool:
    """A thin polygon whose sides run in pairs: a stroke drawn as an area.
    Arrowheads (no parallel sides) and dots (sides a diameter apart) are not."""
    if len(poly) < 4:
        return False
    per = _perimeter(poly)
    if per <= 0:
        return False
    w = 2 * _area(poly) / per
    if w > MAX_W or per < 8 * max(w, 0.05):
        return False
    edges = [(a, b) for a, b in zip(poly, poly[1:] + poly[:1]) if math.dist(a, b) > 1e-6]
    paired = 0.0
    for a, b in edges:
        u = _unit(a, b)
        for c, d in edges:
            v = _unit(c, d)
            if u[0] * v[0] + u[1] * v[1] > -math.cos(ANGLE):  # sides of a band run back
                continue
            n = (-u[1], u[0])
            gap = abs((c[0] - a[0]) * n[0] + (c[1] - a[1]) * n[1])
            if gap > 1.5 * w + SAME or _overlap(a, b, c, d) < 0.3 * min(math.dist(a, b), math.dist(c, d)):
                continue
            paired += math.dist(a, b)
            break
    return paired >= 0.6 * per


def _bands_to_edges(content: PageContent) -> None:
    kept = []
    for fill in content.fills:
        polys = [_open(r) for r in (fill.rings or [fill.points])]
        bands = [p for p in polys if _is_band(p)]
        if not bands:
            kept.append(fill)
            continue
        for poly in bands:
            content.loops += 1
            for a, b in zip(poly, poly[1:] + poly[:1]):
                if math.dist(a, b) > 1e-6:
                    content.segments.append(RawSegment(a, b, 0.0, content.loops))
        rest = [p for p in polys if not any(p is b for b in bands)]
        if rest:
            kept.append(type(fill)(points=[q for p in rest for q in p], color=fill.color, rings=rest))
    content.fills = kept


def _open(ring):
    """A polygon without its closing point."""
    ring = list(ring)
    return ring[:-1] if len(ring) > 1 and math.dist(ring[0], ring[-1]) < 1e-6 else ring


# --- edge pairs and bundles ---------------------------------------------

def _unit(a, b):
    d = math.dist(a, b) or 1.0
    return ((b[0] - a[0]) / d, (b[1] - a[1]) / d)


def _overlap(a, b, c, d) -> float:
    """Length of [c, d] projected onto [a, b] that falls within [a, b]."""
    u = _unit(a, b)
    L = math.dist(a, b)
    t0 = (c[0] - a[0]) * u[0] + (c[1] - a[1]) * u[1]
    t1 = (d[0] - a[0]) * u[0] + (d[1] - a[1]) * u[1]
    return max(0.0, min(L, max(t0, t1)) - max(0.0, min(t0, t1)))


class _Seg:
    __slots__ = ("s", "u", "n", "rho", "theta", "len")

    def __init__(self, s: RawSegment):
        self.s = s
        a, b = s.a, s.b
        theta = math.atan2(b[1] - a[1], b[0] - a[0]) % math.pi
        self.theta = theta
        self.u = (math.cos(theta), math.sin(theta))
        self.n = (-self.u[1], self.u[0])
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        self.rho = mid[0] * self.n[0] + mid[1] * self.n[1]
        self.len = s.length


def _pairs(segs: list[_Seg]):
    """(gap, i, j) of parallel, overlapping edges at most MAX_W apart."""
    bins: dict[tuple[int, int], list[int]] = defaultdict(list)
    nbins = 180
    for i, g in enumerate(segs):
        bins[(int(math.degrees(g.theta)) % nbins, math.floor(g.rho / MAX_W))].append(i)
    out = []
    for i, g in enumerate(segs):
        ab = int(math.degrees(g.theta)) % nbins
        for da in range(-3, 4):
            b = ab + da
            rho = g.rho
            if b < 0 or b >= nbins:  # across 0°/180° the normal flips
                b %= nbins
                rho = -rho
            rb = math.floor(rho / MAX_W)
            for dr in (-1, 0, 1):
                for j in bins.get((b, rb + dr), ()):
                    if j <= i:
                        continue
                    h = segs[j]
                    if (g.s.loop >= 0 or h.s.loop >= 0) and g.s.loop != h.s.loop:
                        continue  # the sides of a band are of one outline
                    if abs(g.u[0] * h.u[0] + g.u[1] * h.u[1]) < math.cos(ANGLE):
                        continue
                    a, bb = g.s.a, g.s.b
                    c, d = h.s.a, h.s.b
                    mid = ((c[0] + d[0]) / 2, (c[1] + d[1]) / 2)
                    gap = abs((mid[0] - a[0]) * g.n[0] + (mid[1] - a[1]) * g.n[1])
                    if gap > MAX_W:
                        continue
                    if _overlap(a, bb, c, d) < 0.5 * min(g.len, h.len) or min(g.len, h.len) < 0.05:
                        continue
                    if gap >= SAME and min(g.len, h.len) < 0.25 * max(g.len, h.len):
                        continue  # a band's cap is no side of it
                    out.append((gap, i, j))
    out.sort()
    return out


def _merge_edges(content: PageContent) -> bool:
    idx = [k for k, s in enumerate(content.segments) if s.width <= HAIR and s.length > 1e-6]
    if len(idx) < 4:
        return False
    loops: dict[int, list[RawSegment]] = defaultdict(list)
    for k in idx:
        if content.segments[k].loop >= 0:
            loops[content.segments[k].loop].append(content.segments[k])
    for ring in loops.values():
        if not _is_band([s.a for s in ring]):  # an outline of its own, not a band's
            for s in ring:
                s.loop = -1
    segs = [_Seg(content.segments[k]) for k in idx]
    parent = list(range(len(segs)))
    members = {i: [i] for i in range(len(segs))}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def spread(group, ref):
        r = [segs[ref].n[0] * _mid(segs[k])[0] + segs[ref].n[1] * _mid(segs[k])[1] for k in group]
        return max(r) - min(r)

    for gap, i, j in _pairs(segs):
        ri, rj = find(i), find(j)
        if ri == rj:
            continue
        si, sj = spread(members[ri], ri), spread(members[rj], rj)
        new = spread(members[ri] + members[rj], ri)
        if new > MAX_W:
            continue
        band_i, band_j = si >= SAME, sj >= SAME
        if band_i and band_j:
            ok = new <= 1.1 * max(si, sj) + SAME  # two pieces of one band
        elif band_i or band_j:
            s = max(si, sj)
            ok = gap <= 1.1 * s + SAME or new <= 1.1 * s + SAME  # the next line of a bundle
        else:  # two lone lines: only a bundle's, close and alike
            g, h = segs[i], segs[j]
            ok = (gap <= PAIR_GAP or g.s.loop >= 0) and min(g.len, h.len) >= 0.8 * max(g.len, h.len)
        if not ok:
            continue
        parent[rj] = ri
        members[ri] += members.pop(rj)

    groups = [g for r, g in members.items() if spread(g, r) >= SAME]
    in_bands = sum(segs[k].len for g in groups for k in g)
    if in_bands < MIN_SHARE * sum(g.len for g in segs):
        return False  # a few close lines (a thread, a fit) — drawn on purpose

    merged = set()
    out: list[RawSegment] = []
    ends: list[tuple[tuple[float, float], float]] = []
    for g in groups:
        centre = _centre(segs, g)
        if centre is None:
            continue
        out.append(centre)
        merged.update(g)
        w = centre.width
        for k in g:
            ends.append((segs[k].s.a, w))
            ends.append((segs[k].s.b, w))

    # the caps closing a band across its ends go with it
    grid: dict[tuple[int, int], list[tuple[tuple[float, float], float]]] = defaultdict(list)
    for p, w in ends:
        grid[(round(p[0]), round(p[1]))].append((p, w))

    def at_end(p):
        best = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for q, w in grid.get((round(p[0]) + dx, round(p[1]) + dy), ()):
                    if math.dist(p, q) < 0.05:
                        best = max(best or 0.0, w)
        return best

    for i, g in enumerate(segs):
        if i in merged:
            continue
        wa, wb = at_end(g.s.a), at_end(g.s.b)
        if wa and wb and g.len <= 1.3 * max(wa, wb) + SAME:
            merged.add(i)
    _weld(out)
    drop = {id(segs[i].s) for i in merged}
    content.segments = [s for s in content.segments if id(s) not in drop] + out
    return True


WELD = 0.03  # mm: centre-line ends this close are one joint


def _weld(lines: list[RawSegment]) -> None:
    """Centre lines of neighbouring bands meet within a hair; make them meet."""
    grid: dict[tuple[int, int], list[list]] = defaultdict(list)
    joints: list[list] = []  # [x, y, count, ends]
    for s in lines:
        for end in ("a", "b"):
            p = getattr(s, end)
            key = (math.floor(p[0] / WELD), math.floor(p[1] / WELD))
            near = [j for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                    for j in grid.get((key[0] + dx, key[1] + dy), ())
                    if math.dist((j[0] / j[2], j[1] / j[2]), p) < WELD]
            if near:
                j = near[0]
                j[0] += p[0]
                j[1] += p[1]
                j[2] += 1
                j[3].append((s, end))
            else:
                j = [p[0], p[1], 1, [(s, end)]]
                joints.append(j)
                grid[key].append(j)
    for x, y, n, ends in joints:
        if n > 1:
            for s, end in ends:
                setattr(s, end, (x / n, y / n))


def _mid(g: _Seg):
    return ((g.s.a[0] + g.s.b[0]) / 2, (g.s.a[1] + g.s.b[1]) / 2)


def _centre(segs: list[_Seg], group: list[int]) -> RawSegment | None:
    """The line half way between the outermost edges, its ends the mean of
    the ends of each edge line (mitred corners: the outer edge runs past the
    corner as far as the inner one stops short of it)."""
    ref = max(group, key=lambda k: segs[k].len)
    u, n = segs[ref].u, segs[ref].n
    rows = []
    for k in group:
        a, b = segs[k].s.a, segs[k].s.b
        ta, tb = a[0] * u[0] + a[1] * u[1], b[0] * u[0] + b[1] * u[1]
        m = _mid(segs[k])
        rows.append((m[0] * n[0] + m[1] * n[1], min(ta, tb), max(ta, tb), segs[k].s.width))
    rows.sort()
    levels: list[list[tuple]] = []
    for r in rows:
        if levels and r[0] - levels[-1][-1][0] < SAME:
            levels[-1].append(r)
        else:
            levels.append([r])
    if len(levels) < 2:
        return None
    t0 = sum(min(r[1] for r in lv) for lv in levels) / len(levels)
    t1 = sum(max(r[2] for r in lv) for lv in levels) / len(levels)
    if t1 - t0 < 1e-3:
        return None
    rho = (rows[0][0] + rows[-1][0]) / 2
    width = rows[-1][0] - rows[0][0] + max(r[3] for r in rows)
    a = (u[0] * t0 + n[0] * rho, u[1] * t0 + n[1] * rho)
    b = (u[0] * t1 + n[0] * rho, u[1] * t1 + n[1] * rho)
    return RawSegment(a, b, width)
