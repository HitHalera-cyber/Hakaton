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
WORK_PX_MM = 8.0  # a small picture (a screenshot) is enlarged to this
FRAME_LEFT, FRAME_OTHER = 20.0, 5.0  # ГОСТ 2.104 frame margins, mm
TEXT_SIZE = 7.0  # mm: a blot of ink no bigger, not a stroke, is a letter


@dataclass
class PhotoResult:
    pdf: Path
    sheet_found: bool
    lines: int
    width_mm: float
    height_mm: float
    frame_found: bool = False
    detected: str | None = None  # the format told by the title block («A3»)

    def text(self) -> str:
        return (f"Фото переведено в линии: {self.lines} полилиний, лист "
                f"{self.width_mm:.0f}×{self.height_mm:.0f} мм"
                + ("" if self.sheet_found else " (край листа не найден — взят весь снимок)")
                + (f" (формат {self.detected} — по основной надписи)" if self.detected else "")
                + (", рамка и основная надпись с фото заменены листом КОМПАС"
                   if self.frame_found else ""))


def photo_to_pdf(image: str | Path, out_pdf: str | Path, sheet_mm=None) -> PhotoResult:
    """``sheet_mm``: the sheet's two sides in mm (A4 when not given), either order."""
    import cv2

    data = np.fromfile(str(image), dtype=np.uint8)  # any path, also non-Latin
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"не удалось прочитать изображение {image}")
    k = MAX_SIDE / max(img.shape[:2])
    if k < 1.0:
        img = cv2.resize(img, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    sheet, found = _sheet(gray, WORK_PX_MM)
    if not found and max(sheet.shape) < WORK_PX_MM * 297.0:
        k = WORK_PX_MM * 297.0 / max(sheet.shape)
        sheet = cv2.resize(sheet, None, fx=k, fy=k, interpolation=cv2.INTER_CUBIC)
    h, w = sheet.shape
    # the A format by the sheet's size in the picture is unknown: A4 unless
    # told (the window asks), turned as the sheet lies in the photo
    auto = sheet_mm is None  # the format from the title block, when the photo has one
    short, long_ = sorted(sheet_mm or (210.0, 297.0))
    sheet_mm = (long_, short) if w >= h else (short, long_)
    ink = _ink(sheet)
    enlarged = WORK_PX_MM * 297.0 / max(gray.shape) >= 1.5
    # how dark the strokes are against the paper around them: a thin line
    # comes out of a photo as wide as a main one, but paler
    bg = cv2.medianBlur(sheet, 31).astype(np.float32)
    dark = np.clip(bg - sheet.astype(np.float32), 0, None) / np.maximum(bg, 1.0)
    px = sheet_mm[0] / w  # mm per pixel
    # the drawing's own frame with its title block: KOMPAS puts its own on
    # the sheet, so it is taken away; its corners are the frame of ГОСТ
    # 2.104 (20 mm on the left, 5 elsewhere) — a truer scale than the
    # paper's edge in the photo
    to_mm = lambda x, y: (x * px, y * px)  # noqa: E731
    frame = _frame(ink)
    if frame is not None:
        (fx0, fy0, fx1, fy1), pixels = frame
        if auto:
            fmt = _format_by_title_block(pixels, (fx0, fy0, fx1, fy1))
            if fmt is not None:
                sheet_mm, detected = fmt[1], fmt[0]
        ink[pixels] = 0
        kx = (sheet_mm[0] - FRAME_LEFT - FRAME_OTHER) / (fx1 - fx0)
        ky = (sheet_mm[1] - 2 * FRAME_OTHER) / (fy1 - fy0)
        to_mm = lambda x, y: (FRAME_LEFT + (x - fx0) * kx, FRAME_OTHER + (y - fy0) * ky)  # noqa: E731
        px = (kx + ky) / 2
    # whole circles first (centre lines crossing a hole cut its trace apart);
    # their ink is taken away before the rest is traced
    circles = _circles(sheet, ink, dark, px)
    rest = _drop_letters(ink, px)
    if enlarged:
        # a small picture enlarged (a screenshot): a thin slanted line of it
        # breaks up into specks of its pixel steps — closed into a stroke
        # (after the letters are gone: closed, a word is one big blot)
        rest = cv2.morphologyEx(rest, cv2.MORPH_CLOSE,
                                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    for (cx, cy), r, _ in circles:
        cv2.circle(rest, (int(round(cx)), int(round(cy))), int(round(r)), 0,
                   max(7, int(round(1.2 / px))))
    skeleton = _thin(rest)
    polylines = _join_ends(_trace(skeleton), 6.0)
    # the darkness around each point of a line, as width: a path may be a
    # main edge running on as a thin extension line, so it is split where
    # its width changes
    samples = []
    paths = []
    local = cv2.blur(dark, (7, 7)) * 7.0 * px
    from collections import Counter

    shared = Counter(tuple(np.round(p[k], 1)) for p in polylines if len(p) >= 2 for k in (0, -1))
    for pts in polylines:
        arr = np.array(pts, dtype=np.float64)
        if len(arr) < 2:
            continue
        length_px = float(np.sum(np.hypot(*np.diff(arr, axis=0).T)))
        # a short piece with a free end is a spur of the thinning (or a speck);
        # between two junctions it is a bit of a line, cut by a spur
        free = any(shared[tuple(np.round(pts[k], 1))] < 2 for k in (0, -1))
        if length_px * px < 1.0 and free:
            continue
        ij = np.round(arr).astype(int)
        vals = local[np.clip(ij[:, 1], 0, h - 1), np.clip(ij[:, 0], 0, w - 1)]
        paths.append((arr, vals))
        samples += list(vals[::3])
    split = _split_widths(samples + [wd for _, _, wd in circles])
    simple = []
    for arr, vals in paths:
        # a change of width shorter than a few millimetres is a blot (a
        # junction, a crossing hatch stroke), not an edge running on as a thin line
        main = _runs(vals >= split, max(8, int(3.0 / px)))
        start = 0
        for k in range(1, len(arr) + 1):
            if k == len(arr) or main[k] != main[start]:
                piece = arr[max(0, start - 1):k] if start else arr[start:k]
                if len(piece) >= 2:
                    approx = _simplify(piece)
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
            pts = [pymupdf.Point(*(v * pt for v in to_mm(x, y))) for x, y in approx]
            shape.draw_polyline(pts)
            any_drawn = True
        if any_drawn:
            shape.finish(color=(0, 0, 0), width=(MAIN_WIDTH if kind == "main" else THIN_WIDTH) * pt,
                         closePath=False)
    for (cx, cy), r, width in circles:
        kind_w = MAIN_WIDTH if width >= split else THIN_WIDTH
        shape.draw_circle(pymupdf.Point(*(v * pt for v in to_mm(cx, cy))), r * px * pt)
        shape.finish(color=(0, 0, 0), width=kind_w * pt)
    shape.commit()
    doc.save(str(out_pdf))
    doc.close()
    return PhotoResult(Path(out_pdf), found, len(simple) + len(circles), sheet_mm[0],
                       sheet_mm[1], frame is not None, locals().get("detected"))


def _simplify(piece):
    """The points of a traced path down to its corners (Douglas–Peucker, a
    pixel). A closed path is halved first: with its ends on one point, the
    open simplification loses a whole side."""
    import cv2

    if len(piece) > 4 and np.hypot(*(piece[0] - piece[-1])) < 2.0:
        mid = len(piece) // 2
        a, b = _simplify(piece[:mid + 1]), _simplify(piece[mid:])
        return np.vstack([a, b[1:]])
    return cv2.approxPolyDP(piece.astype(np.float32).reshape(-1, 1, 2), 1.0, False).reshape(-1, 2)


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
    def ring(cx, cy, r):
        t = np.linspace(0, 2 * math.pi, max(48, int(2 * math.pi * r)), endpoint=False)
        xs = np.clip(np.round(cx + r * np.cos(t)).astype(int), 0, w - 1)
        ys = np.clip(np.round(cy + r * np.sin(t)).astype(int), 0, h - 1)
        return dark[ys, xs]

    def add(cx, cy, r):
        if any(math.dist((cx, cy), c) < 2 and abs(r - rr) < 2 for c, rr, _ in out):
            return
        # the refined ring is dark all round and much darker than a little
        # inside and outside it; a hatched square or a letter Hough took for
        # a circle is dark in patches only
        on = ring(cx, cy, r)
        off = max(4.0, 0.9 / px)  # beyond a main line's half width
        near = max(ring(cx, cy, r - off).mean(), ring(cx, cy, r + off).mean())
        if (on > 0.5 * np.median(on)).mean() < 0.9 or on.mean() < 2.5 * near:
            return
        band = np.zeros(ink.shape, np.uint8)
        cv2.circle(band, (int(round(cx)), int(round(cy))), int(round(r)), 255, 9)
        width = float(dark[band > 0].sum()) / (2 * math.pi * r + 9.0) * px
        out.append(((float(cx), float(cy)), float(r), width))

    def coverage(cx, cy, r):
        n = max(36, int(2 * math.pi * r / 2))
        t = np.linspace(0, 2 * math.pi, n, endpoint=False)
        xs = np.clip(np.round(cx + r * np.cos(t)).astype(int), 0, w - 1)
        ys = np.clip(np.round(cy + r * np.sin(t)).astype(int), 0, h - 1)
        near = np.zeros(n, bool)
        for ox in (-1, 0, 1):
            for oy in (-1, 0, 1):
                near |= ink[np.clip(ys + oy, 0, h - 1), np.clip(xs + ox, 0, w - 1)] > 0
        return near.mean()

    for cx, cy, r in found[0]:
        if coverage(cx, cy, r) < 0.85:
            continue
        # a circle is a thin ring: a little inside and outside it there is
        # paper; the 0 or the Ø of a size's number is an oval of thick ink
        # and Hough's circle runs inside and outside it
        if max(coverage(cx, cy, 0.7 * r), coverage(cx, cy, 1.3 * r)) > 0.6:
            continue
        cx, cy, r = _refine(dark, cx, cy, r)
        add(cx, cy, r)
    # Hough keeps one radius at a centre: the rings around a found circle's
    # centre (a bore inside a flange) are looked for along the radius
    for (cx, cy), r0, _ in list(out):
        rs = np.arange(rmin, rmax, 1.0)
        cov = np.array([coverage(cx, cy, r) for r in rs])
        for k in range(1, len(rs) - 1):
            r = rs[k]
            if cov[k] < 0.85 or cov[k] < cov[k - 1] or cov[k] < cov[k + 1] or abs(r - r0) < 3:
                continue
            if max(coverage(cx, cy, 0.7 * r), coverage(cx, cy, 1.3 * r)) > 0.6:
                continue
            x, y, rr = _refine(dark, cx, cy, r)
            if math.dist((x, y), (cx, cy)) < 2:
                add(cx, cy, rr)  # one centre for the rings of one part
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


def _sheet(gray, px_mm: float = 0.0):
    """The sheet straightened, and whether its edge was found.

    The sheet is the biggest bright convex quadrilateral with the
    proportions of an A format, tried at several brightness levels: the
    paper of a photo is lighter than the table, the page of a screenshot
    lighter than the grey of the viewer around it (and a toolbar as white as
    the page is not of A proportions). The paper is lighter than what lies
    just outside its edge — the inside of the drawing's frame is not. With ``px_mm`` the straightened
    sheet has at least that many pixels per millimetre of an A4 — thin lines
    of a small picture get room to be traced."""
    import cv2

    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    otsu, _ = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    area = gray.shape[0] * gray.shape[1]
    best = None
    levels = sorted({int(otsu), *range(int(otsu) + 8, 251, 8)})
    for level in levels:
        bright = (blur > level).astype(np.uint8) * 255
        contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
            a = cv2.contourArea(cnt)
            if a < 0.12 * area:
                break
            quad = cv2.approxPolyDP(cnt, 0.02 * cv2.arcLength(cnt, True), True)
            if len(quad) != 4 or not cv2.isContourConvex(quad):
                continue
            q = quad.reshape(4, 2).astype(np.float32)
            qa = cv2.contourArea(q)
            if qa > 0.98 * area or qa < 0.85 * a:  # the whole picture / not a quad
                continue
            sides = [float(np.linalg.norm(q[i] - q[(i + 1) % 4])) for i in range(4)]
            long_ = max(sides[0] + sides[2], sides[1] + sides[3])
            short = min(sides[0] + sides[2], sides[1] + sides[3])
            if abs(math.log(long_ / max(short, 1.0) / A_RATIO)) > 0.2:  # not an A sheet
                continue
            if _edge_contrast(blur, q) < 8.0:  # the inside of a frame line
                continue
            if best is None or qa > best[0]:
                best = (qa, q)
    if best is None:
        return gray, False
    best = best[1]
    # corners in order: top-left, top-right, bottom-right, bottom-left
    s, d = best.sum(axis=1), np.diff(best, axis=1).ravel()
    tl, br = best[np.argmin(s)], best[np.argmax(s)]
    tr, bl = best[np.argmin(d)], best[np.argmax(d)]
    # the paper's own edge (a shadow, the viewer's border) is cut off
    centre = (tl + tr + br + bl) / 4
    tl, tr, br, bl = (c + (centre - c) * 0.004 for c in (tl, tr, br, bl))
    width = max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl))
    height = max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr))
    long_side = max(width, height, px_mm * 297.0)
    if width >= height:
        W, H = int(long_side), int(long_side / A_RATIO)
    else:
        W, H = int(long_side / A_RATIO), int(long_side)
    m = cv2.getPerspectiveTransform(np.array([tl, tr, br, bl]),
                                    np.array([[0, 0], [W, 0], [W, H], [0, H]], np.float32))
    return cv2.warpPerspective(gray, m, (W, H), flags=cv2.INTER_CUBIC,
                               borderMode=cv2.BORDER_REPLICATE), True


