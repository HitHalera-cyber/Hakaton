"""A photo (or a scan) of a drawing → a vector PDF the recognition reads.

1. The sheet: the biggest bright quadrilateral of the photo, straightened
   (perspective) to the proportions of an A sheet; without one, the whole
   picture.
2. The ink: an adaptive threshold (uneven light of a photo), specks removed.
3. The lines: the ink thinned to one pixel (Zhang–Suen) and traced into
   polylines between their ends and junctions, each simplified; its width is
   the ink's thickness along it (distance transform) — main or thin.
4. The PDF: every polyline as strokes of its width, in sheet millimetres.
   Arcs and circles come back in the recognition from the polylines, as
   from the chords KOMPAS exports; dashed axes from their dashes.

Texts are not read (no OCR here): the numbers of the sizes are typed in
KOMPAS, or the drawing is built as in the photo.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

A_RATIO = math.sqrt(2.0)
MAX_SIDE = 3000  # px of the long side worked on
MAIN_WIDTH, THIN_WIDTH = 0.5, 0.25  # mm in the PDF


@dataclass
class PhotoResult:
    pdf: Path
    sheet_found: bool
    lines: int
    width_mm: float
    height_mm: float

    def text(self) -> str:
        return (f"Фото переведено в линии: {self.lines} полилиний, лист "
                f"{self.width_mm:.0f}×{self.height_mm:.0f} мм"
                + ("" if self.sheet_found else " (край листа не найден — взят весь снимок)"))


def photo_to_pdf(image: str | Path, out_pdf: str | Path, sheet_mm=None) -> PhotoResult:
    import cv2

    data = np.fromfile(str(image), dtype=np.uint8)  # any path, also non-Latin
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"не удалось прочитать изображение {image}")
    k = MAX_SIDE / max(img.shape[:2])
    if k < 1.0:
        img = cv2.resize(img, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    sheet, found = _sheet(gray)
    h, w = sheet.shape
    if sheet_mm is None:
        landscape = w >= h
        # the A format by the sheet's size in the picture is unknown: A4 for a
        # small part, the scale of the drawing settles the real sizes
        sheet_mm = (297.0, 210.0) if landscape else (210.0, 297.0)
    ink = _ink(sheet)
    # how dark the strokes are against the paper around them: a thin line
    # comes out of a photo as wide as a main one, but paler
    bg = cv2.medianBlur(sheet, 31).astype(np.float32)
    dark = np.clip(bg - sheet.astype(np.float32), 0, None) / np.maximum(bg, 1.0)
    px = sheet_mm[0] / w  # mm per pixel
    # whole circles first (centre lines crossing a hole cut its trace apart);
    # their ink is taken away before the rest is traced
    circles = _circles(sheet, ink, dark, px)
    rest = ink.copy()
    for (cx, cy), r, _ in circles:
        cv2.circle(rest, (int(round(cx)), int(round(cy))), int(round(r)), 0, 7)
    skeleton = _thin(rest)
    polylines = _join_ends(_trace(skeleton), 6.0)
    # the darkness around each point of a line, as width: a path may be a
    # main edge running on as a thin extension line, so it is split where
    # its width changes
    local = cv2.blur(dark, (7, 7)) * 7.0 * px
    samples = []
    paths = []
    for pts in polylines:
        arr = np.array(pts, dtype=np.float64)
        if len(arr) < 2:
            continue
        length_px = float(np.sum(np.hypot(*np.diff(arr, axis=0).T)))
        if length_px * px < 1.0:
            continue
        ij = np.round(arr).astype(int)
        vals = local[np.clip(ij[:, 1], 0, h - 1), np.clip(ij[:, 0], 0, w - 1)]
        paths.append((arr, vals))
        samples += list(vals[::3])
    split = _split_widths(samples + [wd for _, _, wd in circles])
    simple = []
    for arr, vals in paths:
        main = _runs(vals >= split, 8)
        start = 0
        for k in range(1, len(arr) + 1):
            if k == len(arr) or main[k] != main[start]:
                piece = arr[max(0, start - 1):k] if start else arr[start:k]
                if len(piece) >= 2:
                    approx = cv2.approxPolyDP(piece.astype(np.float32).reshape(-1, 1, 2), 1.0,
                                              False).reshape(-1, 2)
                    simple.append((approx, MAIN_WIDTH if main[start] else THIN_WIDTH))
                start = k
    simple = _bridges(simple, 2.5 / px)
    import pymupdf

    doc = pymupdf.open()
    pt = 72.0 / 25.4
    page = doc.new_page(width=sheet_mm[0] * pt, height=sheet_mm[1] * pt)
    shape = page.new_shape()
    for kind in ("thin", "main"):
        any_drawn = False
        for approx, width in simple:
            if ("main" if width >= MAIN_WIDTH else "thin") != kind:
                continue
            pts = [pymupdf.Point(x * px * pt, y * px * pt) for x, y in approx]
            shape.draw_polyline(pts)
            any_drawn = True
        if any_drawn:
            shape.finish(color=(0, 0, 0), width=(MAIN_WIDTH if kind == "main" else THIN_WIDTH) * pt,
                         closePath=False)
    for (cx, cy), r, width in circles:
        kind_w = MAIN_WIDTH if width >= split else THIN_WIDTH
        shape.draw_circle(pymupdf.Point(cx * px * pt, cy * px * pt), r * px * pt)
        shape.finish(color=(0, 0, 0), width=kind_w * pt)
    shape.commit()
    doc.save(str(out_pdf))
    doc.close()
    return PhotoResult(Path(out_pdf), found, len(simple) + len(circles), sheet_mm[0],
                       sheet_mm[1])


def _circles(gray, ink, dark, px):
    """Circles of the drawing: Hough candidates kept when ink runs round
    most of them. ((x, y), r, width mm) in pixels of the sheet."""
    import cv2

    blur = cv2.GaussianBlur(gray, (5, 5), 1.5)
    rmin, rmax = max(4, int(2.5 / px)), int(80.0 / px)  # smaller: the letters of a text
    found = cv2.HoughCircles(blur, cv2.HOUGH_GRADIENT, dp=1.2, minDist=max(6, int(1.5 / px)),
                             param1=120, param2=28, minRadius=rmin, maxRadius=rmax)
    out = []
    if found is None:
        return out
    h, w = ink.shape
    for cx, cy, r in found[0]:
        n = max(36, int(2 * math.pi * r / 2))
        t = np.linspace(0, 2 * math.pi, n, endpoint=False)
        hit = 0
        for dr in (0.0,):
            xs = np.clip(np.round(cx + (r + dr) * np.cos(t)).astype(int), 0, w - 1)
            ys = np.clip(np.round(cy + (r + dr) * np.sin(t)).astype(int), 0, h - 1)
            near = np.zeros(n, bool)
            for ox in (-1, 0, 1):
                for oy in (-1, 0, 1):
                    near |= ink[np.clip(ys + oy, 0, h - 1), np.clip(xs + ox, 0, w - 1)] > 0
            hit = near.mean()
        if hit < 0.85:
            continue
        cx, cy, r = _refine(dark, cx, cy, r)
        if any(math.dist((cx, cy), c) < 2 and abs(r - rr) < 2 for c, rr, _ in out):
            continue
        ring = np.zeros(ink.shape, np.uint8)
        cv2.circle(ring, (int(round(cx)), int(round(cy))), int(round(r)), 255, 9)
        width = float(dark[ring > 0].sum()) / (2 * math.pi * r + 9.0) * px
        out.append(((float(cx), float(cy)), float(r), width))
    return out


def _refine(dark, cx, cy, r):
    """Centre and radius moved (to a quarter pixel) to where the ring is
    darkest: Hough's are a pixel or two off."""
    h, w = dark.shape
    t = np.linspace(0, 2 * math.pi, max(48, int(2 * math.pi * r)), endpoint=False)
    cos, sin = np.cos(t), np.sin(t)

    def score(x, y, rr):
        xs = np.clip(x + rr * cos, 0, w - 1.001)
        ys = np.clip(y + rr * sin, 0, h - 1.001)
        x0, y0 = xs.astype(int), ys.astype(int)
        fx, fy = xs - x0, ys - y0
        v = (dark[y0, x0] * (1 - fx) * (1 - fy) + dark[y0, x0 + 1] * fx * (1 - fy)
             + dark[y0 + 1, x0] * (1 - fx) * fy + dark[y0 + 1, x0 + 1] * fx * fy)
        return float(v.mean())

    best = (score(cx, cy, r), cx, cy, r)
    for step in (1.0, 0.5, 0.25):
        improved = True
        while improved:
            improved = False
            _, x, y, rr = best
            for dx, dy, dr in ((step, 0, 0), (-step, 0, 0), (0, step, 0), (0, -step, 0),
                               (0, 0, step), (0, 0, -step)):
                s = score(x + dx, y + dy, rr + dr)
                if s > best[0] + 1e-6:
                    best = (s, x + dx, y + dy, rr + dr)
                    improved = True
    return best[1], best[2], best[3]


