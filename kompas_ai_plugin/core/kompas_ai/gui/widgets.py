"""Pieces of the window every layout uses: the sheet preview, cards, chips,
a ring of a share, buttons that follow an action."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QFrame, QGraphicsEllipseItem, QGraphicsScene, QGraphicsView,
                               QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget)

from .theme import THEMES

GRID = 20  # px between grid lines behind the drawing


class PreviewView(QGraphicsView):
    """Zoomable, draggable preview of the source drawing with the recognised objects."""

    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setFrameShape(QFrame.NoFrame)
        self.marker: QGraphicsEllipseItem | None = None
        self.png: bytes | None = None
        self.marks: list = []  # (x, y, number) of broken rules, in preview pixels
        self.colors = THEMES["light"]

    def set_colors(self, colors: dict[str, str]) -> None:
        self.colors = colors
        self.setBackgroundBrush(QBrush(QColor(colors["sheet"])))
        if self.png is not None:
            self.show_png(self.png, keep_view=True)
        self.viewport().update()

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        painter.save()
        painter.resetTransform()
        painter.setPen(QPen(QColor(self.colors["grid"]), 1))
        area = self.viewport().rect()
        for x in range(0, area.width(), GRID):
            painter.drawLine(x, 0, x, area.height())
        for y in range(0, area.height(), GRID):
            painter.drawLine(0, y, area.width(), y)
        painter.restore()

    def show_png(self, png: bytes, keep_view: bool = False) -> None:
        self.png = png
        image = QImage.fromData(png, "PNG").convertToFormat(QImage.Format_ARGB32)
        if QColor(self.colors["sheet"]).lightness() < 128:
            image = _night(image, QColor(self.colors["sheet"]))
        transform = self.transform()
        center = self.mapToScene(self.viewport().rect().center())
        self.scene().clear()
        self.marker = None
        pix = QPixmap.fromImage(image)
        self.scene().addPixmap(pix)
        self.scene().setSceneRect(pix.rect())
        self._draw_marks()
        if keep_view:
            self.setTransform(transform)
            self.centerOn(center)
        else:
            self.fit()

    def set_marks(self, marks) -> None:
        """Rings with numbers where the contour breaks its rules."""
        self.marks = list(marks)
        if self.png is not None:
            self.show_png(self.png, keep_view=True)

    def _draw_marks(self) -> None:
        from PySide6.QtGui import QFont

        red = QColor("#E5484D")
        pen = QPen(red, 3)
        pen.setCosmetic(True)  # as thick at any zoom
        font = QFont()
        font.setPixelSize(16)
        font.setBold(True)
        for x, y, number in self.marks:
            r = 14
            ring = self.scene().addEllipse(x - r, y - r, 2 * r, 2 * r, pen, QBrush(Qt.NoBrush))
            ring.setZValue(5)
            ring.setToolTip(f"Нарушение {number} — подробности на странице «Проверка»")
            label = self.scene().addSimpleText(str(number), font)
            label.setBrush(QBrush(red))
            label.setPos(x + r, y - r - 18)
            label.setZValue(5)

    def fit(self) -> None:
        if not self.scene().sceneRect().isEmpty():
            self.fitInView(self.scene().sceneRect(), Qt.KeepAspectRatio)

    def mouseDoubleClickEvent(self, event):
        self.fit()  # the whole sheet again

    def wheelEvent(self, event):
        factor = 1.25 if event.angleDelta().y() > 0 else 0.8
        self.scale(factor, factor)

    def point_at(self, x: float, y: float) -> None:
        if self.marker is not None:
            self.scene().removeItem(self.marker)
        r = 30
        self.marker = self.scene().addEllipse(x - r, y - r, 2 * r, 2 * r,
                                              QPen(QColor(self.colors["warn"]), 6),
                                              QBrush(Qt.NoBrush))
        self.resetTransform()
        self.scale(1.2, 1.2)
        self.centerOn(x, y)


def _night(image: QImage, ground: QColor) -> QImage:
    """Light lines on a dark sheet with the hues kept: blue stays blue, red stays red.

    Lightness is mirrored (c + 255 - max - min per pixel), so white paper turns
    black and black lines white; the paper is then lifted to the sheet colour.
    """
    import numpy as np

    width, height = image.width(), image.height()
    ptr = image.constBits()
    rgba = np.frombuffer(ptr, np.uint8, image.bytesPerLine() * height)
    rgba = rgba.reshape(height, image.bytesPerLine())[:, :width * 4].reshape(height, width, 4)
    floor = np.array([ground.blue(), ground.green(), ground.red()], np.int16)
    result = np.empty((height, width, 4), np.uint8)
    result[..., 3] = 255
    for y0 in range(0, height, 256):  # in bands: a big sheet stays small in memory
        rgb = rgba[y0:y0 + 256, :, :3].astype(np.int16)  # BGRA order; symmetric anyway
        shift = 255 - rgb.max(axis=2, keepdims=True) - rgb.min(axis=2, keepdims=True)
        result[y0:y0 + 256, :, :3] = np.maximum(np.clip(rgb + shift, 0, 255), floor)
    night = QImage(result.data, width, height, width * 4, QImage.Format_ARGB32)
    return night.copy()  # its own pixels: ``result`` goes away with this function


def card(name: str = "card") -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame(objectName=name)
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(20, 16, 20, 18)
    lay.setSpacing(8)
    return frame, lay


def label(text: str, name: str = "") -> QLabel:
    label = QLabel(text)
    if name:
        label.setObjectName(name)
    return label


class StatCard(QFrame):
    """A big number with a caption: rules, dimensions. A click opens its list."""

    clicked = Signal()

    def __init__(self, title: str):
        super().__init__(objectName="card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 18)
        self.title = label(title, "cardTitle")
        lay.addWidget(self.title)
        lay.addStretch(1)
        self.value = label("—", "big")
        self.note = label("откройте чертёж", "sub")
        self.note.setWordWrap(True)
        lay.addWidget(self.value)
        lay.addWidget(self.note)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def set_title(self, title: str) -> None:
        self.title.setText(title)

    def set_value(self, value: str, note: str, state: str = "") -> None:
        self.value.setText(value)
        self.note.setText(note)
        self.note.setObjectName({"ok": "subOk", "warn": "subWarn"}.get(state, "sub"))
        self.note.style().unpolish(self.note)
        self.note.style().polish(self.note)


def chip(text: str, state: str = "") -> QLabel:
    """A small rounded label: plain, ok (green) or warn (orange)."""
    return label(text, {"ok": "chipOk", "warn": "chipWarn"}.get(state, "chip"))


def restyle(widget: QWidget, name: str) -> None:
    """A new object name, and the style sheet applied to it again."""
    widget.setObjectName(name)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class ActionButton(QPushButton):
    """A button that follows its action's text (the theme button names the
    next theme); a slot of its own, so a deleted button is let go."""

    def __init__(self, action, text, kind):
        super().__init__(text or action.text(), objectName=kind)
        self._action = action
        self._fixed = text
        self._short: str | None = None
        if not text:
            action.changed.connect(self._sync)

    def set_short(self, short: str | None) -> None:
        """A shorter label for a narrow window («icon»: the first sign only);
        the full one is in the tooltip. None: the full label again."""
        self._short = short
        self._sync()

    def _sync(self) -> None:
        full = self._fixed or self._action.text()
        tip = self._action.toolTip()
        tip = "" if tip in ("", self._action.text()) else tip
        if self._short:
            self.setText(full.split()[0] if self._short == "icon" else self._short)
            self.setToolTip(full + (f"\n{tip}" if tip else ""))
        else:
            self.setText(full)
            self.setToolTip(tip)


def action_button(action, kind: str = "secondary", text: str | None = None) -> QPushButton:
    """A push button doing what ``action`` does and enabled when it is: the
    same command in every layout, one place deciding when it is allowed."""
    button = ActionButton(action, text, kind)
    button.setCursor(Qt.PointingHandCursor)
    if kind != "primary":  # never squeezed below its text
        button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    button.clicked.connect(action.trigger)
    button.setEnabled(action.isEnabled())
    action.enabledChanged.connect(button.setEnabled)
    tip = action.toolTip()
    if action.shortcut().toString():
        tip = f"{tip} ({action.shortcut().toString()})" if tip and tip != action.text() \
            else action.shortcut().toString()
    if tip and tip != action.text():
        button.setToolTip(tip)
    return button


class ClickCard(QFrame):
    """A card that acts as a button (a recent drawing with its picture)."""

    clicked = Signal()

    def __init__(self, name: str = "thumbCard"):
        super().__init__(objectName=name)
        self.setCursor(Qt.PointingHandCursor)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class ElidedLabel(QLabel):
    """A label that shortens its text in the middle to the width it gets (a
    long file name never pushes the buttons out of the window)."""

    def __init__(self, text: str = "", name: str = ""):
        super().__init__()
        if name:
            self.setObjectName(name)
        self.full = text
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setMinimumWidth(60)
        self.setText(text)

    def setText(self, text: str) -> None:  # noqa: N802 (Qt's name)
        self.full = text
        self.setToolTip(text)
        self._elide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._elide()

    def _elide(self) -> None:
        width = max(self.width() - 4, 40)
        QLabel.setText(self, self.fontMetrics().elidedText(self.full, Qt.ElideMiddle, width))


class Ring(QWidget):
    """A share as a ring with «7/7» in it (sizes held exactly, of all)."""

    def __init__(self, size: int = 76):
        super().__init__()
        self.setFixedSize(size, size)
        self.value, self.total = 0, 0
        self.colors = THEMES["light"]

    def set_value(self, value: int, total: int) -> None:
        self.value, self.total = value, total
        self.setToolTip(f"Размеров выдержано точно: {value} из {total}")
        self.update()

    def paintEvent(self, event):
        c = self.colors
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = 8
        rect = QRectF(w / 2, w / 2, self.width() - w, self.height() - w)
        p.setPen(QPen(QColor(c["card_alt"]), w))
        p.drawEllipse(rect)
        if self.total:
            share = self.value / self.total
            color = c["ok"] if share >= 0.999 else c["warn"]
            pen = QPen(QColor(color), w)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            p.drawArc(rect, 90 * 16, -int(360 * 16 * share))
        p.setPen(QColor(c["text"]))
        font = QFont()
        font.setPixelSize(15)
        font.setBold(True)
        p.setFont(font)
        p.drawText(self.rect(), Qt.AlignCenter, f"{self.value}/{self.total}" if self.total else "—")