def _edge_contrast(gray, quad) -> float:
    """How much lighter the band just inside a quadrilateral is than the band
    just outside it; a quadrilateral cut by the picture's edge has none."""
    import cv2

    h, w = gray.shape
    d = max(3, int(0.012 * math.sqrt(cv2.contourArea(quad))))
    mask = np.zeros((h, w), np.uint8)
    cv2.fillConvexPoly(mask, quad.astype(np.int32), 255)
    kernel = np.ones((2 * d + 1, 2 * d + 1), np.uint8)
    outer = (cv2.dilate(mask, kernel) > 0) & (mask == 0)
    inner = (mask > 0) & (cv2.erode(mask, kernel) == 0)
    perimeter = cv2.arcLength(quad, True)
    if outer.sum() < 0.6 * perimeter * d or not inner.any():
        return 0.0
    return float(np.median(gray[inner])) - float(np.median(gray[outer]))


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


def _frame(ink):
    """The frame of the drawing: the ink in one piece with a rectangle round
    most of the sheet (its title block hangs on it). Its box in pixels and
    its pixels, or None."""
    import cv2

    h, w = ink.shape
    n, labels, stats, _ = cv2.connectedComponentsWithStats(ink, 8)
    best = None
    for i in range(1, n):
        x, y, bw, bh = (stats[i, k] for k in (cv2.CC_STAT_LEFT, cv2.CC_STAT_TOP,
                                              cv2.CC_STAT_WIDTH, cv2.CC_STAT_HEIGHT))
        if bw < 0.6 * w or bh < 0.6 * h:
            continue
        if sum((x < 0.005 * w, y < 0.005 * h, x + bw > 0.995 * w, y + bh > 0.995 * h)) >= 3:
            continue  # the paper's edge or a shadow all round, not a frame
        mask = labels == i
        # a frame: long lines of ink along all four sides (the box of the
        # piece may stick out with a blot hanging on it)
        cols = np.nonzero(mask.sum(axis=0) >= 0.6 * bh)[0]
        rows = np.nonzero(mask.sum(axis=1) >= 0.6 * bw)[0]
        if len(cols) < 2 or len(rows) < 2:
            continue
        x0, x1, y0, y1 = cols[0], cols[-1], rows[0], rows[-1]
        if x1 - x0 < 0.6 * w or y1 - y0 < 0.6 * h:
            continue
        x, y, bw, bh = x0, y0, x1 - x0 + 1, y1 - y0 + 1
        if best is None or bw * bh > best[0]:
            best = (bw * bh, (float(x), float(y), float(x + bw - 1), float(y + bh - 1)), mask)
    if best is None:
        return None
    return best[1], best[2]


