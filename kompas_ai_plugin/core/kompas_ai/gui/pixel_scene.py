"""The waiting screen: a pixel-art room at dawn, 384 × 216 pixels.

All from the concept picture and its edited versions (assets/, made by
prototype/room_assets.py): the room without the man, and the man with his
chair in five poses — feet on the window sill (the concept), sitting by the
window with a cup, working at the computer (twice), stretching. He holds a
pose and fades into the next: a 20-second story whose last frame is its
first. The room is the same in every pose, so only he changes.

Quiet movements over the still room: the windows of the city flicker, the
sun's path on the water shimmers, the screen glows, its cursor blinks, the
keyboard breathes, the tower's lights blink, steam rises from the mug.
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
        got = {"room_bg": QImage(str(d / "room_bg.png")).convertToFormat(QImage.Format_ARGB32)}
        if got["room_bg"].isNull():
            raise RuntimeError("нет картинки комнаты")
        got["lights"] = _city_lights(got["room_bg"])
        layers = {}
        for name in POSES:
            path = d / ("room_man.png" if name == "man" else f"pose_{name}.png")
            # the image stays referenced while its pixels are copied: a view
            # into a freed temporary read garbage (noise over the scene)
            img = QImage(str(path)).convertToFormat(QImage.Format_ARGB32)
            if img.isNull() or (img.width(), img.height()) != (W, H):
                raise RuntimeError(f"нет картинки {path.name}")
            v = np.array(_view(img), dtype=np.float32, copy=True)
            del img
            v[:, :, 3] /= 255.0
            layers[name] = v  # BGR and the share of the pose, 0 or 1
        got["layers"] = layers
        _A.update(got)  # all or nothing
    return _A


def _view(img: QImage) -> np.ndarray:
    """The pixels of ``img`` as a writable array (BGRA) — valid only while
    ``img`` lives: copy it to keep it."""
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


# --- the man and his poses ---------------------------------------------------------------

# (pose, start, end): he holds a pose, then fades into the next one
STORY = [("man", 0.0, 4.5), ("sit", 5.2, 7.5), ("work1", 8.2, 10.0), ("work2", 10.4, 12.0),
         ("work1", 12.4, 13.6), ("stretch", 14.3, 16.0), ("sit", 16.7, 17.6), ("man", 18.4, 20.0)]
POSES = ("man", "sit", "work1", "work2", "stretch")


def story(t: float) -> tuple[str, str, float]:
    """(this pose, the next one, how far the fade into it has gone)."""
    t %= LOOP
    for (a, _, end), (b, start, _) in zip(STORY, STORY[1:]):
        if t < end:
            return a, a, 0.0
        if t < start:
            k = (t - end) / (start - end)
            return a, b, k * k * (3 - 2 * k)
    return STORY[-1][0], STORY[-1][0], 0.0


def paint(img: QImage, t: float) -> None:
    """Frame at ``t`` seconds onto ``img`` (W × H, ARGB32)."""
    a = _assets()
    t %= LOOP
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, False)
    p.setRenderHint(QPainter.SmoothPixmapTransform, False)
    p.drawImage(0, 0, a["room_bg"])
    _ambient(p, a, t)
    p.end()
    now, nxt, k = story(t)
    out = _view(img)
    la, lb = a["layers"][now], a["layers"][nxt]
    if now == nxt:
        wa, wb = la[:, :, 3:4], 0.0
    else:  # fading: his old pose gives way to the room and the new one
        wa, wb = la[:, :, 3:4] * (1.0 - k), lb[:, :, 3:4] * k
    mix = out[:, :, :3] * (1.0 - wa - wb) + la[:, :, :3] * wa + lb[:, :, :3] * wb
    out[:, :, :3] = mix.astype(np.uint8)


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
