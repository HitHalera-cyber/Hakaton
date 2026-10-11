"""Main window: open a drawing, look at what was recognised, build it in KOMPAS.

    py -m kompas_ai.gui            (or KompasAI.exe)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from PySide6.QtCore import QEvent, QSettings, Qt, QThread
from PySide6.QtGui import (QAction, QBrush, QColor, QIcon, QImage, QKeySequence, QPainter, QPen,
                           QPixmap)
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox, QFileDialog,
                               QFrame, QGraphicsEllipseItem, QGraphicsScene, QGraphicsView,
                               QGridLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QMainWindow, QMessageBox, QPlainTextEdit, QPushButton,
                               QStackedWidget, QVBoxLayout, QWidget)

from .. import ir
from ..export.dxf_writer import write_dxf
from ..report.preview import sheet_to_pixel
from ..report.summary import TYPE_NAMES, summary_text
from ..pipeline import STAGES
from .loader import DraftingLoader
from .theme import THEME_ICONS, THEME_NAMES, THEMES, style_sheet
from .workers import PREVIEW_DPI, PREVIEW_STAGE, KompasJob, RecognizeJob, RevolveJob

APP_NAME = "КОМПАС-AI"
MODES = [("Точно по размерам", True), ("Как в PDF (без выравнивания)", False)]
BUILD_MODES = [("Вид с масштабом чертежа", "view"), ("В миллиметрах листа", "sheet")]
PAGES = ["Чертёж", "Отчёт", "Проверка", "Журнал"]
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
        if keep_view:
            self.setTransform(transform)
            self.centerOn(center)
        else:
            self.fit()

    def fit(self) -> None:
        if not self.scene().sceneRect().isEmpty():
            self.fitInView(self.scene().sceneRect(), Qt.KeepAspectRatio)

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
    rgb = rgba[..., :3].astype(np.int16)  # BGRA order on little endian; symmetric anyway
    shift = 255 - rgb.max(axis=2, keepdims=True) - rgb.min(axis=2, keepdims=True)
    out = np.clip(rgb + shift, 0, 255)
    floor = np.array([ground.blue(), ground.green(), ground.red()], np.int16)
    out = np.maximum(out, floor).astype(np.uint8)
    result = np.dstack([out, np.full((height, width, 1), 255, np.uint8)])
    night = QImage(result.tobytes(), width, height, width * 4, QImage.Format_ARGB32)
    return night.copy()


def _card(name: str = "card") -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame(objectName=name)
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(20, 16, 20, 18)
    lay.setSpacing(8)
    return frame, lay


def _label(text: str, name: str = "") -> QLabel:
    label = QLabel(text)
    if name:
        label.setObjectName(name)
    return label


class StatCard(QFrame):
    """A big number with a caption: rules, dimensions."""

    def __init__(self, title: str):
        super().__init__(objectName="card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 18)
        lay.addWidget(_label(title, "cardTitle"))
        lay.addStretch(1)
        self.value = _label("—", "big")
        self.note = _label("откройте чертёж", "sub")
        self.note.setWordWrap(True)
        lay.addWidget(self.value)
        lay.addWidget(self.note)

    def set_value(self, value: str, note: str, state: str = "") -> None:
        self.value.setText(value)
        self.note.setText(note)
        self.note.setObjectName({"ok": "subOk", "warn": "subWarn"}.get(state, "sub"))
        self.note.style().unpolish(self.note)
        self.note.style().polish(self.note)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1440, 900)
        self.setMinimumSize(1100, 720)
        self.settings = QSettings("KompasAI", "KompasAI")
        self.pdf: Path | None = None
        self.drawing: ir.Drawing | None = None
        self.page_height = 0.0
        self.thread: QThread | None = None
        self.job = None
        self.pending: Path | None = None
        self.model_ok: bool | None = None

        self.preview = PreviewView()
        self.preview.setAcceptDrops(False)  # a PDF dropped on the drawing reaches the window
        self.preview.viewport().setAcceptDrops(False)
        self.summary = QPlainTextEdit(readOnly=True, objectName="report")
        self.summary.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.review = QListWidget()
        self.review.itemClicked.connect(self.on_review_clicked)
        self.log = QPlainTextEdit(readOnly=True, objectName="log")
        self.log.setMaximumBlockCount(500)

        root = QWidget(objectName="root")
        lay = QHBoxLayout(root)
        lay.setContentsMargins(20, 20, 20, 8)
        lay.setSpacing(18)
        lay.addWidget(self._sidebar())
        column = QVBoxLayout()
        column.setSpacing(18)
        column.addLayout(self._header())
        self.pages = QStackedWidget()
        self.pages.addWidget(self._drawing_page())
        self.pages.addWidget(self._text_page("Результат распознавания", self.summary))
        self.pages.addWidget(self._text_page(
            "Требуют проверки — щёлкните, покажу на листе", self.review))
        self.pages.addWidget(self._log_page())
        column.addWidget(self.pages, 1)
        lay.addLayout(column, 1)
        self.setCentralWidget(root)

        open_act = QAction(self, shortcut=QKeySequence.Open)
        open_act.triggered.connect(self.open_dialog)
        self.addAction(open_act)
        self.setAcceptDrops(True)
        self.apply_theme(self.settings.value("theme", "light"))
        self._set_ready(False)
        self.statusBar().showMessage("Откройте PDF чертежа (или перетащите его в окно)")

    # --- layout -------------------------------------------------------------------------

    def _sidebar(self) -> QFrame:
        side = QFrame(objectName="sidebar")
        side.setFixedWidth(232)
        lay = QVBoxLayout(side)
        lay.setContentsMargins(16, 20, 16, 16)
        lay.setSpacing(6)
        brand = QHBoxLayout()
        brand.setSpacing(10)
        icon = _icon_path()
        if icon:
            logo = QLabel()
            logo.setPixmap(QPixmap(str(icon)).scaled(34, 34, Qt.KeepAspectRatio,
                                                     Qt.SmoothTransformation))
            brand.addWidget(logo)
        brand.addWidget(_label(APP_NAME, "brand"))
        brand.addStretch(1)
        lay.addLayout(brand)
        lay.addSpacing(18)

        self.nav = QButtonGroup(self)
        for i, name in enumerate(PAGES):
            button = QPushButton(name, objectName="nav", checkable=True)
            button.setCursor(Qt.PointingHandCursor)
            self.nav.addButton(button, i)
            lay.addWidget(button)
        self.nav.button(0).setChecked(True)
        self.nav.idClicked.connect(lambda i: self.pages.setCurrentIndex(i))

        lay.addStretch(1)
        self.theme_button = QPushButton(objectName="flat")
        self.theme_button.setCursor(Qt.PointingHandCursor)
        self.theme_button.clicked.connect(self.toggle_theme)
        lay.addWidget(self.theme_button)
        ready = sys.platform == "win32"
        self.kompas_note = _label("КОМПАС-3D v23<br>" + (
            "строит в Windows" if ready else "доступен только в Windows"), "kompas")
        self.kompas_note.setTextFormat(Qt.RichText)
        self.kompas_note.setWordWrap(True)
        lay.addWidget(self.kompas_note)
        return side

    def _header(self) -> QHBoxLayout:
        head = QHBoxLayout()
        head.setSpacing(14)
        self.title = _label("Чертёж не открыт", "title")
        head.addWidget(self.title)
        self.sheet_chip = _label("", "chip")
        self.sheet_chip.hide()
        head.addWidget(self.sheet_chip)
        head.addStretch(1)
        open_button = QPushButton("Открыть PDF", objectName="secondary")
        open_button.clicked.connect(self.open_dialog)
        head.addWidget(open_button)
        self.build_button = QPushButton("Построить в КОМПАС", objectName="primary")
        self.build_button.clicked.connect(self.build_in_kompas)
        if sys.platform != "win32":
            self.build_button.setToolTip("Доступно в Windows с установленным КОМПАС-3D")
        head.addWidget(self.build_button)
        for button in (open_button, self.build_button):
            button.setCursor(Qt.PointingHandCursor)
        return head

    def _drawing_page(self) -> QWidget:
        page = QWidget()
        grid = QGridLayout(page)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(18)
        for i in range(3):
            grid.setColumnStretch(i, 1)
        grid.setRowStretch(0, 3)
        grid.setRowStretch(1, 3)
        grid.setRowStretch(2, 2)

        sheet, lay = _card()
        lay.setContentsMargins(14, 14, 14, 14)
        top = QHBoxLayout()
        top.setSpacing(8)
        self.view_label = _label("Чертёж", "cardTitle")
        top.addWidget(self.view_label)
        top.addStretch(1)
        self.contour_chip = _label("", "chipOk")
        self.contour_chip.hide()
        top.addWidget(self.contour_chip)
        fit = QPushButton("Весь лист", objectName="flat")
        fit.clicked.connect(self.preview.fit)
        top.addWidget(fit)
        lay.addLayout(top)
        lay.addWidget(self.preview, 1)
        grid.addWidget(sheet, 0, 0, 2, 2)
        self.sheet_card = sheet
        self.loader = DraftingLoader(sheet)
        sheet.installEventFilter(self)

        self.rules_card = StatCard("Правила контура")
        grid.addWidget(self.rules_card, 0, 2)
        self.dims_card = StatCard("Размеров")
        grid.addWidget(self.dims_card, 1, 2)

        options, lay = _card()
        lay.addWidget(_label("Параметры построения", "cardTitle"))
        row = QGridLayout()
        row.setHorizontalSpacing(24)
        row.setVerticalSpacing(12)
        self.mode = QComboBox()
        for name, _ in MODES:
            self.mode.addItem(name)
        self.mode.setToolTip("Точно по размерам — геометрия доводится до значений размеров чертежа")
        self.mode.currentIndexChanged.connect(lambda _: self.recognize())
        self.build_mode = QComboBox()
        for name, _ in BUILD_MODES:
            self.build_mode.addItem(name)
        self.build_mode.setToolTip(
            "Вид с масштабом: деталь в настоящих размерах, КОМПАС сам считает размеры "
            "(нужна лицензия, иначе — мм листа).\nВ миллиметрах листа: как на PDF, "
            "числа размеров вписываются из PDF.")
        self.dims_box = QCheckBox("Размеры по ГОСТ")
        self.dims_box.setChecked(True)
        self.dims_box.setToolTip("Снимите, чтобы построить просто чертёж — без размеров")
        self.param_box = QCheckBox("Параметризация")
        self.param_box.setChecked(True)
        self.param_box.setToolTip("Связи: горизонталь, вертикаль, совпадение концов, касание, "
                                  "концентричность, точки размеров на контуре "
                                  "(нужна лицензия КОМПАС)")
        row.addWidget(self.mode, 0, 0)
        row.addWidget(self.build_mode, 0, 1)
        row.addWidget(self.dims_box, 1, 0)
        row.addWidget(self.param_box, 1, 1)
        lay.addLayout(row)
        lay.addStretch(1)
        grid.addWidget(options, 2, 0, 1, 2)

        model, lay = _card("cardAccent")
        lay.addWidget(_label("3D-модель", "cardTitle"))
        self.model_note = _label("Тело вращения: профиль над осью вращается на 360°, "
                                 "лыски, отверстия, резьба", "sub")
        self.model_note.setWordWrap(True)
        lay.addWidget(self.model_note)
        lay.addStretch(1)
        self.model_button = QPushButton("Построить модель", objectName="secondary")
        self.model_button.setCursor(Qt.PointingHandCursor)
        self.model_button.clicked.connect(self.build_3d)
        lay.addWidget(self.model_button)
        grid.addWidget(model, 2, 2)
        return page

    def _text_page(self, title: str, body: QWidget) -> QWidget:
        frame, lay = _card()
        lay.addWidget(_label(title, "cardTitle"))
        lay.addWidget(body, 1)
        return frame

    def _log_page(self) -> QWidget:
        frame, lay = _card()
        top = QHBoxLayout()
        top.addWidget(_label("Журнал", "cardTitle"))
        top.addStretch(1)
        self.dxf_button = QPushButton("Сохранить DXF…", objectName="secondary")
        self.dxf_button.clicked.connect(self.save_dxf)
        self.report_button = QPushButton("Сохранить отчёт…", objectName="secondary")
        self.report_button.clicked.connect(self.save_report)
        top.addWidget(self.dxf_button)
        top.addWidget(self.report_button)
        lay.addLayout(top)
        lay.addWidget(self.log, 1)
        return frame

    def eventFilter(self, obj, event):
        if obj is self.sheet_card and event.type() == QEvent.Resize:
            self.loader.setGeometry(self.sheet_card.rect())
        return super().eventFilter(obj, event)

    # --- theme ----------------------------------------------------------------------------

    def apply_theme(self, name: str) -> None:
        self.theme = name if name in THEMES else "light"
        colors = THEMES[self.theme]
        self.setStyleSheet(style_sheet(colors))
        self.preview.set_colors(colors)
        self.loader.set_colors(colors)
        nxt = self._next_theme()
        self.theme_button.setText(f"{THEME_ICONS[nxt]}  {THEME_NAMES[nxt]}")
        self.settings.setValue("theme", self.theme)

    def _next_theme(self) -> str:
        names = list(THEMES)
        return names[(names.index(self.theme) + 1) % len(names)]

    def toggle_theme(self) -> None:
        self.apply_theme(self._next_theme())

    def _set_ready(self, ready: bool) -> None:
        for button in (self.build_button, self.model_button, self.dxf_button, self.report_button):
            button.setEnabled(ready)
        if self.model_ok is False:
            self.model_button.setEnabled(False)  # only the drawing for this part
        if sys.platform != "win32":
            self.build_button.setEnabled(False)
            self.model_button.setEnabled(False)

    # --- open / recognise -----------------------------------------------------------------

    def open_dialog(self) -> None:
        start = self.settings.value("last_dir", str(Path.home()))
        name, _ = QFileDialog.getOpenFileName(self, "Открыть чертёж", start, "PDF (*.pdf)")
        if name:
            self.open_file(Path(name))

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.suffix.lower() == ".pdf":
                self.open_file(path)
                break

    def open_file(self, path: Path) -> None:
        if self._busy():
            # after the running job: a drawing opened meanwhile is not lost
            self.pending = path
            self._log(f"Откроется после текущей операции: {path.name}")
            self.statusBar().showMessage(f"{path.name} откроется, когда закончится текущая операция")
            return
        self.pending = None
        self.pdf = path
        self.drawing = None
        self.model_ok = None
        self.show_page(0)
        self.settings.setValue("last_dir", str(path.parent))
        self.setWindowTitle(f"{APP_NAME} — {path.name}")
        self.title.setText(path.name)
        self.recognize()

    def recognize(self) -> None:
        if self.pdf is None or self._busy():
            return
        self._set_ready(False)
        self.statusBar().showMessage(f"Распознаю {self.pdf.name}…")
        self._log(f"Распознавание: {self.pdf}")
        job = RecognizeJob(self.pdf, exact=MODES[self.mode.currentIndex()][1])
        exact = MODES[self.mode.currentIndex()][1]
        stages = [s for s in STAGES if exact or s not in STAGES[5:]] + [PREVIEW_STAGE]
        self.loader.start(f"Читаю {self.pdf.name}", stages)
        job.stage.connect(self.loader.stage)
        job.finished.connect(self.on_recognized)
        job.failed.connect(self.on_failed)
        self._start(job)

    def on_recognized(self, drawing: ir.Drawing, png: bytes, page_height: float) -> None:
        self.loader.stop()
        self.drawing, self.page_height = drawing, page_height
        self.preview.show_png(png)
        self.summary.setPlainText(summary_text(drawing))
        self.review.clear()
        for e in drawing.review:
            note = "; ".join(e.notes)
            item = QListWidgetItem(f"{TYPE_NAMES.get(e.kind, e.kind)} {e.id} — {e.confidence:.0%}"
                                   + (f": {note}" if note else ""))
            item.setData(Qt.UserRole, e.id)
            self.review.addItem(item)
        self._show_results(drawing)
        self._judge_model(drawing)
        for w in drawing.warnings:
            if w.startswith("Точный режим"):
                self._log(w)
        counts = drawing.summary()
        self.statusBar().showMessage(
            f"Готово: {len(drawing.entities)} объектов, требуют проверки {counts['review']}")
        self._log("Распознавание завершено")
        self._set_ready(True)

    def _judge_model(self, drawing: ir.Drawing) -> None:
        """Whether a body of revolution can be made: if not, only the drawing."""
        try:
            from ..model3d.revolve import find_revolve_profile, revolve_verdict

            ok, why = revolve_verdict(drawing)
            if ok is False and not MODES[self.mode.currentIndex()][1] \
                    and find_revolve_profile(drawing) is not None:
                # without the fitting the model follows the lines, whatever the sizes say
                ok, why = None, "режим без выравнивания: модель строится по линиям чертежа"
            if ok is not False and find_revolve_profile(drawing) is None:
                ok, why = False, "не найден профиль над осевой линией"
        except Exception as exc:  # the drawing stays usable whatever happens here
            ok, why = None, f"не удалось проверить: {exc!r}"
        self.model_ok = ok
        if ok is False:
            self.model_note.setText(f"Не тело вращения — будет только чертёж. {why[:1].upper() + why[1:]}.")
            self.model_note.setObjectName("subWarn")
            self._log(f"3D-модель не строится: {why}")
        else:
            self.model_note.setText("Тело вращения: " + why + (
                "" if ok else ". Проверьте модель после построения") + ".")
            self.model_note.setObjectName("sub")
        self.model_note.style().unpolish(self.model_note)
        self.model_note.style().polish(self.model_note)

    def _show_results(self, drawing: ir.Drawing) -> None:
        self.sheet_chip.setText(f"{drawing.sheet.format} · {drawing.scale.text}")
        self.sheet_chip.show()
        self.view_label.setText(f"Чертёж · масштаб {drawing.scale.text}")
        broken = _broken_rules(drawing)
        exact = MODES[self.mode.currentIndex()][1]
        if not exact:
            self.rules_card.set_value("—", "выравнивание выключено")
            self.contour_chip.hide()
        else:
            self.rules_card.set_value(str(broken), "нарушений" if broken else "нарушений · контур точный",
                                      "warn" if broken else "ok")
            self.contour_chip.setText("Есть нарушения" if broken else "Контур замкнут")
            self.contour_chip.setObjectName("chipWarn" if broken else "chipOk")
            self.contour_chip.style().unpolish(self.contour_chip)
            self.contour_chip.style().polish(self.contour_chip)
            self.contour_chip.show()
        dims = drawing.of_type(ir.Dimension)
        doubtful = sum(1 for d in dims if d.confidence < ir.REVIEW_THRESHOLD)
        self.dims_card.set_value(str(len(dims)),
                                 f"проверить: {doubtful}" if doubtful else "все распознаны уверенно",
                                 "warn" if doubtful else "ok")
        self.nav.button(2).setText(f"Проверка · {len(drawing.review)}" if drawing.review
                                   else "Проверка")

    def on_review_clicked(self, item: QListWidgetItem) -> None:
        if self.drawing is None:
            return
        entity = self.drawing.get(item.data(Qt.UserRole))
        anchor = _anchor(entity) if entity else None
        if anchor:
            self.show_page(0)
            x, y = sheet_to_pixel(self.drawing, self.page_height, PREVIEW_DPI, anchor)
            self.preview.point_at(x, y)

    # --- outputs -----------------------------------------------------------------------------

    def build_in_kompas(self) -> None:
        if self.drawing is None or self._busy():
            return
        out = self.pdf.with_name(self.pdf.stem + "_kompas.cdw")
        name, _ = QFileDialog.getSaveFileName(self, "Сохранить чертёж КОМПАС", str(out),
                                              "КОМПАС (*.cdw)")
        if not name:
            return
        self._set_ready(False)
        self.statusBar().showMessage("Строю чертёж в КОМПАС…")
        self.show_page(PAGES.index("Журнал"))
        job = KompasJob(self.drawing, Path(name), BUILD_MODES[self.build_mode.currentIndex()][1],
                        with_dimensions=self.dims_box.isChecked(),
                        parametric=self.param_box.isChecked())
        job.progress.connect(self._log)
        job.finished.connect(self.on_built)
        job.failed.connect(self.on_failed)
        self._start(job)

    def build_3d(self) -> None:
        if self.drawing is None or self._busy():
            return
        out = self.pdf.with_name(self.pdf.stem + "_kompas.m3d")
        name, _ = QFileDialog.getSaveFileName(self, "Сохранить деталь КОМПАС", str(out),
                                              "Деталь КОМПАС (*.m3d)")
        if not name:
            return
        self._set_ready(False)
        self.statusBar().showMessage("Строю 3D-модель в КОМПАС…")
        self.show_page(PAGES.index("Журнал"))
        job = RevolveJob(self.drawing, Path(name), exact=MODES[self.mode.currentIndex()][1])
        job.progress.connect(self._log)
        job.finished.connect(self.on_built)
        job.failed.connect(self.on_failed)
        self._start(job)

    def show_page(self, index: int) -> None:
        self.nav.button(index).setChecked(True)
        self.pages.setCurrentIndex(index)

    def on_built(self, report: str) -> None:
        self._log(report)
        self.statusBar().showMessage("Построено в КОМПАС — подробности в журнале")
        self._set_ready(True)
        self.show_page(PAGES.index("Журнал"))
        QMessageBox.information(self, APP_NAME, report)

    def save_dxf(self) -> None:
        name, _ = QFileDialog.getSaveFileName(
            self, "Сохранить DXF", str(self.pdf.with_suffix(".dxf")), "DXF (*.dxf)")
        if name:
            write_dxf(self.drawing, name)
            self._log(f"DXF сохранён: {name}")

    def save_report(self) -> None:
        name, _ = QFileDialog.getSaveFileName(
            self, "Сохранить отчёт", str(self.pdf.with_name(self.pdf.stem + "_отчёт.txt")),
            "Текст (*.txt)")
        if name:
            Path(name).write_text(summary_text(self.drawing) + "\n", encoding="utf-8")
            self.drawing.save_json(Path(name).with_suffix(".json"))
            self._log(f"Отчёт сохранён: {name}")

    # --- helpers --------------------------------------------------------------------------------

    def on_failed(self, message: str) -> None:
        self.loader.stop()
        self._log(message)
        self.statusBar().showMessage("Ошибка — подробности в журнале")
        self._set_ready(self.drawing is not None)
        self.show_page(PAGES.index("Журнал"))
        QMessageBox.warning(self, APP_NAME, message.strip().splitlines()[-1])

    def _log(self, text: str) -> None:
        self.log.appendPlainText(text)

    def _busy(self) -> bool:
        return self.thread is not None and self.thread.isRunning()

    def _start(self, job) -> None:
        self.thread = QThread(self)
        self.job = job
        job.moveToThread(self.thread)
        self.thread.started.connect(job.run)
        for signal in (job.finished, job.failed):
            signal.connect(self.thread.quit)
        self.thread.finished.connect(self._after_job)
        self.thread.start()

    def _after_job(self) -> None:
        if self.pending is not None:
            path, self.pending = self.pending, None
            self.open_file(path)


def _broken_rules(drawing: ir.Drawing) -> int:
    """Number of contour rules the pipeline reported as broken (0 when none)."""
    for w in drawing.warnings:
        m = re.match(r"Правила контура не выполнены \((\d+)\)", w)
        if m:
            return int(m.group(1))
    return 0


def _anchor(e: ir.Entity):
    if isinstance(e, ir.Line):
        return ((e.p1[0] + e.p2[0]) / 2, (e.p1[1] + e.p2[1]) / 2)
    if isinstance(e, (ir.Circle, ir.Arc, ir.Ellipse)):
        return e.center
    if isinstance(e, ir.Dimension):
        return e.line_point or e.p1 or e.center
    if isinstance(e, ir.Text):
        return e.position
    if isinstance(e, ir.PointMark):
        return e.position
    if isinstance(e, ir.Hatch) and e.contours:
        return e.contours[0][0]
    return None


def _icon_path() -> Path | None:
    """Icon next to the packaged exe, or in the source tree when run from code."""
    candidates = [Path(getattr(sys, "_MEIPASS", "")) / "kompas_ai" / "kompas_ai.png",
                  Path(__file__).resolve().parents[3] / "packaging" / "icon" / "kompas_ai.png"]
    return next((p for p in candidates if p.is_file()), None)


def main(argv: list[str] | None = None) -> int:
    if sys.platform == "win32":
        # Own taskbar identity: without it Windows groups the window under the
        # python/launcher icon instead of the application's own icon.
        import ctypes

        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("KompasAI.App")
        except (AttributeError, OSError):
            pass
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    icon = _icon_path()
    if icon:
        app.setWindowIcon(QIcon(str(icon)))
    window = MainWindow()
    window.show()
    args = app.arguments()[1:]
    if args and Path(args[0]).suffix.lower() == ".pdf" and Path(args[0]).exists():
        window.open_file(Path(args[0]))
    return app.exec()