TITLE_BLOCK_W = 185.0  # mm: the main title block of ГОСТ 2.104, on every format
FORMATS = [("A4", (210.0, 297.0)), ("A3", (297.0, 420.0)), ("A2", (420.0, 594.0)),
           ("A1", (594.0, 841.0)), ("A0", (841.0, 1189.0))]


def _format_by_title_block(pixels, box):
    """The sheet's format from its frame: the title block is 185 mm wide on
    every format, so the frame is as many title blocks wide as it shows —
    (name, (width, height) in mm) or None without a title block."""
    fx0, fy0, fx1, fy1 = (int(v) for v in box)
    fw, fh = fx1 - fx0, fy1 - fy0
    if fw <= 0 or fh <= 0:
        return None
    top = None
    # rows of the lower part, from the top down: the first run of ink that
    # leaves the frame's right side is the title block's upper edge
    for y in range(fy0 + int(0.5 * fh), fy1 - 4):
        # a band of rows: a photo's lines lean a little after straightening
        row = pixels[max(0, y - 6):y + 7, fx0:fx1 + 1].any(axis=0)
        if row[-4:].any() and row[-int(0.1 * fw):].mean() > 0.8:
            top = y
            break
    if top is None or fy1 - top < 0.08 * fh:
        return None
    # its left side: the leftmost upright line from that edge down to the
    # frame (the upper edge itself may be broken in a photo)
    width = None
    lower = pixels[top + 8:fy1 - 8]
    if lower.shape[0] < 10:
        return None
    for x in range(fx0 + int(0.25 * fw), fx1 - int(0.05 * fw)):
        column = lower[:, max(0, x - 3):x + 4].any(axis=1)
        if column.mean() > 0.85:
            width = fx1 - x
            break
    if width is None:
        return None
    frame_mm = TITLE_BLOCK_W * fw / width
    landscape = fw >= fh
    best = None
    for name, (short, long_) in FORMATS:
        inner = (long_ if landscape else short) - FRAME_LEFT - FRAME_OTHER
        miss = abs(inner - frame_mm) / inner
        if miss <= 0.12 and (best is None or miss < best[0]):
            best = (miss, name, (long_, short) if landscape else (short, long_))
    return None if best is None else (best[1], best[2])


