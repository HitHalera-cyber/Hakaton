"""Waiting screen while a drawing is read: a pixel-art room at dawn
(pixel_scene.py) framed like the other cards of the window, under it the
file, the real stage of the recognition, the time spent and a thin bar."""

from __future__ import annotations

import time

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QPushButton, QWidget

from .pixel_scene import H, W, paint

STATUS = 90  # px under the scene: the file, the stage, the bar, «Отменить»


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
        # stops the reading: the work gives up at its next stage
        self.cancel_button = QPushButton("Отменить", self, objectName="secondary")
        self.cancel_button.setCursor(Qt.PointingHandCursor)
        self.cancel_button.hide()
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
        self.cancel_button.setText("Отменить")
        self.cancel_button.setEnabled(True)
        self.cancel_button.show()
        self._place_button()
        self.raise_()
        self.show()
        self.timer.start()

    def stage(self, name: str) -> None:
        if name in self.stages:
            self.current = self.stages.index(name)
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place_button()

    def _geometry(self):
        """(scene frame x, y, width, height) for the widget's size."""
        w, h = self.width(), self.height()
        pad, status = 16, STATUS
        k = min((w - 2 * pad) / W, (h - 2 * pad - status) / H)
        if k >= 3:
            k = int(k)
        sw, sh = int(W * k), int(H * k)
        return (w - sw) // 2, max(pad, (h - status - sh) // 2), sw, sh

    def _place_button(self) -> None:
        x, y, sw, sh = self._geometry()
        self.cancel_button.setGeometry(x + sw - 120, y + sh + 48, 120, 34)

    def stop(self) -> None:
        self.timer.stop()
        self.hide()

    # --- drawing ------------------------------------------------------------------------

    def _col(self, key: str, fallback: str) -> QColor:
        return QColor(self.colors.get(key, fallback))

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        now = time.monotonic() - self.started
        # the card itself, as every card of the window
        p.setPen(QPen(self._col("border", "#303338"), 1))
        p.setBrush(self._col("card", "#232528"))
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 18, 18)
        # the scene: as large as fits above the status, whole pixels when large
        x, y, sw, sh = self._geometry()
        frame = QRectF(x, y, sw, sh)
        scene = QImage(W, H, QImage.Format_ARGB32)
        scene.fill(self._col("card_alt", "#2B2E33"))
        try:
            paint(scene, now)
        except Exception:  # the waiting screen never stops the work
            pass
        clip = QPainterPath()
        clip.addRoundedRect(frame, 12, 12)
        p.save()
        p.setClipPath(clip)
        p.setRenderHint(QPainter.SmoothPixmapTransform, False)
        p.drawImage(frame, scene)
        p.restore()
        p.setPen(QPen(self._col("border", "#303338"), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(frame.adjusted(0.5, 0.5, -0.5, -0.5), 12, 12)
        self._status(p, QRectF(x, y + sh + 12, sw, 34), now)
        p.end()

    def _status(self, p: QPainter, box: QRectF, now: float) -> None:
        """Under the scene: the file and the stage, the time, a thin bar."""
        n = max(len(self.stages), 1)
        target = (self.current + 0.5) / n if self.current >= 0 else 0.0
        self.sun += (target - self.sun) * 0.15  # the bar moves on smoothly
        font = QFont(self.font())
        font.setPixelSize(13)
        font.setBold(True)
        p.setFont(font)
        p.setPen(self._col("text", "#E3E5E8"))
        stage = self.stages[self.current] if 0 <= self.current < len(self.stages) else "Начинаю"
        metrics = p.fontMetrics()
        title = metrics.elidedText(self.title, Qt.ElideMiddle, int(box.width() * 0.5))
        p.drawText(QRectF(box.x(), box.y(), box.width(), 18), Qt.AlignLeft | Qt.AlignVCenter, title)
        shift = metrics.horizontalAdvance(title) + 12
        font.setBold(False)
        p.setFont(font)
        p.setPen(self._col("muted", "#8C9199"))
        p.drawText(QRectF(box.x() + shift, box.y(), box.width() - shift - 60, 18),
                   Qt.AlignLeft | Qt.AlignVCenter, stage + "…")
        p.drawText(QRectF(box.x(), box.y(), box.width(), 18), Qt.AlignRight | Qt.AlignVCenter,
                   f"{now:.0f} с")
        track = QRectF(box.x(), box.y() + 26, box.width(), 4)
        p.setPen(Qt.NoPen)
        p.setBrush(self._col("card_alt", "#2B2E33"))
        p.drawRoundedRect(track, 2, 2)
        p.setBrush(self._col("select", "#6FB1EE"))
        p.drawRoundedRect(QRectF(track.x(), track.y(), max(4.0, track.width() * self.sun), 4), 2, 2)
