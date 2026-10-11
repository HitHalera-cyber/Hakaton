"""The waiting screen: a pixel-art room at dawn, 384 × 216 pixels.

The room and the man resting with his feet on the window sill are the
concept picture (assets/, made by prototype/room_assets.py): the room
without him, and him with his chair cut out. He only breathes: his head and
shoulders rise a pixel and settle, slowly (moving parts of a cut-out apart
by single pixels looked like a glitch).

Quiet movements over the still room: the windows of the city flicker, the
sun's path on the water shimmers, the screen glows, its cursor blinks, the
keyboard breathes, the tower's lights blink, steam rises from the mug.
LOOP seconds, the last frame being the first.
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

SCREEN = QRect(0, 71, 42, 38)
KEYS = QRect(18, 114, 40, 8)
TOWER = QRect(64, 85, 7, 24)
WATER = QRect(137, 104, 194, 21)
SUN_PATH = QRect(252, 104, 30, 21)


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


# --- the man ---------------------------

BREATH = 4.0  # seconds of one breath
LEGS_X, UPPER_Y = 158, 118  # his head and shoulders: left of LEGS_X, above UPPER_Y


def _parts(man: QImage) -> dict:
    """The part of the cut-out that breathes: head and shoulders."""
    ys, xs = np.mgrid[0:H, 0:W]
    img = man.copy()
    _view(img)[~((ys < UPPER_Y) & (xs < LEGS_X)), 3] = 0
    return {"upper": img}


def paint(img: QImage, t: float) -> None:
    """Frame at ``t`` seconds onto ``img`` (W × H, ARGB32)."""
    a = _assets()
    t %= LOOP
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, False)
    p.setRenderHint(QPainter.SmoothPixmapTransform, False)
    p.drawImage(0, 0, a["room_bg"])
    _ambient(p, a, t)
    p.drawImage(0, 0, a["room_man"])
    # he breathes: head and shoulders rise a pixel, slowly, and settle
    if (t % BREATH) < BREATH * 0.45:
        p.drawImage(0, -1, a["parts"]["upper"])
    p.end()


def _ambient(p: QPainter, a: dict, t: float) -> None:
    bg = a["room_bg"]
    # the city's windows go on and off
    for x, y, phase, dark in a["lights"]:
        if math.sin(2 * math.pi * (t / LOOP * 3 + phase)) > 0.55:
            p.fillRect(x, y, 1, 1, dark)
    # the sun's path shimmers: every other row of it moves a pixel, slowly
    for y in range(WATER.top() + 1, WATER.bottom() + 1, 2):
        dx = 1 if (int(t * 1.5) + y // 2) % 2 else -1
        row = QRect(SUN_PATH.left(), y, SUN_PATH.width(), 1)
        p.save()
        p.setClipRect(row)
        p.drawImage(row.translated(dx, 0), bg, row)
        p.restore()
    # the screen flickers a little, the cursor blinks
    p.fillRect(SCREEN, QColor(120, 150, 255, 8 + round(6 * (1 + math.sin(2 * math.pi * t / 1.6)))))
    if int(t * 2) % 2:
        p.fillRect(30, 96, 3, 1, QColor("#c8d0ff"))
    # the keyboard breathes, the tower's lights blink
    p.fillRect(KEYS, QColor(170, 80, 255, 25 + round(20 * (1 + math.sin(2 * math.pi * t / 2.5)))))
    for k, y in enumerate(range(TOWER.top() + 3, TOWER.bottom(), 5)):
        if (int(t * 2) + k) % 3 == 0:
            p.fillRect(TOWER.left() + 2, y, 3, 2, QColor("#0a0a30"))
    # steam from the mug
    for k in range(4):
        ph = (t / 1.25 + k / 4) % 1.0
        sx = 66 + k % 2 * 3 + round(math.sin((ph + k) * 6) * 1.5)
        p.fillRect(sx, round(106 - ph * 14), 1, 1, QColor(200, 200, 240, int(150 * (1 - ph))))