def _sheet(gray):
    """The sheet straightened, and whether its edge was found."""
    import cv2

    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, bright = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    area = gray.shape[0] * gray.shape[1]
    best = None
    for cnt in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
        if cv2.contourArea(cnt) < 0.25 * area:
            break
        quad = cv2.approxPolyDP(cnt, 0.02 * cv2.arcLength(cnt, True), True)
        if len(quad) == 4 and cv2.isContourConvex(quad):
            best = quad.reshape(4, 2).astype(np.float32)
            break
    if best is None or cv2.contourArea(best) > 0.98 * area:
        return gray, False
    # corners in order: top-left, top-right, bottom-right, bottom-left
    s, d = best.sum(axis=1), np.diff(best, axis=1).ravel()
    tl, br = best[np.argmin(s)], best[np.argmax(s)]
    tr, bl = best[np.argmin(d)], best[np.argmax(d)]
    width = max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl))
    height = max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr))
    if width >= height:
        W, H = int(width), int(width / A_RATIO)
    else:
        W, H = int(height / A_RATIO), int(height)
    m = cv2.getPerspectiveTransform(np.array([tl, tr, br, bl]),
                                    np.array([[0, 0], [W, 0], [W, H], [0, H]], np.float32))
    return cv2.warpPerspective(gray, m, (W, H)), True


