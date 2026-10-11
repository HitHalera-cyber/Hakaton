"""The waiting screen: a pixel-art room at dawn, 384 × 216 pixels.

The room and the man resting with his feet on the window sill are the
concept picture (assets/, made by prototype/room_assets.py): the room
without him, and him with his chair cut out. He lives the way pixel art
idles: by whole pixels. His body and the chair's back rock a pixel to and
fro, his head follows a moment later, his feet stay on the sill and the
chair's base on the floor; the parts overlap, so no seam opens between them.

Small movements over the still room: the clouds drift, the windows of the
city flicker, the water ripples, the screen flickers, the tower's lights
blink, the keyboard glows, steam rises from the mug. LOOP seconds, the last
frame being the first.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QImage, QPainter

W, H = 384, 216
LOOP = 20.0

BASE_Y = 170  # below it the chair's base
SCREEN = QRect(0, 71, 42, 38)
KEYS = QRect(18, 114, 40, 8)
TOWER = QRect(64, 85, 7, 24)
SKY = QRect(137, 12, 194, 50)  # the clouds over the city
WATER = QRect(137, 104, 194, 21)


def _asset_dir() -> Path:
    here = Path(__file__).resolve().parent / "assets"
    if here.is_dir():
        return here
    return Path(getattr(sys, "_MEIPASS", "")) / "kompas_ai" / "gui" / "assets"


_A: dict = {}


def _assets() -> dict:
    if not _A:
        d = _asset_dir()
        got = {name: QImage(str(d / f"{name}.png")).convertToFormat(QImage.Format_ARGB32)
               for name in ("room_bg", "room_man")}
        got["lights"] = _city_lights(got["room_bg"])
        got["parts"] = _parts(got["room_man"])
        _A.update(got)  # all or nothing
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


# --- the man: parts of the cut-out that move by whole pixels ---------------------------

ROCK = 5.0  # seconds of one rock to and fro
LEGS_X, HEAD_Y = 158, 101  # right of LEGS_X (above the seat) his legs, above HEAD_Y his head


def _parts(man: QImage) -> dict:
    """The cut-out split: legs (stay on the sill), base (stays on the floor),
    head, and the rest (body and the chair's back)."""
    ys, xs = np.mgrid[0:H, 0:W]
    legs = (xs >= LEGS_X) & (ys < 150)
    base = ys >= BASE_Y
    head = (ys < HEAD_Y) & (xs < 145)
    out = {}
    for name, keep in (("legs", legs), ("base", base), ("head", head),
                       ("body", ~legs & ~base & ~head)):
        img = man.copy()
        _view(img)[~keep, 3] = 0
        out[name] = img
    return out


def _offsets(t: float):
    """(body dx, body dy, head dx, head dy) in whole pixels."""
    ph = 2 * math.pi * t / ROCK
    body = math.sin(ph)
    head = math.sin(ph - 0.9)  # the head follows the body a moment later
    breath = math.sin(2 * math.pi * t / 4.0)
    return (round(body * 1.0), 1 if breath > 0.6 else 0,
            round(head * 1.4), 1 if breath > 0.6 else 0)


def paint(img: QImage, t: float) -> None:
    """Frame at ``t`` seconds onto ``img`` (W × H, ARGB32)."""
    a = _assets()
    t %= LOOP
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, False)
    p.setRenderHint(QPainter.SmoothPixmapTransform, False)
    p.drawImage(0, 0, a["room_bg"])
    _ambient(p, a, t, mug_on_desk=True)
    parts = a["parts"]
    bx, by, hx, hy = _offsets(t)
    p.drawImage(0, 0, parts["base"])
    # each moving part is laid also where it was, so no gap opens behind it
    p.drawImage(0, 0, parts["body"])
    p.drawImage(bx, by, parts["body"])
    p.drawImage(0, 0, parts["legs"])
    if bx < 0:  # the body leans away from the legs: the thigh follows a pixel
        p.drawImage(bx, 0, parts["legs"])
        p.drawImage(0, 0, parts["legs"])
    p.drawImage(bx, by, parts["head"])
    p.drawImage(hx, hy, parts["head"])
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