def _drop_letters(ink, px):
    """The ink without the letters and numbers standing apart from the lines:
    small blots that are no straight stroke (a dash of an axis is kept).
    Texts are not read; traced, they would come back as a mess of short
    lines and arcs."""
    import cv2

    out = ink.copy()
    n, labels, stats, _ = cv2.connectedComponentsWithStats(ink, 8)
    size = TEXT_SIZE / px
    drop = np.zeros(n, bool)
    for i in range(1, n):
        w, h = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
        if max(w, h) > size:
            continue
        fill = stats[i, cv2.CC_STAT_AREA] / max(1, w * h)
        long_, short = max(w, h), max(1, min(w, h))
        dash = long_ >= 1.5 / px and long_ / short >= 4.0  # a dash of an axis
        dot = 0.6 / px <= long_ <= 2.5 / px and long_ / short >= 2.5  # its dot
        tilted = long_ >= 1.5 / px and fill < 0.35 and _straight(labels == i)
        if not dash and not dot and not tilted:
            drop[i] = True
    out[drop[labels]] = 0
    return out


def _straight(mask) -> bool:
    """Whether the pixels of a blot lie along one straight stroke."""
    ys, xs = np.nonzero(mask)
    if len(xs) < 5:
        return False
    pts = np.stack([xs, ys], 1).astype(np.float64)
    pts -= pts.mean(0)
    s = np.linalg.svd(pts, compute_uv=False)
    return s[1] < 0.18 * s[0]


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
    """A thin piece between two main ones is main: short (a corner, a
    junction), or running straight on from both (an edge whose middle came
    out pale — a hatch beside it took the darkness away); the contour would
    stay open there."""
    ends = []  # (point, unit direction pointing out of the piece) of main pieces
    for p, w in pieces:
        if w < MAIN_WIDTH or len(p) < 2:
            continue
        for a, b in ((p[0], p[1]), (p[-1], p[-2])):
            d = np.asarray(a, float) - np.asarray(b, float)
            n = float(np.hypot(*d))
            ends.append((np.asarray(a, float), d / n if n > 0 else d))
    near = {}
    for k, (q, _) in enumerate(ends):
        near.setdefault((int(q[0]) // 4, int(q[1]) // 4), []).append(k)

    def touching(q):
        x, y = int(round(q[0])), int(round(q[1]))
        out = []
        for gx in (x // 4 - 1, x // 4, x // 4 + 1):
            for gy in (y // 4 - 1, y // 4, y // 4 + 1):
                out += [k for k in near.get((gx, gy), ())
                        if abs(ends[k][0][0] - x) <= 2 and abs(ends[k][0][1] - y) <= 2]
        return out

    def straight_on(q, inward):
        # a main piece ending here that runs on in the thin piece's direction
        return any(abs(float(np.dot(ends[k][1], inward))) > 0.985 for k in touching(q))

    out = []
    for p, w in pieces:
        if w < MAIN_WIDTH and len(p) >= 2:
            pa = p.astype(np.float64)
            length = float(np.sum(np.hypot(*np.diff(pa, axis=0).T)))
            first, last = pa[1] - pa[0], pa[-2] - pa[-1]
            first /= max(float(np.hypot(*first)), 1e-9)
            last /= max(float(np.hypot(*last)), 1e-9)
            if touching(p[0]) and touching(p[-1]) and (
                    length <= longest or straight_on(p[0], first) and straight_on(p[-1], last)):
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
