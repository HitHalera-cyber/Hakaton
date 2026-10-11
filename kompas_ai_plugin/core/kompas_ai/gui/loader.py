"""Waiting screen while a drawing is read: a pixel-art room
at dawn (pixel_scene.py), under it a line with
the real stage of the recognition, a block per stage and the time spent."""

from __future__ import annotations

import time

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtWidgets import QWidget

from .pixel_scene import H, W, paint


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
        self.timer.setInterval(50)
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
        scene = QImage(W, H, QImage.Format_ARGB32)
        paint(scene, now)
        # the scene alone, as large as fits above a line of status
        k = min(w / W, (h - 64) / H)
        if k >= 1:
            k = int(k)  # whole pixels where it fits
        sw, sh = int(W * k), int(H * k)
        x, y = (w - sw) // 2, max(0, (h - 64 - sh) // 2)
        p.fillRect(self.rect(), QColor("#0b0a1a"))
        p.setRenderHint(QPainter.SmoothPixmapTransform, False)
        p.drawImage(QRectF(x, y, sw, sh), scene)
        self._hud(p, QRectF(x, y + sh + 10, sw, 48), now)
        p.end()

    def _hud(self, p: QPainter, box: QRectF, now: float) -> None:
        """Under the scene: the file, the stage, a block per stage, the time."""
        font = QFont("Consolas")
        font.setStyleHint(QFont.Monospace)
        font.setPointSizeF(10.5)
        p.setFont(font)
        stage = self.stages[self.current] if 0 <= self.current < len(self.stages) else "Начинаю"
        dots = "." * (int(now * 3) % 4)
        p.setPen(QColor("#ffcc6e"))
        p.drawText(QRectF(box.x(), box.y(), box.width(), 18), Qt.AlignLeft | Qt.AlignVCenter,
                   f"{self.title} · {stage}{dots}")
        p.setPen(QColor("#8a84b0"))
        p.drawText(QRectF(box.x(), box.y(), box.width(), 18), Qt.AlignRight | Qt.AlignVCenter,
                   f"{now:.0f} с")
        n = max(len(self.stages), 1)
        bw = (box.width() - (n - 1) * 3) / n
        for i in range(n):
            r = QRectF(box.x() + i * (bw + 3), box.y() + 24, bw, 6)
            if i < self.current:
                c = QColor("#ff8a52")
            elif i == self.current:
                c = QColor("#ffcc6e") if int(now * 4) % 2 else QColor("#a0603a")
            else:
                c = QColor("#25204c")
            p.fillRect(r, c)
