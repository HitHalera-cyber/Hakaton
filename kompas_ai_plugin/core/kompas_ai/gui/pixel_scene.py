"""The waiting screen: a pixel-art room at dawn, 384 × 216 pixels.

The room and the man resting with his feet on the window sill come from the
concept picture (assets/, made by prototype/room_assets.py): the room
without him, and him with his chair cut out. He rocks there; then — drawn
here in the same silhouette, lit at its edges by the window — takes his feet
down, turns, rolls to the desk, types, drinks from the mug, stretches, rolls
back, turns and puts his feet up again, where the cut-out takes over. The
change between the two is a pixel dissolve. The story is LOOP seconds and
its last frame is its first.

Small movements over the still room: the clouds drift, the windows of the
city flicker, the water ripples, the screen flickers, the tower's lights
blink, the keyboard glows, steam rises from the mug.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from PySide6.QtCore import QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPolygon

W, H = 384, 216
LOOP = 20.0

BODY, BODY_FOLD = "#020318", "#0e0d35"
CHAIR, CHAIR_SIDE, CHAIR_MARK = "#010213", "#091050", "#2429a7"
SHOE = "#101661"
RIM, RIM_TOP = (250, 117, 71), (203, 68, 113)
RIM_SCREEN = (120, 140, 255)
FEET = (205, 112)  # he rocks about them
BASE_Y = 170  # below it the chair's base stays put
SCREEN = QRect(0, 71, 42, 38)
KEYS = QRect(18, 114, 40, 8)
TOWER = QRect(64, 85, 7, 24)
SKY = QRect(137, 12, 194, 50)  # the clouds over the city
WATER = QRect(137, 104, 194, 21)
DESK_FRONT = QRect(0, 121, 101, 95)  # stands in front of his legs at the desk

BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0


def _asset_dir() -> Path:
    here = Path(__file__).resolve().parent / "assets"
    if here.is_dir():
        return here
    return Path(getattr(sys, "_MEIPASS", "")) / "kompas_ai" / "gui" / "assets"


_A: dict = {}


def _assets() -> dict:
    if not _A:
        d = _asset_dir()
        for name in ("room_bg", "room_nomug", "room_man"):
            _A[name] = QImage(str(d / f"{name}.png")).convertToFormat(QImage.Format_ARGB32)
        _A["lights"] = _city_lights(_A["room_bg"])
        _A["man_upper"] = _clip(_A["room_man"], True)
        _A["man_base"] = _clip(_A["room_man"], False)
    return _A


def _view(img: QImage) -> np.ndarray:
    a = np.frombuffer(img.bits(), np.uint8, img.sizeInBytes())
    return a.reshape(img.height(), img.bytesPerLine() // 4, 4)[:, :img.width()]


def _city_lights(bg: QImage):
    """The lit windows of the city: small bright warm pixels among darker ones."""
    a = _view(bg).astype(int)
    out = []
    for y in range(64, 104):
        for x in range(138, 330):
            if abs(x - 266) < 14:
                continue  # not the sun's column
            b, g, r = a[y, x, 0], a[y, x, 1], a[y, x, 2]
            if r > 200 and g > 120 and b < 150:
                around = a[y, x - 1, :3].sum() + a[y, x + 1, :3].sum()
                if around < 2 * (r + g + b) * 0.8:
                    out.append((x, y, ((x * 7 + y * 13) % 17) / 17.0,
                                QColor(int(a[y, x - 1, 2]), int(a[y, x - 1, 1]),
                                       int(a[y, x - 1, 0]))))
    return out


def _clip(img: QImage, upper: bool) -> QImage:
    out = QImage(W, H, QImage.Format_ARGB32)
    out.fill(Qt.transparent)
    q = QPainter(out)
    q.setClipRect(QRect(0, 0, W, BASE_Y) if upper else QRect(0, BASE_Y, W, H - BASE_Y))
    q.drawImage(0, 0, img)
    q.end()
    return out


class _Pen:
    def __init__(self, img: QImage):
        self.p = QPainter(img)
        self.p.setRenderHint(QPainter.Antialiasing, False)

    def end(self):
        self.p.end()

    def rect(self, x, y, w, h, c):
        self.p.fillRect(QRect(round(x), round(y), round(w), round(h)), QColor(c))

    def poly(self, pts, c):
        self.p.setPen(Qt.NoPen)
        self.p.setBrush(QColor(c))
        self.p.drawPolygon(QPolygon([QPoint(round(x), round(y)) for x, y in pts]))

    def line(self, a, b, width, c):
        self.p.setPen(QPen(QColor(c), width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        self.p.drawLine(QPointF(*a), QPointF(*b))

    def disc(self, cx, cy, rx, c, ry=None):
        self.p.setPen(Qt.NoPen)
        self.p.setBrush(QColor(c))
        self.p.drawEllipse(QPointF(cx, cy), rx, ry if ry is not None else rx)


# --- poses (the man drawn) -------------------------------------------------------------------

POSE_KEYS = ("seat", "back", "head", "shoulder", "elbow", "hand", "elbow2", "hand2",
             "hip", "knee", "ankle", "toe", "knee2", "ankle2", "toe2")

RECLINE = dict(
    seat=(145, 166), back=((103, 96), (127, 92), (146, 160), (110, 188)), head=(124, 88),
    shoulder=(136, 112), elbow=(152, 132), hand=(166, 139), elbow2=(118, 128), hand2=(116, 146),
    hip=(150, 148), knee=(178, 117), ankle=(201, 113), toe=(206, 100),
    knee2=(176, 124), ankle2=(200, 121), toe2=(207, 109))
SIT_W = dict(RECLINE, back=((106, 96), (130, 94), (144, 164), (112, 182)), head=(126, 88),
             knee=(170, 160), ankle=(172, 190), toe=(181, 194),
             knee2=(166, 163), ankle2=(166, 191), toe2=(175, 195))
BACK = dict(
    seat=(132, 166), back=((114, 94), (150, 94), (150, 172), (114, 172)), head=(132, 85),
    shoulder=(150, 112), elbow=(158, 140), hand=(158, 156), elbow2=(108, 140), hand2=(108, 156),
    hip=(132, 160), knee=(132, 168), ankle=(132, 190), toe=(132, 194),
    knee2=(132, 168), ankle2=(132, 190), toe2=(132, 194))
DESK_OUT = dict(
    seat=(124, 166), back=((128, 96), (146, 98), (146, 174), (128, 174)), head=(112, 89),
    shoulder=(116, 108), elbow=(100, 126), hand=(84, 120), elbow2=(108, 128), hand2=(92, 124),
    hip=(120, 160), knee=(100, 158), ankle=(98, 190), toe=(90, 194),
    knee2=(104, 162), ankle2=(103, 191), toe2=(95, 195))
DESK = dict(
    seat=(114, 166), back=((118, 96), (136, 98), (136, 174), (118, 174)), head=(100, 90),
    shoulder=(104, 108), elbow=(84, 124), hand=(58, 117), elbow2=(94, 126), hand2=(66, 119),
    hip=(110, 160), knee=(90, 158), ankle=(88, 190), toe=(80, 194),
    knee2=(94, 162), ankle2=(93, 191), toe2=(85, 195))
GRAB = dict(DESK, elbow=(84, 120), hand=(68, 112))
SIP = dict(DESK, head=(101, 89), elbow=(88, 112), hand=(94, 96))
STRETCH = dict(DESK, head=(102, 88), elbow=(90, 76), hand=(80, 60), elbow2=(118, 76),
               hand2=(126, 60))


def _ease(k):
    k = max(0.0, min(1.0, k))
    return k * k * (3 - 2 * k)


def _mix(a, b, k):
    k = _ease(k)
    out = {}
    for key in POSE_KEYS:
        if key == "back":
            out[key] = tuple((pa[0] + (pb[0] - pa[0]) * k, pa[1] + (pb[1] - pa[1]) * k)
                             for pa, pb in zip(a[key], b[key]))
        else:
            out[key] = (a[key][0] + (b[key][0] - a[key][0]) * k,
                        a[key][1] + (b[key][1] - a[key][1]) * k)
    return out


STORY = [(4.0, 5.0, RECLINE, SIT_W), (5.0, 5.8, SIT_W, BACK), (5.8, 6.8, BACK, DESK_OUT),
         (6.8, 7.6, DESK_OUT, DESK), (11.0, 11.5, DESK, GRAB), (11.5, 12.1, GRAB, SIP),
         (12.9, 13.5, SIP, GRAB), (13.5, 14.0, GRAB, DESK), (14.0, 14.8, DESK, STRETCH),
         (14.8, 15.5, STRETCH, DESK_OUT), (15.5, 16.3, DESK_OUT, BACK),
         (16.3, 17.1, BACK, SIT_W), (17.1, 18.1, SIT_W, RECLINE)]
CUT_OUT = (3.6, 4.0)  # the concept's man dissolves into the drawn one
CUT_IN = (18.1, 18.5)  # and back


def story(t: float) -> dict:
    t %= LOOP
    pose = RECLINE
    for t0, t1, a, b in STORY:
        if t >= t1:
            pose = b
        elif t >= t0:
            pose = _mix(a, b, (t - t0) / (t1 - t0))
            break
        else:
            break
    env = 1.0 if t < 4.0 else (_ease((t - 17.6) / 1.0) if t > 17.6 else 0.0)
    rock = 1.0 * math.sin(2 * math.pi * t / 4.0) * env
    if t < CUT_OUT[0] or t >= CUT_IN[1]:
        drawn = 0.0
    elif t < CUT_OUT[1]:
        drawn = (t - CUT_OUT[0]) / (CUT_OUT[1] - CUT_OUT[0])
    elif t < CUT_IN[0]:
        drawn = 1.0
    else:
        drawn = 1.0 - (t - CUT_IN[0]) / (CUT_IN[1] - CUT_IN[0])
    desk = 0.0
    if 5.8 <= t < 7.6:
        desk = _ease((t - 5.8) / 1.8)
    elif 7.6 <= t < 14.8:
        desk = 1.0
    elif 14.8 <= t < 16.3:
        desk = 1.0 - _ease((t - 14.8) / 1.5)
    return dict(pose=pose, rock=rock, drawn=drawn, desk=desk,
                typing=7.6 <= t < 11.0, mug=11.4 <= t < 13.4, t=t)


def _draw_man(s: dict, upper: bool) -> QImage:
    """The drawn man and his chair: the part above BASE_Y, or the base."""
    img = QImage(W, H, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    d = _Pen(img)
    p = dict(s["pose"])
    if not upper:
        sx = p["seat"][0]
        d.rect(sx - 3, BASE_Y, 6, 22, CHAIR)
        d.rect(sx - 34, 191, 68, 4, CHAIR)
        d.rect(sx - 34, 191, 68, 1, CHAIR_SIDE)
        for dx in (-36, -4, 28):
            d.rect(sx + dx, 195, 8, 5, "#000008")
        d.end()
        return img
    d.p.setClipRect(QRect(0, 0, W, BASE_Y))
    if s["typing"]:
        j = int(s["t"] * 10) % 2
        p["hand"] = (p["hand"][0] + j, p["hand"][1] - (1 - j))
        p["hand2"] = (p["hand2"][0] + (1 - j), p["hand2"][1] - j)
    sx, sy = p["seat"]
    for knee, ankle, toe in (("knee2", "ankle2", "toe2"), ("knee", "ankle", "toe")):
        d.line(p["hip"], p[knee], 15, BODY)
        d.line(p[knee], p[ankle], 12, BODY)
        d.line(p[ankle], p[toe], 9, SHOE)
    d.rect(sx - 30, sy - 6, 60, 10, CHAIR)  # the seat
    d.rect(sx - 30, sy - 6, 60, 1, CHAIR_SIDE)
    (hpx, hpy), (spx, spy) = p["hip"], p["shoulder"]
    ux, uy = spx - hpx, spy - hpy
    n = math.hypot(ux, uy) or 1.0
    nx, ny = -uy / n, ux / n
    d.poly([(hpx + nx * 12, hpy + ny * 12), (spx + nx * 16, spy + ny * 16 + 3),
            (spx - nx * 16, spy - ny * 16 + 3), (hpx - nx * 12, hpy - ny * 12)], BODY)
    d.disc(spx, spy + 2, 15, BODY, 8)  # the shoulders under the hood
    hx, hy = p["head"]
    d.line(p["shoulder"], (hx, hy + 8), 15, BODY)
    d.disc(hx, hy, 11, BODY, 12)
    sway = 1 if (s["t"] % 2.0) > 1.0 else 0  # the hair stirs a little
    for dx, dy, r in ((-8, -6, 5), (-3, -10, 5), (3, -10, 5), (8, -6, 4.5), (-11, 0, 4),
                      (10, 0, 3.5), (-6, -13, 3), (5, -13 - sway, 3)):
        d.disc(hx + dx, hy + dy, r, BODY)
    # headphones: the band over the hair, the cups with a little light
    d.p.setPen(QPen(QColor("#141640"), 2))
    d.p.setBrush(Qt.NoBrush)
    d.p.drawArc(QRect(round(hx - 12), round(hy - 14), 24, 24), 20 * 16, 140 * 16)
    for side in (-1, 1):
        d.disc(hx + side * 11, hy + 2, 3.5, "#0a0a26", 4.5)
    d.rect(hx - 12, hy + 2, 1, 2, "#c070ff" if (s["t"] % 1.0) < 0.8 else "#5a2a8a")
    # the chair's back with its seams and mark
    back = p["back"]
    (ax, ay), (bx, by) = back[0], back[1]
    d.poly([(ax + 2, ay - 6), (bx - 2, by - 6), (bx, by), (ax, ay)], CHAIR)  # headrest
    d.poly(back, CHAIR)
    (ax, ay), (bx, by), (cx, cy), (ex, ey) = back
    d.line((ax + 3, ay + 4), (ex + 3, ey - 4), 2, CHAIR_SIDE)
    d.line((bx - 3, by + 4), (cx - 3, cy - 4), 2, CHAIR_SIDE)
    if math.dist((ax, ay), (bx, by)) > 20:
        mx, my = ax + (bx - ax) / 2 + (ex - ax) * 0.18, ay + (by - ay) / 2 + (ey - ay) * 0.18
        d.line((mx - 5, my - 4), (mx + 5, my + 4), 2, CHAIR_MARK)
        d.line((mx - 5, my + 4), (mx + 5, my - 4), 2, CHAIR_MARK)
    # arms and hands
    for el, ha in (("elbow2", "hand2"), ("elbow", "hand")):
        d.line(p["shoulder"], p[el], 11, BODY)
        d.line(p[el], p[ha], 9, BODY)
        d.disc(p[ha][0], p[ha][1], 3, "#1a1240")
    if min(p["hand"][1], p["hand2"][1]) < hy - 6:  # arms up: the head in front
        d.disc(hx, hy, 12, BODY, 13)
    if s["mug"]:
        mx, my = p["hand"]
        d.rect(mx - 6, my - 10, 11, 13, "#2429a7")
        d.rect(mx + 5, my - 7, 3, 6, "#2429a7")
        d.rect(mx - 6, my - 10, 11, 2, "#6a7ae0")
    d.end()
    return img


def _rim(img: QImage, desk: float, t: float) -> None:
    """Light the edges: from the window (right and up), from the screen
    (left) while he works at the desk."""
    a = _view(img)
    m = a[:, :, 3] > 0
    right = np.zeros_like(m)
    right[:, :-1] = m[:, :-1] & ~m[:, 1:]
    top = np.zeros_like(m)
    top[1:, :] = m[1:, :] & ~m[:-1, :]
    diag = np.zeros_like(m)
    diag[1:, :-1] = m[1:, :-1] & ~m[:-1, 1:]
    edge = right | (diag & ~top)
    checker = BAYER[np.arange(H)[:, None] % 4, np.arange(W)[None, :] % 4]
    for dist, color, share in ((2, RIM_TOP, 0.6), (3, (19, 15, 62), 0.6), (4, (19, 15, 62), 0.3)):
        band = np.zeros_like(m)
        band[:, :-dist] = m[:, :-dist] & ~m[:, dist:]
        band &= ~edge & (checker < share)
        a[band, 0:3] = color[::-1]
    a[top, 0:3] = RIM_TOP[::-1]
    a[edge, 0:3] = RIM[::-1]
    if desk > 0.05:
        left = np.zeros_like(m)
        left[:, 1:] = m[:, 1:] & ~m[:, :-1]
        k = desk * (0.8 + 0.2 * ((int(t * 12) * 7) % 5) / 4)
        sel = left & (np.arange(H)[:, None] < 150)
        a[sel, 0:3] = (np.array(RIM_SCREEN[::-1]) * k + a[sel, 0:3] * (1 - k)).astype(np.uint8)


def _dissolve(a: QImage, b: QImage, k: float) -> QImage:
    """Pixels of ``b`` where the ordered threshold is below k, else of ``a``."""
    va, vb = _view(a), _view(b)
    take_b = BAYER[np.arange(H)[:, None] % 4, np.arange(W)[None, :] % 4] < k
    out = QImage(W, H, QImage.Format_ARGB32)
    _view(out)[:] = np.where(take_b[..., None], vb, va)
    return out


def _rocked(p: QPainter, img: QImage, rock: float) -> None:
    """The upper part turned about the feet (the base is drawn as it is)."""
    p.save()
    if abs(rock) > 1e-3:
        p.translate(*FEET)
        p.rotate(rock)
        p.translate(-FEET[0], -FEET[1])
    p.drawImage(0, 0, img)
    p.restore()


def paint(img: QImage, t: float) -> None:
    """Frame at ``t`` seconds onto ``img`` (W × H, ARGB32)."""
    a = _assets()
    s = story(t)
    t = s["t"]
    room = a["room_nomug"] if s["mug"] else a["room_bg"]
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, False)
    p.setRenderHint(QPainter.SmoothPixmapTransform, False)
    p.drawImage(0, 0, room)
    _ambient(p, a, t, mug_on_desk=not s["mug"])
    if s["drawn"] <= 0:
        upper, base = a["man_upper"], a["man_base"]
    else:
        upper = _draw_man(s, True)
        _rim(upper, s["desk"], t)
        base = _draw_man(s, False)
        if s["drawn"] < 1:  # the concept's man and the drawn one, dissolving
            upper = _dissolve(a["man_upper"], upper, s["drawn"])
            base = _dissolve(a["man_base"], base, s["drawn"])
    p.drawImage(0, 0, base)
    _rocked(p, upper, s["rock"])
    if s["desk"] > 0:  # the desk stands in front of his knees
        p.drawImage(DESK_FRONT, room, DESK_FRONT)
    p.end()


def _ambient(p: QPainter, a: dict, t: float, mug_on_desk: bool) -> None:
    bg = a["room_bg"]
    # clouds: the sky band slides a few pixels to and fro (and back for the loop)
    for y0, y1, amp in ((12, 36, 3.0), (36, 60, 1.6)):
        dx = round(amp * math.sin(2 * math.pi * t / LOOP))
        if dx:
            band = QRect(SKY.left(), y0, SKY.width(), y1 - y0)
            p.save()
            p.setClipRect(band)
            p.drawImage(band.translated(dx, 0), bg, band)
            p.restore()
    # the city's windows go on and off
    for x, y, phase, dark in a["lights"]:
        if math.sin(2 * math.pi * (t / LOOP * 3 + phase)) > 0.55:
            p.fillRect(x, y, 1, 1, dark)
    # ripples: rows of the water shift by a pixel, now one way, now the other
    for y in range(WATER.top(), WATER.bottom() + 1):
        r = (int(t * 3) + y) % 3
        dx = 1 if r == 0 else (-1 if r == 1 else 0)
        if dx:
            row = QRect(WATER.left(), y, WATER.width(), 1)
            p.save()
            p.setClipRect(row)
            p.drawImage(row.translated(dx, 0), bg, row)
            p.restore()
    # the screen flickers a little, the cursor blinks
    p.fillRect(SCREEN, QColor(120, 150, 255, 10 + (int(t * 12) * 37) % 18))
    if int(t * 2) % 2:
        p.fillRect(30, 96, 3, 1, QColor("#c8d0ff"))
    # the keyboard breathes, the tower's lights blink
    p.fillRect(KEYS, QColor(170, 80, 255, 25 + round(20 * (1 + math.sin(2 * math.pi * t / 2.5)))))
    for k, y in enumerate(range(TOWER.top() + 3, TOWER.bottom(), 5)):
        if (int(t * 2) + k) % 3 == 0:
            p.fillRect(TOWER.left() + 2, y, 3, 2, QColor("#0a0a30"))
    # steam from the mug
    if mug_on_desk:
        for k in range(4):
            ph = (t / 1.25 + k / 4) % 1.0
            sx = 66 + k % 2 * 3 + round(math.sin((ph + k) * 6) * 1.5)
            p.fillRect(sx, round(106 - ph * 14), 1, 1, QColor(200, 200, 240, int(150 * (1 - ph))))
