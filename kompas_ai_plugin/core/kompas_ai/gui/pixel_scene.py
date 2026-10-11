"""The waiting screen: a pixel-art room at dawn, 320 × 180 pixels.

A young man in a gaming chair, seen from behind, rests his feet on a wide
window sill and rocks slowly, watching the sun rise over a city by the
water; then takes his feet down, turns, rolls to the desk and works, sips
coffee, stretches, rolls back, turns to the window and puts his feet up
again. The story is LOOP seconds long and its last frame is its first.

Built from layers: a sky with ordered dithering, clouds, the sun, a hazy
and a near city, water with the sun's path (cached where nothing moves),
the room with a transparent window, the small movements (city lights,
steam, the computer's LED, the cat breathing), then the man and his chair
drawn as a dark silhouette, its edges lit by the window (orange) and, at
the desk, by the monitor (blue). No smoothing anywhere: everything is
whole pixels, scaled up by the caller without filtering.
"""

from __future__ import annotations

import math
import random

import numpy as np
from PySide6.QtCore import QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPolygon

W, H = 320, 180
LOOP = 20.0

GLASS = QRect(124, 10, 152, 94)  # the window opening
HORIZON = 84
SUN = (222, 72)

SKY = ["#2b2a86", "#3c2f98", "#5634a4", "#7c3aa8", "#a8409e", "#d4508a", "#f06a6c",
       "#ff8a52", "#ffac56", "#ffcc6e"]

# the man and the chair
HAIR = "#110d22"
JACKET, JACKET_FOLD = "#1b1739", "#25204c"
PANTS = "#15122f"
SHOE = "#2c2862"
HAND = "#3b2340"
CHAIR, CHAIR_SEAM, CHAIR_MARK = "#100e22", "#3b1631", "#2a2660"
RIM_SUN, RIM_SUN2 = (255, 140, 74), (122, 48, 96)
RIM_SCREEN = (110, 140, 255)

BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0


def _c(hex_or_color, alpha=255) -> QColor:
    c = QColor(hex_or_color)
    c.setAlpha(alpha)
    return c


