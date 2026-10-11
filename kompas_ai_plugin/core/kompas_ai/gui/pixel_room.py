"""A pixel-art room for the waiting screen: an engineer in a gaming chair,
feet on the window sill, rocks and watches the sunrise; now and then turns
to the computer and draws a part on it, stretches, turns back.

Everything is drawn on a small image (W × H pixels) with plain rectangles
and thick lines, no smoothing, and scaled up without filtering — the look
of a 2D game. ``paint_room(image, t, sun)``: ``t`` seconds into the loop,
``sun`` from 0 (before dawn) to 1 (the sun up) — the loader ties it to how
far the recognition has got.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPolygon

W, H = 192, 108
LOOP = 26.0  # seconds of the whole story

# --- colours --------------------------------------------------------------------------

SKY_NIGHT = ["#141a3c", "#1d2350", "#2a2c62", "#3a3270", "#4a3a78", "#5a4280"]
SKY_DAWN = ["#3b4f9a", "#6a64b0", "#b77ab0", "#ee8f8a", "#f7b36e", "#ffd88a"]
SKIN, SKIN_SHADE = "#f2c79f", "#d9a77f"
HAIR = "#3b2418"
HOODIE, HOODIE_SHADE = "#3d7fd6", "#2f63ab"
PANTS, PANTS_SHADE = "#4a5b8c", "#3a4870"
SHOES = "#eeeeee"
CHAIR, CHAIR_ACCENT = "#1c1c26", "#d6383f"
WOOD, WOOD_DARK, WOOD_LIGHT = "#8a5a3a", "#6a4229", "#a87650"


def _mix(a: str, b: str, k: float) -> QColor:
    ca, cb = QColor(a), QColor(b)
    k = max(0.0, min(1.0, k))
    return QColor(round(ca.red() + (cb.red() - ca.red()) * k),
                  round(ca.green() + (cb.green() - ca.green()) * k),
                  round(ca.blue() + (cb.blue() - ca.blue()) * k))


def _ease(k: float) -> float:
    k = max(0.0, min(1.0, k))
    return k * k * (3 - 2 * k)


class _Pix:
    """Pixel-art drawing helpers on a QPainter without antialiasing."""

    def __init__(self, p: QPainter):
        self.p = p

    def rect(self, x, y, w, h, c):
        self.p.fillRect(round(x), round(y), round(w), round(h), QColor(c))

    def line(self, a, b, width, c):
        pen = QPen(QColor(c), width, Qt.SolidLine, Qt.SquareCap, Qt.MiterJoin)
        self.p.setPen(pen)
        self.p.drawLine(QPointF(*a), QPointF(*b))

    def disc(self, cx, cy, r, c):
        self.p.setPen(Qt.NoPen)
        self.p.setBrush(QColor(c))
        self.p.drawEllipse(QPointF(cx, cy), r, r)

    def poly(self, pts, c):
        self.p.setPen(Qt.NoPen)
        self.p.setBrush(QColor(c))
        self.p.drawPolygon(QPolygon([QPoint(round(x), round(y)) for x, y in pts]))


# --- the story ------------------------------------------------------------------------

# joints of the poses: hip, knee, foot, shoulder, elbow, hand, head; chair back top
RECLINE = dict(hip=(118, 76), knee=(102, 69), foot=(87, 62), shoulder=(125, 61),
               elbow=(119, 49), hand=(127, 49), head=(126, 52), back=(132, 47), face=-1)
SIT_LEFT = dict(hip=(118, 76), knee=(106, 76), foot=(105, 92), shoulder=(119, 61),
                elbow=(114, 69), hand=(108, 75), head=(119, 52), back=(124, 46), face=-1)
WORK = dict(hip=(117, 76), knee=(130, 76), foot=(131, 92), shoulder=(118, 61),
            elbow=(125, 69), hand=(140, 67), head=(119, 52), back=(111, 46), face=1)
LEAN = dict(hip=(117, 76), knee=(131, 75), foot=(133, 92), shoulder=(114, 61),
            elbow=(112, 50), hand=(119, 49), head=(115, 52), back=(108, 46), face=1)
STRETCH = dict(hip=(117, 76), knee=(130, 76), foot=(131, 92), shoulder=(118, 61),
               elbow=(121, 49), hand=(123, 38), head=(119, 52), back=(111, 46), face=1)


def _lerp_pose(a, b, k):
    k = _ease(k)
    out = {}
    for key in a:
        if key == "face":
            out[key] = a[key] if k < 0.5 else b[key]
        else:
            out[key] = (a[key][0] + (b[key][0] - a[key][0]) * k,
                        a[key][1] + (b[key][1] - a[key][1]) * k)
    return out


def _pose(t):
    """(pose, rocking angle in degrees, working 0..1, typing) at time t."""
    t %= LOOP
    rock = 2.2 * math.sin(t * 2.1)
    if t < 9.0:
        return RECLINE, rock, 0.0, False
    if t < 10.0:
        return _lerp_pose(RECLINE, SIT_LEFT, t - 9.0), rock * (10.0 - t), 0.0, False
    if t < 10.5:
        return dict(SIT_LEFT, face=0), 0.0, 0.0, False  # seen from behind, turning
    if t < 11.0:
        return _lerp_pose(dict(SIT_LEFT, face=1), WORK, (t - 10.5) * 2), 0.0, 0.1, False
    if t < 15.5:
        return WORK, 0.0, (t - 11.0) / 9.0, True
    if t < 16.3:
        return _lerp_pose(WORK, STRETCH, (t - 15.5) / 0.8), 0.0, 4.5 / 9.0, False
    if t < 17.1:
        return _lerp_pose(STRETCH, WORK, (t - 16.3) / 0.8), 0.0, 4.5 / 9.0, False
    if t < 19.6:
        return WORK, 0.0, (t - 12.6) / 9.0, True
    if t < 20.8:
        return _lerp_pose(WORK, LEAN, (t - 19.6) / 1.2), 0.0, 1.0, False
    if t < 22.0:
        return _lerp_pose(LEAN, dict(WORK, face=1), (t - 20.8) / 1.2), 0.0, 1.0, False
    if t < 22.5:
        return dict(SIT_LEFT, face=0), 0.0, 1.0, False
    if t < 23.5:
        return _lerp_pose(SIT_LEFT, RECLINE, t - 22.5), 0.0, 1.0, False
    return RECLINE, rock * min(1.0, t - 23.5), 1.0, False


# --- painting ---------------------------------------------------------------------------

def paint_room(image: QImage, t: float, sun: float) -> None:
    p = QPainter(image)
    p.setRenderHint(QPainter.Antialiasing, False)
    d = _Pix(p)
    pose, rock, work, typing = _pose(t)
    _room(d, sun)
    _outside(d, t, sun)
    _window(d, sun)
    _shelf(d)
    _floor_things(d)
    _chair_base(d)
    p.save()
    # rocking: the chair and the man turn a little about the feet on the sill
    if abs(rock) > 0.01:
        p.translate(87, 62)
        p.rotate(rock)
        p.translate(-87, -62)
    _chair_back(d, pose)
    _man(d, pose, t, typing, work)
    p.restore()
    _desk(d, t, work, typing)
    _light(d, sun)
    p.end()


def _room(d: _Pix, sun: float) -> None:
    d.rect(0, 0, W, H, _mix("#1f1a33", "#3a2c4c", sun))
    # wainscot and floor boards
    d.rect(0, 84, W, 2, _mix("#2a2240", "#4a3858", sun))
    floor = _mix("#2b2238", "#4b3a52", sun)
    d.rect(0, 86, W, H - 86, floor)
    seam = _mix("#241c30", "#3e2f45", sun)
    for y in (92, 100):
        d.rect(0, y, W, 1, seam)
    for i, y in enumerate((86, 92, 100)):
        for x in range(8 + i * 13, W, 34):
            d.rect(x, y, 1, 6 if y < 100 else 8, seam)


def _outside(d: _Pix, t: float, sun: float) -> None:
    x0, y0, w, h = 16, 14, 68, 50
    bands = len(SKY_NIGHT)
    for i in range(bands):
        c = _mix(SKY_NIGHT[i], SKY_DAWN[i], sun)
        d.rect(x0, y0 + i * h // bands, w, h // bands + 1, c)
    # stars fade with the dawn
    if sun < 0.7:
        star = _mix("#ffffff", SKY_DAWN[0], sun / 0.7)
        for sx, sy in ((22, 18), (35, 22), (51, 17), (68, 21), (77, 16), (29, 27), (60, 26)):
            if (int(t * 2 + sx) % 7) != 0:
                d.rect(sx, sy, 1, 1, star)
    # the sun rises from behind the hills
    sy = 66 - 34 * sun
    d.disc(44, sy, 9, _mix("#ff9a5a", "#ffe3a0", sun).lighter(105))
    d.disc(44, sy, 6.5, _mix("#ffb070", "#fff2c4", sun))
    # clouds drifting, lit from below
    for cx, cy, size in ((20 + (t * 1.5) % 90 - 10, 24, 1.0), (55 + (t * 0.9) % 90 - 40, 33, 0.8)):
        cx = x0 + (cx - x0) % (w + 20) - 10
        body = _mix("#3a3570", "#f7c6c0", sun)
        under = _mix("#4a3a78", "#f59a7e", sun)
        d.rect(cx, cy, 14 * size, 3, body)
        d.rect(cx + 3, cy - 2, 7 * size, 2, body)
        d.rect(cx + 1, cy + 3, 12 * size, 1, under)
    # hills and a town with lights going out
    far = _mix("#1d1a3a", "#5a4a86", sun)
    near = _mix("#151229", "#3a2f60", sun)
    d.poly([(x0, 54), (26, 48), (38, 51), (52, 45), (66, 50), (x0 + w, 47), (x0 + w, 64),
            (x0, 64)], far)
    d.poly([(x0, 58), (30, 55), (44, 58), (58, 54), (x0 + w, 57), (x0 + w, 64), (x0, 64)], near)
    town = _mix("#120f22", "#2c2448", sun)
    for bx, bw, bh in ((20, 5, 6), (26, 4, 9), (31, 6, 5), (61, 5, 8), (67, 4, 5), (72, 6, 10)):
        d.rect(bx, 64 - bh, bw, bh, town)
        if sun < 0.85:
            for wy in range(64 - bh + 2, 63, 3):
                if (bx + wy) % 3:
                    d.rect(bx + 1 + (wy % 2) * 2, wy, 1, 1, "#ffd27a")
    # a pair of birds now and then
    bt = (t % 13.0) / 13.0
    if bt < 0.6:
        bx = x0 + w - bt / 0.6 * (w + 10)
        flap = int(t * 6) % 2
        for k, (ox, oy) in enumerate(((0, 0), (6, 3))):
            if x0 <= bx + ox < x0 + w - 3:
                c = "#2a2140"
                d.rect(bx + ox, 30 + oy, 1, 1, c)
                d.rect(bx + ox - 1, 29 + oy - flap, 1, 1, c)
                d.rect(bx + ox + 1, 29 + oy - flap, 1, 1, c)


def _window(d: _Pix, sun: float) -> None:
    frame = _mix(WOOD_DARK, WOOD, sun)
    d.rect(12, 10, 76, 4, frame)
    d.rect(12, 10, 4, 56, frame)
    d.rect(84, 10, 4, 56, frame)
    d.rect(48, 14, 3, 50, frame)
    d.rect(16, 37, 68, 2, frame)
    # the sill the feet rest on
    d.rect(8, 64, 84, 3, _mix(WOOD, WOOD_LIGHT, sun))
    d.rect(8, 67, 84, 1, _mix("#3a2a26", WOOD_DARK, sun))
    # curtain on the left
    cur = _mix("#5a2a3a", "#b04a5a", sun)
    d.rect(4, 8, 8, 60, cur)
    d.rect(6, 8, 2, 60, _mix("#4a2230", "#903a4a", sun))
    d.rect(2, 7, 92, 2, "#2a2230")


def _floor_things(d: _Pix) -> None:
    """A stack of books and a rolled drawing under the window."""
    for i, (w, c) in enumerate(((16, "#2e86de"), (14, "#c0392b"), (15, "#f1c40f"),
                                (12, "#27ae60"))):
        y = 99 - i * 3
        d.rect(24 + (i % 2), y, w, 3, c)
        d.rect(24 + (i % 2), y, w, 1, QColor(c).lighter(125))
    d.line((46, 101), (62, 95), 3, "#e8e4d8")
    d.rect(61, 94, 2, 2, "#c8c4b8")


def _light(d: _Pix, sun: float) -> None:
    """The warm light falling through the window onto the floor."""
    if sun <= 0.05:
        return
    c = QColor(255, 196, 120, int(46 * sun))
    d.p.setPen(Qt.NoPen)
    d.p.setBrush(c)
    d.p.drawPolygon(QPolygon([QPoint(16, 64), QPoint(84, 64), QPoint(150, H), QPoint(70, H)]))


def _shelf(d: _Pix) -> None:
    d.rect(128, 30, 58, 2, WOOD)
    d.rect(130, 32, 2, 3, WOOD_DARK)
    d.rect(182, 32, 2, 3, WOOD_DARK)
    x = 131
    for w, h, c in ((3, 12, "#c0392b"), (4, 14, "#2e86de"), (3, 11, "#27ae60"), (5, 13, "#f39c12"),
                    (3, 12, "#8e44ad"), (4, 10, "#16a085"), (3, 14, "#d35400"), (4, 12, "#ecf0f1")):
        d.rect(x, 30 - h, w, h, c)
        d.rect(x, 30 - h + 2, w, 1, QColor(c).darker(130))
        x += w + 1
    # a leaning book and a little gear model
    d.poly([(171, 30), (174, 30), (180, 20), (177, 19)], "#e74c3c")
    d.disc(182, 25, 3.5, "#9aa4b0")
    d.disc(182, 25, 1.2, "#5a6470")
    # a drawing pinned to the wall
    d.rect(100, 18, 20, 14, "#e8e4d8")
    d.rect(103, 24, 14, 2, "#3a5a8a")
    d.rect(106, 21, 6, 8, "#3a5a8a")
    d.rect(102, 25, 16, 0.5, "#c04040")


def _chair_base(d: _Pix) -> None:
    d.rect(117, 79, 3, 11, "#2a2a32")
    d.rect(109, 90, 19, 2, "#24242c")
    for x in (109, 117, 126):
        d.rect(x, 92, 3, 2, "#111116")


def _chair_back(d: _Pix, pose) -> None:
    hx, hy = pose["hip"]
    seat_y = hy + 1
    d.rect(hx - 9, seat_y, 18, 3, CHAIR)
    d.rect(hx - 9, seat_y, 18, 1, CHAIR_ACCENT)
    if pose["face"] == 0:  # from behind: the back is drawn over the man (_man)
        return
    bx, by = pose["back"]
    base = (hx + 5 * pose["face"] * -1, hy + 1)
    d.line(base, (bx, by), 6, CHAIR)
    d.line((base[0] + pose["face"] * -2, base[1] - 4), (bx + pose["face"] * -2, by + 3), 1,
           CHAIR_ACCENT)
    d.rect(bx - 3, by - 3, 6, 4, CHAIR)  # headrest


def _man(d: _Pix, pose, t, typing, work) -> None:
    face = pose["face"]
    hip, knee, foot = pose["hip"], pose["knee"], pose["foot"]
    sh, el, hand, head = pose["shoulder"], pose["elbow"], pose["hand"], pose["head"]
    if face == 0:
        # from behind: shoulders past the chair's back, the back of the head
        d.rect(hip[0] - 9, hip[1] - 17, 18, 5, HOODIE)
        d.rect(hip[0] - 7, hip[1] - 30, 14, 31, CHAIR)
        d.rect(hip[0] - 5, hip[1] - 28, 10, 2, CHAIR_ACCENT)
        d.rect(hip[0] - 1, hip[1] - 26, 2, 24, CHAIR_ACCENT)
        d.disc(head[0], head[1], 5, HAIR)
        d.rect(head[0] - 6, head[1] - 1, 2, 4, "#222")  # headphones
        d.rect(head[0] + 4, head[1] - 1, 2, 4, "#222")
        d.rect(head[0] - 5, head[1] - 6, 10, 1, "#222")
        return
    if typing:
        jig = 1 if int(t * 9) % 2 else 0
        hand = (hand[0] + jig, hand[1] - (1 - jig))
    # far leg, body, near leg
    d.line(hip, knee, 5, PANTS)
    d.line(knee, foot, 4, PANTS)
    d.line((hip[0], hip[1] + 2), (knee[0], knee[1] + 2), 1, PANTS_SHADE)
    sole = (foot[0] - (4 if face < 0 else 0), foot[1] - 2)
    d.rect(sole[0], sole[1], 5, 3, SHOES)
    d.rect(sole[0], sole[1] + 2, 5, 1, "#b8b8c0")
    d.line(hip, sh, 6, HOODIE)
    d.line((hip[0] + face * 2, hip[1]), (sh[0] + face * 2, sh[1] + 2), 2, HOODIE_SHADE)
    # head: face towards ``face``, hair at the back, headphones
    hx, hy = head
    d.disc(hx, hy, 5, SKIN)
    d.disc(hx - face * 1.5, hy - 1.5, 4.5, HAIR)
    d.rect(hx - 4, hy - 6, 8, 2, HAIR)
    d.rect(hx + face * 3, hy - 1, 1, 1, "#1a1a1a")  # eye
    d.rect(hx + face * 4, hy + 2, 1, 1, SKIN_SHADE)  # mouth corner
    d.rect(hx - face * 2 - 1, hy - 2, 3, 4, "#222")  # headphone cup
    d.line((hx - 4, hy - 5), (hx + 3, hy - 6), 1, "#222")
    if work > 0 and face > 0 and typing:
        d.rect(hx + face * 4, hy - 1, 1, 3, "#7fd3ff")  # the screen's glow on the face
    # the near arm
    d.line(sh, el, 3, HOODIE)
    d.line(el, hand, 3, HOODIE)
    d.rect(hand[0] - 1, hand[1] - 1, 3, 3, SKIN)


def _desk(d: _Pix, t, work, typing) -> None:
    top = 70
    d.rect(128, top, 60, 3, WOOD)
    d.rect(128, top, 60, 1, WOOD_LIGHT)
    d.rect(130, top + 3, 3, 22, WOOD_DARK)
    d.rect(183, top + 3, 3, 22, WOOD_DARK)
    d.rect(160, top + 3, 23, 12, WOOD)
    d.rect(170, top + 8, 4, 1, WOOD_LIGHT)
    # monitor
    d.rect(146, 44, 36, 23, "#15151c")
    d.rect(162, 67, 4, 3, "#2a2a32")
    d.rect(156, 69, 16, 1, "#2a2a32")
    _screen(d, t, work)
    # keyboard and mouse
    d.rect(140, 68, 18, 2, "#3a3a44")
    d.rect(141, 68, 16, 1, "#5a5a66")
    d.rect(160, 68, 3, 2, "#3a3a44")
    # a mug with steam    d.rect(178, 64, 6, 6, "#e8e4d8")
    d.rect(184, 66, 2, 2, "#e8e4d8")
    for k in range(3):
        phase = (t * 0.8 + k * 0.33) % 1.0
        sx = 180 + round(math.sin((t + k) * 3) * 1)
        d.rect(sx, 62 - phase * 8, 1, 1, QColor(230, 230, 240, int(160 * (1 - phase))))
    # a desk lamp
    d.line((186, top), (182, 52), 1, "#9aa4b0")
    d.rect(176, 50, 8, 3, "#9aa4b0")


def _screen(d: _Pix, t, work) -> None:
    x0, y0, w, h = 148, 46, 32, 19
    d.rect(x0, y0, w, h, "#0d2236")
    if work <= 0:
        # screensaver: the logo drifting
        lx = x0 + 4 + (t * 3) % (w - 10)
        ly = y0 + 4 + abs(math.sin(t * 0.7)) * (h - 10)
        d.disc(lx + 2, ly + 2, 2.5, "#2a4a6a")
        return
    # a part being drawn: its outline grows with the work, the axis first
    d.rect(x0 + 1, y0 + 9, w - 2, 1, "#c0703a")
    outline = [(2, 6), (8, 6), (8, 4), (14, 4), (14, 2), (20, 2), (20, 5), (28, 5), (28, 9),
               (28, 13), (20, 13), (20, 16), (14, 16), (14, 14), (8, 14), (8, 12), (2, 12),
               (2, 6)]
    total = len(outline) - 1
    done = min(work * 1.15, 1.0) * total
    pen = QPen(QColor("#7fd3ff"), 1)
    d.p.setPen(pen)
    for i in range(int(done)):
        (ax, ay), (bx, by) = outline[i], outline[i + 1]
        d.p.drawLine(x0 + ax, y0 + ay, x0 + bx, y0 + by)
    i = int(done)
    if i < total:
        (ax, ay), (bx, by) = outline[i], outline[i + 1]
        k = done - i
        d.p.drawLine(QPointF(x0 + ax, y0 + ay),
                     QPointF(x0 + ax + (bx - ax) * k, y0 + ay + (by - ay) * k))
        if int(t * 4) % 2:
            d.rect(x0 + ax + (bx - ax) * k, y0 + ay + (by - ay) * k, 1, 1, "#ffffff")
    if work > 0.85:
        d.rect(x0 + 2, y0 + 1, 26, 1, "#5fd38a")  # a dimension line over it
