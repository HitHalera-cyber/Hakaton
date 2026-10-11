"""Waiting screen while a drawing is read: a compass draws a circle, the centre
lines and a diameter dimension follow; next to it the real stages of the
recognition tick off one by one, with the time spent."""

from __future__ import annotations

import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

CYCLE = 4.2  # seconds for one circle, its centre lines and its dimension


class DraftingLoader(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.colors: dict[str, str] = {}
        self.stages: list[str] = []
        self.current = -1
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

    def _c(self, key: str, alpha: int = 255) -> QColor:
        c = QColor(self.colors.get(key, "#888888"))
        c.setAlpha(alpha)
        return c

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), self._c("sheet"))
        w, h = self.width(), self.height()
        p.setPen(QPen(self._c("grid"), 1))
        for x in range(0, w, 20):
            p.drawLine(x, 0, x, h)
        for y in range(0, h, 20):
            p.drawLine(0, y, w, y)
        r = min(h * 0.24, w * 0.15)
        self._drawing(p, QPointF(w * 0.3, h * 0.5 + r * 0.15), r)
        self._stages(p, QRectF(w * 0.56, h * 0.5 - 130, w * 0.42, 300))
        p.end()

    def _drawing(self, p: QPainter, c: QPointF, r: float) -> None:
        t = ((time.monotonic() - self.started) % CYCLE) / CYCLE
        line = self._c("text")
        accent = self._c("select")
        axis = self._c("warn")

        # the circle so far, from the top clockwise as a hand would draw it
        sweep = min(t / 0.6, 1.0) * 360.0
        start = 90.0
        rect = QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r)
        p.setPen(QPen(line, 2.6, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        p.drawArc(rect, int(start * 16), int(-sweep * 16))

        # centre lines grow out of the centre
        if t > 0.6:
            k = min((t - 0.6) / 0.2, 1.0)
            reach = (r + 18) * k
            pen = QPen(axis, 1.2)
            pen.setDashPattern([14, 4, 2, 4])
            p.setPen(pen)
            p.drawLine(QPointF(c.x() - reach, c.y()), QPointF(c.x() + reach, c.y()))
            p.drawLine(QPointF(c.x(), c.y() - reach), QPointF(c.x(), c.y() + reach))

        # the diameter: extension lines, the dimension line with arrows, the value
        if t > 0.8:
            k = min((t - 0.8) / 0.12, 1.0)
            y = c.y() + r + 34
            p.setPen(QPen(accent, 1.2))
            for x in (c.x() - r, c.x() + r):
                p.drawLine(QPointF(x, c.y() + 6), QPointF(x, c.y() + (r + 40) * k + 6 * (1 - k)))
            if k >= 1.0:
                p.drawLine(QPointF(c.x() - r, y), QPointF(c.x() + r, y))
                for x, d in ((c.x() - r, 1), (c.x() + r, -1)):
                    p.setBrush(accent)
                    p.drawPolygon(QPolygonF([QPointF(x, y), QPointF(x + d * 12, y - 3.5),
                                             QPointF(x + d * 12, y + 3.5)]))
                p.setBrush(Qt.NoBrush)
                font = QFont(self.font())
                font.setPointSizeF(13)
                font.setItalic(True)
                p.setFont(font)
                p.drawText(QRectF(c.x() - 60, y - 26, 120, 22), Qt.AlignCenter, "Ø40")

        # the compass seen from the front: the hinge above the centre, the
        # needle leg in the centre, the pencil leg on the circle, a knob on top
        if t <= 0.6:
            a = math.radians(start - sweep)
            tip = QPointF(c.x() + r * math.cos(a), c.y() - r * math.sin(a))
            hinge = QPointF((c.x() + tip.x()) / 2, c.y() - r * 1.35 + (tip.y() - c.y()) * 0.25)
            legs = self._c("muted")
            p.setPen(QPen(legs, 6, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(hinge, QPointF(c.x(), c.y() - 10))
            p.drawLine(hinge, QPointF(tip.x() + (hinge.x() - tip.x()) * 0.12,
                                      tip.y() + (hinge.y() - tip.y()) * 0.12))
            # the needle and the pencil lead
            p.setPen(QPen(line, 2, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(c.x(), c.y() - 10), c)
            p.setPen(QPen(accent, 3, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(tip.x() + (hinge.x() - tip.x()) * 0.12,
                               tip.y() + (hinge.y() - tip.y()) * 0.12), tip)
            # hinge and knob
            p.setPen(QPen(line, 2))
            p.setBrush(self._c("card"))
            p.drawEllipse(hinge, 8, 8)
            p.setPen(QPen(line, 5, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(hinge.x(), hinge.y() - 9), QPointF(hinge.x(), hinge.y() - 26))

    def _stages(self, p: QPainter, box: QRectF) -> None:
        font = QFont(self.font())
        font.setPointSizeF(15)
        font.setBold(True)
        p.setFont(font)
        p.setPen(self._c("text"))
        p.drawText(QRectF(box.x(), box.y() - 46, box.width(), 30),
                   Qt.AlignLeft | Qt.AlignVCenter, self.title)
        font.setBold(False)
        font.setPointSizeF(12)
        p.setFont(font)
        row = 30
        for i, name in enumerate(self.stages):
            y = box.y() + i * row
            done, now = i < self.current, i == self.current
            mark = QRectF(box.x(), y + 7, 16, 16)
            if done:
                p.setPen(Qt.NoPen)
                p.setBrush(self._c("ok"))
                p.drawEllipse(mark)
                p.setPen(QPen(self._c("card"), 2, Qt.SolidLine, Qt.RoundCap))
                tick = QPainterPath(QPointF(mark.x() + 4, mark.y() + 8.5))
                tick.lineTo(mark.x() + 7, mark.y() + 11.5)
                tick.lineTo(mark.x() + 12, mark.y() + 5)
                p.setBrush(Qt.NoBrush)
                p.drawPath(tick)
            elif now:
                p.setPen(QPen(self._c("select"), 2))
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(mark)
                spin = (time.monotonic() * 360) % 360
                p.drawArc(mark.adjusted(-3, -3, 3, 3), int(spin * 16), 90 * 16)
            else:
                p.setPen(QPen(self._c("border"), 1.5))
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(mark)
            p.setPen(self._c("text" if now else ("muted" if not done else "text"),
                             255 if (now or done) else 170))
            p.drawText(QRectF(box.x() + 28, y, box.width() - 28, row),
                       Qt.AlignLeft | Qt.AlignVCenter, name)
        p.setPen(self._c("muted"))
        elapsed = time.monotonic() - self.started
        p.drawText(QRectF(box.x(), box.y() + len(self.stages) * row + 12, box.width(), 24),
                   Qt.AlignLeft | Qt.AlignVCenter, f"Идёт работа · {elapsed:.0f} с")
