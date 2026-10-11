"""Waiting screen while a drawing is read: a pixel-art room (pixel_room.py)
where the sun rises as the recognition goes on, and a game-like plate with
the real stage of the recognition, a block bar and the time spent."""

from __future__ import annotations

import time

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .pixel_room import H, W, paint_room


class DraftingLoader(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.colors: dict[str, str] = {}
        self.stages: list[str] = []
        self.current = -1
        self.sun = 0.0
        self.title = ""
        self.started = time.monotonic()
        self.timer = QTimer(self)
        self.timer.setInterval(30)
        self.timer.timeout.connect(self.update)
        self.hide()

    def set_colors(self, colors: dict[str, str]) -> None:
        self.colors = colors
        self.update()

    def start(self, title: str, stages: list[str]) -> None:
        self.title, self.stages, self.current = title, list(stages), -1
        self.sun = 0.0
        self.started = time.monotonic()
        if self.parentWidget() is not None:
            self.setGeometry(self.parentWidget().rect())
        self.raise_()
        self.show()
        self.timer.start()

    def stage(self, name: str) -> None:
        if name in self.stages:
            self.current = self.stages.index(name)
        self.update()

    def stop(self) -> None:
        self.timer.stop()
        self.hide()

    # --- drawing ------------------------------------------------------------------------

    def paintEvent(self, _event):
        p = QPainter(self)
        w, h = self.width(), self.height()
        now = time.monotonic() - self.started
        # the sun follows the recognition, smoothly
        target = (self.current + 0.5) / max(len(self.stages), 1) if self.current >= 0 else 0.0
        self.sun += (target - self.sun) * 0.04
        scene = QImage(W, H, QImage.Format_RGB32)
        paint_room(scene, now, self.sun)
        # whole pixels: the scene scaled by an integer where it fits
        k = max(1, min(w // W, h // H)) if min(w // W, h // H) >= 1 else min(w / W, h / H)
        sw, sh = int(W * k), int(H * k)
        x, y = (w - sw) // 2, (h - sh) // 2
        p.fillRect(self.rect(), QColor("#17131f"))
        p.setRenderHint(QPainter.SmoothPixmapTransform, False)
        p.drawImage(QRectF(x, y, sw, sh), scene)
        self._hud(p, QRectF(x, y, sw, sh), now)
        p.end()

    def _hud(self, p: QPainter, scene: QRectF, now: float) -> None:
        """A game-like plate at the bottom: the file, the stage, a block bar."""
        p.setRenderHint(QPainter.Antialiasing, False)
        box = QRectF(scene.x() + 16, scene.bottom() - 84, min(scene.width() - 32, 520), 68)
        p.fillRect(box, QColor(14, 12, 24, 215))
        p.setPen(QPen(QColor("#e8e4d8"), 2))
        p.setBrush(Qt.NoBrush)
        p.drawRect(box.adjusted(3, 3, -3, -3))
        font = QFont("Consolas")
        font.setStyleHint(QFont.Monospace)
        font.setPointSizeF(11)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor("#ffd88a"))
        stage = self.stages[self.current] if 0 <= self.current < len(self.stages) else "Начинаю"
        dots = "." * (int(now * 3) % 4)
        p.drawText(QRectF(box.x() + 14, box.y() + 8, box.width() - 28, 22),
                   Qt.AlignLeft | Qt.AlignVCenter, f"{self.title}")
        p.setPen(QColor("#e8e4d8"))
        font.setBold(False)
        p.setFont(font)
        p.drawText(QRectF(box.x() + 14, box.y() + 28, box.width() - 110, 20),
                   Qt.AlignLeft | Qt.AlignVCenter, f"{stage}{dots}")
        p.setPen(QColor("#9a94b0"))
        p.drawText(QRectF(box.right() - 100, box.y() + 28, 86, 20),
                   Qt.AlignRight | Qt.AlignVCenter, f"{now:.0f} с")
        # the bar: one block per stage, the current one blinking
        n = max(len(self.stages), 1)
        bw = (box.width() - 28 - (n - 1) * 3) / n
        for i in range(n):
            r = QRectF(box.x() + 14 + i * (bw + 3), box.y() + 51, bw, 7)
            if i < self.current:
                c = QColor("#5fd38a")
            elif i == self.current:
                c = QColor("#ffd88a") if int(now * 4) % 2 else QColor("#b8964a")
            else:
                c = QColor("#3a3450")
            p.fillRect(r, c)