def _ink(gray):
    """Dark strokes as 255 on 0: an adaptive threshold (uneven light), specks
    smaller than a dot removed."""
    import cv2

    block = max(15, (min(gray.shape) // 40) | 1)
    ink = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV,
                                block, 12)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(ink, 8)
    small = stats[:, cv2.CC_STAT_AREA] < 12
    small[0] = False
    ink[small[labels]] = 0
    return ink


def _thin(ink):
    """Zhang–Suen thinning of a 0/255 image to one-pixel lines (0/1)."""
    img = (ink > 0).astype(np.uint8)
    img = np.pad(img, 1)
    while True:
        changed = False
        for step in (0, 1):
            p = img
            p2, p3, p4 = p[:-2, 1:-1], p[:-2, 2:], p[1:-1, 2:]
            p5, p6, p7 = p[2:, 2:], p[2:, 1:-1], p[2:, :-2]
            p8, p9 = p[1:-1, :-2], p[:-2, :-2]
            c = p[1:-1, 1:-1]
            nb = [p2, p3, p4, p5, p6, p7, p8, p9]
            b = sum(x.astype(np.int32) for x in nb)
            seq = nb + [p2]
            a = sum(((seq[i] == 0) & (seq[i + 1] == 1)).astype(np.int32) for i in range(8))
            if step == 0:
                cond = (p2 * p4 * p6 == 0) & (p4 * p6 * p8 == 0)
            else:
                cond = (p2 * p4 * p8 == 0) & (p2 * p6 * p8 == 0)
            drop = (c == 1) & (b >= 2) & (b <= 6) & (a == 1) & cond
            if drop.any():
                img[1:-1, 1:-1][drop] = 0
                changed = True
        if not changed:
            break
    return img[1:-1, 1:-1]


NEIGHBOURS = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]