def _view(img: QImage) -> np.ndarray:
    """The pixels of an ARGB32 image as a (H, W, 4) BGRA array (writable)."""
    a = np.frombuffer(img.bits(), np.uint8, img.sizeInBytes())
    return a.reshape(img.height(), img.bytesPerLine() // 4, 4)[:, :img.width()]


def _new(transparent: bool = True) -> QImage:
    img = QImage(W, H, QImage.Format_ARGB32)
    img.fill(Qt.transparent if transparent else QColor("#000000"))
    return img


class _Pen:
    """Rectangles, polygons and thick lines in whole pixels."""

    def __init__(self, img: QImage):
        self.p = QPainter(img)
        self.p.setRenderHint(QPainter.Antialiasing, False)

    def end(self):
        self.p.end()

    def rect(self, x, y, w, h, c, alpha=255):
        self.p.fillRect(QRect(round(x), round(y), round(w), round(h)), _c(c, alpha))

    def poly(self, pts, c, alpha=255):
        self.p.setPen(Qt.NoPen)
        self.p.setBrush(_c(c, alpha))
        self.p.drawPolygon(QPolygon([QPoint(round(x), round(y)) for x, y in pts]))

    def line(self, a, b, width, c, alpha=255):
        self.p.setPen(QPen(_c(c, alpha), width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        self.p.drawLine(QPointF(*a), QPointF(*b))

    def disc(self, cx, cy, rx, c, ry=None, alpha=255):
        self.p.setPen(Qt.NoPen)
        self.p.setBrush(_c(c, alpha))
        self.p.drawEllipse(QPointF(cx, cy), rx, ry if ry is not None else rx)


# --- the still layers ---------------------------------------------------------------------

def _sky() -> QImage:
    """The sky behind the glass: bands of a few colours, dithered between."""
    img = _new(False)
    a = _view(img)
    y0, y1 = GLASS.top(), HORIZON
    pal = np.array([[QColor(c).blue(), QColor(c).green(), QColor(c).red()] for c in SKY])
    ys = np.arange(H)[:, None]
    xs = np.arange(W)[None, :]
    v = np.clip((ys - y0) / (y1 - y0), 0, 1) * (len(SKY) - 1)
    # the sky is brighter towards the sun
    v = np.clip(v + np.maximum(0, 1 - np.hypot(xs - SUN[0], (ys - SUN[1]) * 1.6) / 70) * 1.2,
                0, len(SKY) - 1)
    i = np.floor(v).astype(int)
    frac = v - i
    up = frac > BAYER[ys % 4, xs % 4]
    idx = np.clip(np.where(up, i + 1, i), 0, len(SKY) - 1)
    a[:, :, :3] = pal[idx]
    a[:, :, 3] = 255
    return img


def _clouds_layout():
    """Streaky clouds: rows of pixel bars, darker up high, lit near the sun."""
    rnd = random.Random(7)
    out = []
    for y in (13, 17, 20, 24, 28, 31, 35, 40, 44, 49, 54, 58, 63):
        k = (y - 10) / (HORIZON - 10)
        for _ in range(rnd.randint(3, 5)):
            x = rnd.randint(GLASS.left() - 30, GLASS.right() + 10)
            w = rnd.randint(8, 34)
            if k < 0.3:
                body, lit = "#3a2d8e", "#6a3ea8"
            elif k < 0.55:
                body, lit = "#7a3a9e", "#d0508a"
            else:
                body, lit = "#c84a86", "#ff8a5a"
            out.append((x, y, w, rnd.choice((2, 2, 3)), body, lit, rnd.uniform(0.6, 1.4)))
    return out


CLOUDS = _clouds_layout()


def _city() -> QImage:
    """A hazy far city, a near one with lit windows, a spire, a bridge."""
    img = _new()
    d = _Pen(img)
    rnd = random.Random(3)
    x = GLASS.left() - 4
    while x < GLASS.right():  # far, in the haze
        w = rnd.randint(5, 11)
        h = rnd.randint(8, 22) if abs(x + w / 2 - SUN[0]) > 16 else rnd.randint(2, 5)
        d.rect(x, HORIZON - h, w, h, "#6a3c9c")
        x += w + rnd.randint(0, 3)
    x = GLASS.left() - 2
    near = []
    while x < GLASS.right():
        w = rnd.randint(6, 12)
        h = rnd.randint(10, 30) if abs(x + w / 2 - SUN[0]) > 18 else rnd.randint(3, 6)
        near.append((x, w, h))
        x += w + rnd.randint(1, 4)
    for x, w, h in near:
        d.rect(x, HORIZON - h, w, h, "#2c2468")
        d.rect(x + w - 1, HORIZON - h, 1, h, "#4a3488")  # the side towards the sun
    # landmarks: a tall tower left, a spire right
    d.rect(150, HORIZON - 44, 9, 44, "#2c2468")
    d.rect(152, HORIZON - 48, 5, 4, "#2c2468")
    d.rect(158, HORIZON - 44, 1, 44, "#4a3488")
    d.rect(258, HORIZON - 40, 8, 40, "#2c2468")
    d.rect(260, HORIZON - 50, 4, 10, "#2c2468")
    d.rect(261, HORIZON - 58, 2, 8, "#2c2468")
    d.rect(262, HORIZON - 63, 1, 5, "#2c2468")
    d.rect(265, HORIZON - 40, 1, 40, "#4a3488")
    # the bridge over the water
    d.rect(196, HORIZON + 1, 74, 1, "#241c58")
    for px in range(200, 270, 12):
        d.rect(px, HORIZON + 1, 1, 3, "#241c58")
    d.end()
    return img


def _windows_of_city():
    """Positions of the lit windows of the near city (they flicker)."""
    rnd = random.Random(11)
    out = []
    for _ in range(70):
        x = rnd.randint(GLASS.left(), GLASS.right() - 2)
        if abs(x - SUN[0]) < 12:
            continue
        y = rnd.randint(HORIZON - 26, HORIZON - 3)
        out.append((x, y, rnd.choice(("#ffb35a", "#ffd27a", "#ff8a5a")), rnd.random()))
    return out


CITY_LIGHTS = _windows_of_city()


def _room() -> QImage:
    """Everything indoors; the window glass left transparent."""
    img = _new()
    d = _Pen(img)
    d.rect(0, 0, W, H, "#15123c")
    # walls a shade lighter near the window, darker in the corners
    d.rect(0, 0, 24, 150, "#110e32")
    d.rect(300, 0, 20, 150, "#110e32")
    # window: frame, top band, the thick left pillar, the glass cut out
    d.rect(108, 3, 176, 107, "#0d0b25")
    d.rect(108, 3, 176, 2, "#24205a")
    d.rect(112, 6, 168, 4, "#1d1950")
    d.rect(112, 6, 20, 98, "#100d2c")
    d.rect(131, 10, 1, 94, "#ff8a52", 120)  # the pillar's edge in the light
    d.p.setCompositionMode(QPainter.CompositionMode_Clear)
    d.p.fillRect(QRect(132, 10, 144, 94), Qt.transparent)
    d.p.setCompositionMode(QPainter.CompositionMode_SourceOver)
    d.rect(196, 10, 3, 94, "#0d0b25")  # a mullion
    d.rect(196, 10, 1, 94, "#ff8a52", 90)
    # the wide sill
    d.rect(104, 104, 186, 2, "#ff9a5a")
    d.rect(104, 106, 186, 3, "#5a2a5c")
    d.rect(104, 109, 186, 2, "#0d0b25")
    # the wall under the window: panels, a socket
    d.rect(112, 111, 140, 38, "#120f34")
    for x in (150, 200):
        d.rect(x, 114, 1, 32, "#1a1648")
    d.rect(165, 128, 6, 6, "#1d1950")
    d.rect(173, 128, 6, 6, "#1d1950")
    # floor: planks, warm light from the window lying across them
    d.rect(0, 150, W, 30, "#0f0c2a")
    for y in (156, 164, 173):
        d.rect(0, y, W, 1, "#151238")
    d.poly([(140, 150), (250, 150), (290, 180), (150, 180)], "#3a1d4a")
    d.poly([(165, 150), (220, 150), (250, 180), (185, 180)], "#5a2852")
    for x in range(170, 250, 9):
        d.rect(x, 152 + (x % 3) * 8, 6, 1, "#7a345a")

    _shelves(d)
    _desk(d)
    _right_side(d)
    # hanging plants from the top corners of the window
    for x0, length in ((116, 34), (284, 40)):
        for k in range(length):
            x = x0 + round(math.sin(k / 4.0) * 2)
            d.rect(x, 4 + k, 2, 1, "#1d4a3a" if k % 5 else "#2e6a4a")
            if k % 4 == 0:
                d.rect(x + (1 if k % 8 else -2), 4 + k, 2, 2, "#2e6a4a")
    d.end()
    return img


def _shelves(d: _Pen) -> None:
    for y in (30, 56):
        d.rect(0, y, 60, 3, "#2a2050")
        d.rect(0, y, 60, 1, "#3e2f6a")
    rnd = random.Random(5)
    x = 2
    for _ in range(9):
        w, h = rnd.randint(3, 5), rnd.randint(11, 17)
        d.rect(x, 30 - h, w, h, rnd.choice(("#3a2a6a", "#5a2a5a", "#2a3a6a", "#6a3a4a",
                                            "#2e4a5a")))
        d.rect(x, 32 - h, w, 1, "#120f30")
        x += w + 1
    # lower shelf: books lying, a plant, a cat figurine
    d.rect(3, 50, 16, 3, "#3a2a6a")
    d.rect(4, 47, 14, 3, "#5a2a5a")
    d.rect(26, 48, 7, 8, "#6a3a3a")  # pot
    for k in range(6):
        d.rect(24 + k * 2, 40 + (k % 3) * 2, 2, 8 - (k % 3) * 2, "#2e6a4a")
    d.rect(40, 47, 9, 9, "#c8b8c8")  # the cat figurine
    d.rect(40, 45, 2, 2, "#c8b8c8")
    d.rect(47, 45, 2, 2, "#c8b8c8")
    d.rect(42, 49, 1, 1, "#2a2050")
    d.rect(46, 49, 1, 1, "#2a2050")
    # posters and notes between the shelves and the window
    d.rect(68, 14, 24, 32, "#1d1950")
    d.poly([(70, 42), (80, 22), (90, 42)], "#3a3488")
    d.poly([(76, 30), (80, 22), (84, 30)], "#c8c8e8")
    d.rect(79, 18, 3, 3, "#c04a6a")
    d.rect(66, 52, 10, 12, "#24205a")
    d.rect(80, 50, 9, 9, "#2a2660")
    d.rect(94, 58, 10, 10, "#1d1950")
    d.rect(68, 55, 6, 1, "#3e3a7a")
    d.rect(68, 58, 6, 1, "#3e3a7a")


def _desk(d: _Pen) -> None:
    # top, drawers, legs
    d.rect(0, 100, 90, 4, "#2a2050")
    d.rect(0, 100, 90, 1, "#4a3a7a")
    d.rect(44, 104, 36, 46, "#1b1744")
    for y in (118, 133):
        d.rect(46, y, 32, 1, "#100d2c")
    for y in (110, 125, 140):
        d.rect(58, y, 8, 1, "#3e3a7a")
    d.rect(2, 104, 3, 46, "#1b1744")
    d.rect(18, 138, 20, 12, "#3a2440")  # a box on the floor
    d.rect(18, 138, 20, 1, "#5a3450")
    # monitor and tower
    d.rect(0, 58, 38, 36, "#0b0a1a")
    d.rect(16, 94, 6, 6, "#0b0a1a")
    d.rect(10, 99, 18, 1, "#0b0a1a")
    d.rect(50, 70, 11, 30, "#0e0c22")
    d.rect(51, 71, 9, 1, "#2a2660")
    for y in (76, 80, 84):
        d.rect(52, y, 3, 2, "#4a3a8a")
    # books, headphones on the desk
    d.rect(64, 94, 18, 3, "#3a2a6a")
    d.rect(65, 91, 16, 3, "#5a2a5a")
    d.rect(64, 88, 17, 3, "#2a3a6a")
    d.rect(66, 89, 14, 1, "#ff8a52")  # lit by the window
    d.rect(84, 96, 4, 4, "#0e0c22")


def _right_side(d: _Pen) -> None:
    # a plant on the sill, a little box with a green light
    d.rect(286, 92, 12, 12, "#8a4a3a")
    d.rect(286, 92, 12, 2, "#b0604a")
    for k, (dx, h) in enumerate(((0, 14), (3, 20), (6, 16), (9, 12), (-2, 10))):
        d.rect(288 + dx, 92 - h, 2, h, "#2e6a4a" if k % 2 else "#3e8a5a")
        d.rect(287 + dx, 92 - h, 2, 2, "#3e8a5a")
    d.rect(252, 96, 22, 8, "#2a2660")
    d.rect(252, 96, 22, 1, "#ff9a5a")
    # the night table and the bed
    d.rect(240, 110, 64, 40, "#1b1744")
    d.rect(240, 110, 64, 1, "#3e3a7a")
    d.rect(262, 126, 16, 1, "#3e3a7a")
    d.poly([(258, 180), (268, 128), (320, 120), (320, 180)], "#24307a")
    d.poly([(268, 128), (320, 120), (320, 126), (266, 136)], "#3a4a9a")
    for y in range(140, 180, 7):
        d.rect(262, y, 58, 1, "#1d2766")
    d.rect(304, 20, 14, 18, "#1d1950")  # a moon poster
    d.disc(311, 29, 4, "#c8c8e8")
    d.disc(313, 28, 4, "#1d1950")


# --- the man and his chair ------------------------------------------------------------------

KEYS = ("seat", "back", "head", "shoulder", "elbow", "hand", "elbow2", "hand2",
        "hip", "knee", "ankle", "toe", "knee2", "ankle2", "toe2")

RECLINE = dict(
    seat=(124, 133), back=((88, 84), (111, 79), (124, 134), (101, 140)), head=(107, 72),
    shoulder=(117, 90), elbow=(126, 108), hand=(134, 117), elbow2=(100, 104), hand2=(98, 118),
    hip=(128, 128), knee=(152, 112), ankle=(171, 101), toe=(176, 93),
    knee2=(150, 117), ankle2=(170, 104), toe2=(178, 98))
SIT_W = dict(RECLINE, back=((92, 82), (114, 80), (122, 134), (100, 138)), head=(108, 73),
             knee=(146, 128), ankle=(146, 148), toe=(152, 150),
             knee2=(142, 130), ankle2=(141, 149), toe2=(147, 151))
BACK = dict(
    seat=(108, 133), back=((96, 80), (120, 80), (120, 136), (96, 136)), head=(108, 71),
    shoulder=(122, 92), elbow=(124, 110), hand=(124, 120), elbow2=(94, 110), hand2=(94, 120),
    hip=(108, 130), knee=(108, 134), ankle=(108, 148), toe=(108, 150),
    knee2=(108, 134), ankle2=(108, 148), toe2=(108, 150))
DESK_OUT = dict(
    seat=(100, 133), back=((104, 82), (114, 84), (114, 136), (104, 136)), head=(94, 73),
    shoulder=(96, 88), elbow=(84, 102), hand=(70, 100), elbow2=(90, 104), hand2=(76, 104),
    hip=(98, 128), knee=(82, 127), ankle=(80, 147), toe=(74, 150),
    knee2=(84, 130), ankle2=(84, 148), toe2=(78, 150))
DESK = dict(
    seat=(90, 133), back=((96, 82), (106, 84), (106, 136), (96, 136)), head=(84, 74),
    shoulder=(86, 88), elbow=(72, 100), hand=(56, 97), elbow2=(80, 102), hand2=(62, 99),
    hip=(88, 128), knee=(72, 127), ankle=(70, 147), toe=(64, 150),
    knee2=(74, 130), ankle2=(74, 148), toe2=(68, 150))
GRAB = dict(DESK, elbow=(68, 98), hand=(56, 92))
SIP = dict(DESK, head=(85, 73), elbow=(74, 96), hand=(80, 80))
STRETCH = dict(DESK, head=(86, 72), elbow=(80, 62), hand=(76, 52), elbow2=(92, 64),
               hand2=(90, 53))

MUG_ON_DESK = (55, 92)


def _ease(k):
    k = max(0.0, min(1.0, k))
    return k * k * (3 - 2 * k)


def _mix(a, b, k):
    k = _ease(k)
    out = {}
    for key in KEYS:
        va, vb = a[key], b[key]
        if key == "back":
            out[key] = tuple((pa[0] + (pb[0] - pa[0]) * k, pa[1] + (pb[1] - pa[1]) * k)
                             for pa, pb in zip(va, vb))
        else:
            out[key] = (va[0] + (vb[0] - va[0]) * k, va[1] + (vb[1] - va[1]) * k)
    return out


# (start, end, from, to); the man holds the last pose between the steps
STORY = [(4.0, 5.0, RECLINE, SIT_W), (5.0, 5.8, SIT_W, BACK), (5.8, 6.8, BACK, DESK_OUT),
         (6.8, 7.6, DESK_OUT, DESK), (11.0, 11.5, DESK, GRAB), (11.5, 12.1, GRAB, SIP),
         (12.9, 13.5, SIP, GRAB), (13.5, 14.0, GRAB, DESK), (14.0, 14.8, DESK, STRETCH),
         (14.8, 15.5, STRETCH, DESK_OUT), (15.5, 16.3, DESK_OUT, BACK),
         (16.3, 17.1, BACK, SIT_W), (17.1, 18.1, SIT_W, RECLINE)]


def story(t: float):
    """(pose, rocking degrees, at the desk 0..1, typing, the mug in hand)."""
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
    if t < 4.0:
        rock_env = 1.0
    elif t > 17.6:
        rock_env = _ease((t - 17.6) / 1.0)
    else:
        rock_env = 0.0
    rock = 1.6 * math.sin(2 * math.pi * t / 4.0) * rock_env
    desk = _ease((t - 5.8) / 1.0) if t < 11 else (1.0 - _ease((t - 14.8) / 1.0))
    desk = max(0.0, min(1.0, desk if 5.8 <= t <= 15.8 else 0.0))
    typing = 7.6 <= t < 11.0 or 14.0 > t >= 13.8
    mug = 11.3 <= t < 13.3
    return pose, rock, desk, typing, mug


def _man(t: float) -> tuple[QImage, float]:
    pose, rock, desk, typing, mug = story(t)
    img = _new()
    d = _Pen(img)
    if abs(rock) > 1e-3:  # rocking about the feet on the sill; the base stays
        d.p.translate(174, 100)
        d.p.rotate(rock)
        d.p.translate(-174, -100)
    p = dict(pose)
    if typing:
        j = int(t * 10) % 2
        p["hand"] = (p["hand"][0] + j, p["hand"][1] - (1 - j))
        p["hand2"] = (p["hand2"][0] + (1 - j), p["hand2"][1] - j * 0.5)
    sx, sy = p["seat"]
    # legs: the far one first
    for knee, ankle, toe in (("knee2", "ankle2", "toe2"), ("knee", "ankle", "toe")):
        d.line(p["hip"], p[knee], 8, PANTS)
        d.line(p[knee], p[ankle], 7, PANTS)
        d.line(p[ankle], p[toe], 5, SHOE)
    # seat and the far armrest
    d.rect(sx - 15, sy - 3, 30, 6, CHAIR)
    # body, head, hair, headphones
    d.line(p["hip"], p["shoulder"], 17, JACKET)
    d.line((p["hip"][0] + 3, p["hip"][1] - 4), (p["shoulder"][0] + 3, p["shoulder"][1] + 4), 2,
           JACKET_FOLD)
    hx, hy = p["head"]
    d.line(p["shoulder"], (hx, hy + 6), 9, JACKET)  # neck and hood
    d.disc(hx, hy, 7, HAIR, 7.5)
    sway = 1 if (t % 2.0) > 1.0 else 0  # the hair stirs a little
    for dx, dy, h in ((-5, -5, 3), (-2, -7, 3), (2, -7, 3 + sway), (5, -4, 2), (6, -1, 2)):
        d.rect(hx + dx, hy + dy - h + 1, 2, h, HAIR)
    d.line((hx - 6, hy - 2), (hx + 5, hy - 6), 1, "#0a0816")
    d.rect(hx - 7, hy - 1, 3, 5, "#0a0816")
    led = "#c070ff" if (t % 1.0) < 0.8 else "#6a3a9a"
    d.rect(hx - 7, hy + 1, 1, 1, led)
    # the chair's back with its seam and mark
    back = p["back"]
    d.poly(back, CHAIR)
    (ax, ay), (bx, by), (cx, cy), (ex, ey) = back
    mid_top = ((ax + bx) / 2, (ay + by) / 2)
    mid_bot = ((cx + ex) / 2, (cy + ey) / 2)
    d.line((ax + 2, ay + 3), (ex + 2, ey - 3), 1, CHAIR_SEAM)
    d.line((bx - 2, by + 3), (cx - 2, cy - 3), 1, CHAIR_SEAM)
    mx, my = mid_top[0] + (mid_bot[0] - mid_top[0]) * 0.22, mid_top[1] + (mid_bot[1] - mid_top[1]) * 0.22
    width = math.dist((ax, ay), (bx, by))
    if width > 14:
        d.line((mx - 3, my - 2), (mx + 3, my + 2), 1, CHAIR_MARK)
        d.line((mx - 3, my + 2), (mx + 3, my - 2), 1, CHAIR_MARK)
    # arms and hands, the mug when he drinks
    for el, ha in (("elbow2", "hand2"), ("elbow", "hand")):
        d.line(p["shoulder"], p[el], 7, JACKET)
        d.line(p[el], p[ha], 6, JACKET)
        d.rect(p[ha][0] - 1, p[ha][1] - 1, 3, 3, HAND)
    if min(p["hand"][1], p["hand2"][1]) < hy - 4:  # arms up: the head in front
        d.disc(hx, hy, 7, HAIR, 7.5)
        d.rect(hx - 7, hy - 1, 3, 5, "#0a0816")
    if mug:
        mx, my = p["hand"]
        d.rect(mx - 3, my - 5, 6, 7, "#c8b8d8")
        d.rect(mx + 3, my - 3, 2, 3, "#c8b8d8")
    d.end()
    return img, desk


def _rim(img: QImage, desk: float, t: float) -> None:
    """Light the edges of the silhouette: the window (right and up), the
    monitor (left) while he works at the desk."""
    a = _view(img)
    m = a[:, :, 3] > 0
    right = np.zeros_like(m)
    right[:, :-1] = m[:, :-1] & ~m[:, 1:]
    top = np.zeros_like(m)
    top[1:, :] = m[1:, :] & ~m[:-1, :]
    window_side = np.arange(W)[None, :] > 60
    diag = np.zeros_like(m)  # a slanting edge facing up and right
    diag[1:, :-1] = m[1:, :-1] & ~m[:-1, 1:]
    right |= diag & ~top
    a[top & window_side, 0:3] = RIM_SUN2[::-1]
    a[right & window_side, 0:3] = RIM_SUN[::-1]
    if desk > 0.05:
        left = np.zeros_like(m)
        left[:, 1:] = m[:, 1:] & ~m[:, :-1]
        flicker = 0.85 + 0.15 * ((int(t * 12) * 7) % 5) / 4
        k = desk * flicker
        sel = left & (np.arange(H)[:, None] < 120)
        a[sel, 0:3] = (np.array(RIM_SCREEN[::-1]) * k
                       + a[sel, 0:3].astype(float) * (1 - k)).astype(np.uint8)


def _chair_base(d: _Pen, t: float) -> None:
    pose = story(t)[0]
    sx = pose["seat"][0]
    d.rect(sx - 2, 136, 4, 18, CHAIR)
    d.rect(sx - 20, 154, 40, 3, CHAIR)
    d.rect(sx - 20, 154, 40, 1, "#2a2660")
    for dx in (-20, -2, 16):
        d.rect(sx + dx, 157, 4, 3, "#0a0816")


# --- frames -----------------------------------------------------------------------------

_CACHE: dict = {}


def _still():
    if not _CACHE:
        _CACHE["sky"] = _sky()
        _CACHE["city"] = _city()
        _CACHE["room"] = _room()
    return _CACHE


def paint(img: QImage, t: float) -> None:
    """Frame at ``t`` seconds of the loop onto ``img`` (W × H, ARGB32)."""
    t %= LOOP
    s = _still()
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, False)
    p.drawImage(0, 0, s["sky"])
    d = _Pen.__new__(_Pen)
    d.p = p
    p.setClipRect(GLASS)
    # the clouds drift a little to and fro (and come back for the loop)
    for x, y, w, h, body, lit, speed in CLOUDS:
        dx = 4 * speed * math.sin(2 * math.pi * t / LOOP)
        d.rect(x + dx, y, w, h, body)
        d.rect(x + dx + 2, y + h - 1, w - 3, 1, lit)
    # the sun, a soft halo of two rings
    d.disc(SUN[0], SUN[1], 11, "#ffb060", alpha=90)
    d.disc(SUN[0], SUN[1], 8, "#ffd27a")
    d.disc(SUN[0], SUN[1], 6, "#fff0b8")
    p.drawImage(0, 0, s["city"])
    for x, y, c, phase in CITY_LIGHTS:  # windows going on and off
        if (math.sin(2 * math.pi * (t / LOOP * 4 + phase)) + 1) / 2 > 0.25:
            d.rect(x, y, 1, 1, c)
    _water(d, t)
    p.setClipping(False)
    p.drawImage(0, 0, s["room"])
    _small_things(d, t)
    _chair_base(d, t)
    man, desk = _man(t)
    _rim(man, desk, t)
    p.drawImage(0, 0, man)
    # the desk's drawers stand in front of his legs when he sits at it
    p.drawImage(QRect(40, 104, 42, 46), s["room"], QRect(40, 104, 42, 46))
    p.end()


def _water(d: _Pen, t: float) -> None:
    for y in range(HORIZON + 1, GLASS.bottom() + 1):
        k = (y - HORIZON) / (GLASS.bottom() - HORIZON)
        d.rect(GLASS.left(), y, GLASS.width(), 1, "#3a2c86" if k < 0.4 else "#2a2068")
    rnd = random.Random(int(t * 4) % 80)  # shimmer: 4 changes a second, 80 per loop
    for _ in range(26):  # the sky in the ripples
        y = rnd.randint(HORIZON + 2, GLASS.bottom())
        x = rnd.randint(GLASS.left(), GLASS.right() - 8)
        d.rect(x, y, rnd.randint(3, 9), 1, rnd.choice(("#c04a8a", "#6a3aa0", "#e0607a")))
    for y in range(HORIZON + 1, GLASS.bottom() + 1, 2):  # the sun's path
        spread = 3 + (y - HORIZON) * 0.25
        w = max(2, round(spread * 2 * (0.6 + 0.4 * rnd.random())))
        c = "#ffe08a" if y < HORIZON + 8 else ("#ffb060" if y < HORIZON + 14 else "#ff8a52")
        d.rect(SUN[0] - w // 2 + rnd.randint(-1, 1), y, w, 1, c)


def _small_things(d: _Pen, t: float) -> None:
    # the screen: windows of a program, a slight flicker
    flick = 235 + (int(t * 12) * 37) % 20
    d.rect(1, 59, 36, 33, "#2a3ea8", flick)
    d.rect(1, 59, 36, 3, "#1a2470")
    d.rect(2, 63, 8, 28, "#1d2a80")
    for k in range(6):
        d.rect(3, 64 + k * 4, 6, 2, "#5a6ad8")
    d.rect(12, 64, 23, 12, "#3a5ad8")
    d.rect(13, 65, 10, 1, "#c8d0ff")
    d.rect(13, 68, 18, 1, "#8aa0ff")
    d.rect(13, 71, 14, 1, "#8aa0ff")
    d.rect(12, 79, 23, 11, "#2a46c0")
    for k in range(3):
        d.rect(14, 81 + k * 3, 4, 2, "#c86ad8")
        d.rect(20, 81 + k * 3, 12, 1, "#8aa0ff")
    # the screen lights the desk; the keyboard glows
    d.rect(0, 100, 40, 1, "#4a5ad8")
    glow = "#9a5aff" if int(t * 2) % 2 else "#8a4af0"
    d.rect(14, 96, 34, 3, "#2a2060")
    for x in range(15, 47, 3):
        d.rect(x, 96 + (x // 3) % 2, 2, 1, glow)
    d.rect(40, 97, 4, 2, "#3a2a70")  # mouse
    # the tower's LED blinks
    d.rect(57, 72, 2, 2, "#5aff9a" if (t % 1.0) < 0.5 else "#1d4a3a")
    # the mug and its steam (unless he holds it)
    _, _, _, _, mug = story(t)
    if not mug:
        mx, my = MUG_ON_DESK
        d.rect(mx - 3, my, 6, 8, "#c8b8d8")
        d.rect(mx + 3, my + 2, 2, 3, "#c8b8d8")
        d.rect(mx - 3, my, 6, 1, "#ffe0f0")
        for k in range(3):
            ph = (t / 1.25 + k / 3) % 1.0
            sx = mx + round(math.sin((ph + k) * 6) * 1.5)
            d.rect(sx, my - 2 - ph * 10, 1, 1, "#c8b8e8", int(200 * (1 - ph)))
    # the cat asleep on the bed, breathing
    breath = 1 if (t % 2.5) > 1.25 else 0
    d.disc(300, 132 - breath * 0.5, 11, "#b8b8d0", 5 + breath * 0.5)
    d.disc(296, 131, 5, "#4a4a6a", 3)
    d.disc(289, 130, 4, "#d0d0e8", 3.5)
    d.rect(286, 125, 2, 3, "#d0d0e8")
    d.rect(291, 125, 2, 3, "#d0d0e8")
    d.rect(308, 135, 7, 2, "#8a8aa8")
    d.rect(300, 127 - breath, 8, 1, "#ff9a6a")  # the window's light on its back