def _trace(skel) -> list[list[tuple[int, int]]]:
    """Polylines of a one-pixel skeleton, from end/junction to end/junction
    (closed loops from any of their pixels)."""
    h, w = skel.shape
    on = set(zip(*np.nonzero(skel.T)))  # (x, y)

    def nbrs(p):
        x, y = p
        return [(x + dx, y + dy) for dx, dy in NEIGHBOURS if (x + dx, y + dy) in on]

    degree = {p: len(nbrs(p)) for p in on}
    nodes = {p for p, d in degree.items() if d != 2}
    used_edges = set()
    out = []

    def walk(start, nxt):
        path = [start, nxt]
        used_edges.add((start, nxt))
        used_edges.add((nxt, start))
        prev, cur = start, nxt
        while cur not in nodes:
            step = [q for q in nbrs(cur) if q != prev and (cur, q) not in used_edges]
            if not step:
                break
            prev, cur = cur, step[0]
            used_edges.add((prev, cur))
            used_edges.add((cur, prev))
            path.append(cur)
            if cur == start:
                break
        return path

    for n in nodes:
        for q in nbrs(n):
            if (n, q) not in used_edges:
                out.append(walk(n, q))
    seen = {p for path in out for p in path}
    for p in on:  # loops with no junction (a circle)
        if p in seen or degree[p] != 2:
            continue
        q = nbrs(p)[0]
        path = walk(p, q)
        seen.update(path)
        out.append(path)
    return out


def _join_ends(paths, reach: float):
    """Ends of polylines a few pixels apart are one point (thinning pulls a
    corner or a junction apart): each cluster of ends moves to its middle."""
    ends = [(i, k) for i, p in enumerate(paths) for k in (0, -1) if len(p) >= 2]
    pts = [np.array(paths[i][k], dtype=np.float64) for i, k in ends]
    paths = [[tuple(map(float, q)) for q in p] for p in paths]
    done = set()
    for a in range(len(ends)):
        if a in done:
            continue
        group = [b for b in range(len(ends)) if b not in done
                 and np.linalg.norm(pts[a] - pts[b]) <= reach]
        if len(group) < 2:
            continue
        mid = tuple(map(float, np.mean([pts[b] for b in group], axis=0)))
        for b in group:
            i, k = ends[b]
            paths[i][k] = mid
            done.add(b)
    return paths


def _bridges(pieces, longest: float):
    """A short thin piece between two main ones (a corner, a junction) is
    main: the contour would stay open there."""
    mains = [p for p, w in pieces if w >= MAIN_WIDTH]
    ends = [tuple(np.round(q).astype(int)) for p in mains for q in (p[0], p[-1])]
    near = {}
    for x, y in ends:
        near.setdefault((x // 4, y // 4), []).append((x, y))

    def touches(q):
        x, y = int(round(q[0])), int(round(q[1]))
        for gx in (x // 4 - 1, x // 4, x // 4 + 1):
            for gy in (y // 4 - 1, y // 4, y // 4 + 1):
                if any(abs(a - x) <= 2 and abs(b - y) <= 2 for a, b in near.get((gx, gy), ())):
                    return True
        return False

    out = []
    for p, w in pieces:
        if w < MAIN_WIDTH and len(p) >= 2:
            length = float(np.sum(np.hypot(*np.diff(p.astype(np.float64), axis=0).T)))
            if length <= longest and touches(p[0]) and touches(p[-1]):
                w = MAIN_WIDTH
        out.append((p, w))
    return out


def _runs(flags, shortest: int):
    """A per-point main/thin choice with runs shorter than ``shortest`` points
    given to their neighbours (a junction's or a letter's blot)."""
    flags = list(bool(f) for f in flags)
    changed = True
    while changed:
        changed = False
        k = 0
        while k < len(flags):
            j = k
            while j < len(flags) and flags[j] == flags[k]:
                j += 1
            if j - k < shortest and (k > 0 or j < len(flags)) and j - k < len(flags):
                for m in range(k, j):
                    flags[m] = not flags[m]
                changed = True
                break
            k = j
    return flags


def _split_widths(widths) -> float:
    """The width between thin and main lines (Otsu on the widths), or above
    all of them when they are one kind."""
    if not widths:
        return 1.0
    ws = np.sort(np.asarray(widths, dtype=np.float64))
    n = len(ws)
    if n < 2 or ws[-1] <= 1.6 * max(ws[0], 1e-9) and ws[int(0.95 * (n - 1))] <= 1.6 * ws[int(0.05 * (n - 1))]:
        return ws[-1] + 1.0  # one kind of line
    csum = np.cumsum(ws)
    k = np.arange(1, n)
    mean_a = csum[:-1] / k
    mean_b = (csum[-1] - csum[:-1]) / (n - k)
    between = k * (n - k) * (mean_a - mean_b) ** 2
    i = int(np.argmax(between))
    return float((ws[i] + ws[i + 1]) / 2)
