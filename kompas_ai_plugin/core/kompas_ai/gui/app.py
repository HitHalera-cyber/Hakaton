"""Main window: open a drawing, look at what was recognised, build it in KOMPAS.

    py -m kompas_ai.gui            (or KompasAI.exe)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from PySide6.QtCore import QEvent, QSettings, Qt, QThread, Signal
from PySide6.QtGui import (QAction, QBrush, QColor, QIcon, QImage, QKeySequence, QPainter, QPen,
                           QPixmap)
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox, QFileDialog,
                               QFrame, QGraphicsEllipseItem, QGraphicsScene, QGraphicsView,
                               QGridLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QPushButton,
                               QSizePolicy,
                               QStackedWidget, QVBoxLayout, QWidget)

from .. import ir
from ..export.dxf_writer import write_dxf
from ..report.preview import sheet_to_pixel
from ..report.summary import TYPE_NAMES, summary_text
from ..pipeline import STAGES
from .loader import DraftingLoader
from .session import SessionLog, app_folder, recent_files, remember_file, stamped
from .theme import THEME_ICONS, THEME_NAMES, THEMES, style_sheet
from .workers import (CANCELLED, IMAGE_SUFFIXES, MODEL_STAGE, PHOTO_STAGE, PREVIEW_DPI, PREVIEW_STAGE, BothJob, CheckJob,
                      KompasJob, ModelDrawingJob, RecognizeJob, RevolveJob)

APP_NAME = "КОМПАС-AI"
MODES = [("Точно по размерам", True), ("Как в PDF (без выравнивания)", False)]
SCALES = [("Масштаб как на чертеже", None)] + [
    (f"Масштаб {name}", value) for name, value in (
        ("1:1", 1.0), ("1:2", 0.5), ("1:2,5", 0.4), ("1:4", 0.25), ("1:5", 0.2), ("1:10", 0.1),
        ("2:1", 2.0), ("2,5:1", 2.5), ("4:1", 4.0), ("5:1", 5.0), ("10:1", 10.0))]
PAGES = ["Чертёж", "Отчёт", "Проверка", "Журнал"]
SHEET_FORMATS = [("A4", (210.0, 297.0)), ("A3", (297.0, 420.0)), ("A2", (420.0, 594.0)),
                 ("A1", (594.0, 841.0)), ("A0", (841.0, 1189.0))]
PHOTO_SCALES = [(name, value) for name, value in SCALES[1:]]
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
    """A big number with a caption: rules, dimensions. A click opens its list."""

    clicked = Signal()

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

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)

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
        self.session_log = SessionLog()
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
            "Нарушения правил контура и объекты под вопросом — щёлкните, покажу на листе",
            self.review))
        self.pages.addWidget(self._log_page())
        column.addWidget(self.pages, 1)
        lay.addLayout(column, 1)
        self.setCentralWidget(root)

        self._shortcuts()
        self._restore_options()
        self.setAcceptDrops(True)
        self.apply_theme(self.settings.value("theme", "light"))
        self._set_ready(False)
        self.statusBar().showMessage("Откройте PDF чертежа (или перетащите его в окно)")

    # --- layout -------------------------------------------------------------------------

    def _shortcuts(self) -> None:
        def when_enabled(button):  # a key does no more than its button may
            return lambda: button.isEnabled() and button.click()

        keys = [(QKeySequence.Open, self.open_dialog),
                ("Ctrl+B", when_enabled(self.build_button)),
                ("Ctrl+M", when_enabled(self.model_button)),
                ("Ctrl+Shift+B", when_enabled(self.both_button)), ("Ctrl+0", self.preview.fit),
                ("Esc", self.cancel_recognition), ("Ctrl+L", self.open_log_folder)]
        keys += [(f"Ctrl+{i + 1}", lambda i=i: self.show_page(i)) for i in range(len(PAGES))]
        for key, action in keys:
            act = QAction(self, shortcut=QKeySequence(key))
            act.triggered.connect(action)
            self.addAction(act)

    def _restore_options(self) -> None:
        """The build options as they were left last time (and kept on change)."""
        s = self.settings

        def index(key, box):
            try:
                i = int(s.value(key, 0))
            except (TypeError, ValueError):
                i = 0
            if 0 <= i < box.count():
                box.blockSignals(True)  # no recognition: nothing is open yet
                box.setCurrentIndex(i)
                box.blockSignals(False)
            box.currentIndexChanged.connect(lambda i, key=key: s.setValue(key, i))

        index("mode", self.mode)
        index("scale", self.scale_box)
        for key, box in (("dims", self.dims_box), ("parametric", self.param_box)):
            box.setChecked(str(s.value(key, "true")).lower() in ("true", "1"))
            box.toggled.connect(lambda on, key=key: s.setValue(key, on))

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
        # a long file name is shortened, never pushes the buttons off the window
        self.title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.title.setMinimumWidth(120)
        head.addWidget(self.title, 1)
        self.sheet_chip = _label("", "chip")
        self.sheet_chip.hide()
        head.addWidget(self.sheet_chip)
        open_button = QPushButton("Открыть PDF / фото", objectName="secondary")
        open_button.clicked.connect(self.open_dialog)
        open_button.setCursor(Qt.PointingHandCursor)
        model_button = QPushButton("Чертёж по модели…", objectName="secondary")
        model_button.setToolTip("Открыть 3D-модель КОМПАС (.m3d) и построить её чертёж: виды "
                                "спереди, сверху, слева и изометрия, связанные с моделью")
        model_button.clicked.connect(self.drawing_from_model)
        model_button.setCursor(Qt.PointingHandCursor)
        self.recent_button = QPushButton("Недавние", objectName="secondary")
        self.recent_button.setCursor(Qt.PointingHandCursor)
        self.recent_button.setToolTip("Чертежи, открытые недавно")
        self.recent_menu = QMenu(self)
        self.recent_button.setMenu(self.recent_menu)
        self._fill_recent()
        open_button.setToolTip("Ctrl+O. Можно и перетащить файл в окно (PDF, фото, .m3d)")
        head.addWidget(self.recent_button)
        head.addWidget(model_button)
        head.addWidget(open_button)
        return head

    def _fill_recent(self, paths=None) -> None:
        self.recent_menu.clear()
        paths = recent_files(self.settings) if paths is None else paths
        for path in paths:
            act = self.recent_menu.addAction(path.name)
            act.setToolTip(str(path))
            act.triggered.connect(lambda _=False, p=path: self.open_file(p))
        self.recent_button.setEnabled(bool(paths))

    def _drawing_page(self) -> QWidget:
        page = QWidget()
        grid = QGridLayout(page)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(18)
        for i in range(3):
            grid.setColumnStretch(i, 1)
        grid.setRowStretch(0, 3)
        grid.setRowStretch(1, 3)
        grid.setRowStretch(2, 3)

        sheet, lay = _card()
        lay.setContentsMargins(14, 14, 14, 14)
        top = QHBoxLayout()
        top.setSpacing(8)
        self.view_label = _label("Чертёж", "cardTitle")
        top.addWidget(self.view_label)
        top.addStretch(1)
        self.marks_box = QCheckBox("Нарушения на листе")
        self.marks_box.setChecked(True)
        self.marks_box.setToolTip("Красные кольца с номерами там, где контур нарушает правила")
        self.marks_box.toggled.connect(self._toggle_marks)
        top.addWidget(self.marks_box)
        self.contour_chip = _label("", "chipOk")
        self.contour_chip.hide()
        top.addWidget(self.contour_chip)
        lay.addLayout(top)
        self.preview.setToolTip("Колесо — масштаб, перетаскивание — сдвиг, двойной щелчок или "
                                "Ctrl+0 — весь лист")
        lay.addWidget(self.preview, 1)
        grid.addWidget(sheet, 0, 0, 2, 2)
        self.sheet_card = sheet
        self.loader = DraftingLoader(sheet)
        self.loader.cancel_button.clicked.connect(self.cancel_recognition)
        sheet.installEventFilter(self)

        self.rules_card = StatCard("Правила контура")
        self.rules_card.setCursor(Qt.PointingHandCursor)
        self.rules_card.setToolTip("Щёлкните — список нарушений, каждое можно показать на листе")
        self.rules_card.clicked.connect(lambda: self.show_page(PAGES.index("Проверка")))
        grid.addWidget(self.rules_card, 0, 2)
        self.dims_card = StatCard("Размеров")
        grid.addWidget(self.dims_card, 1, 2)

        bottom = QHBoxLayout()
        bottom.setSpacing(18)
        options, lay = _card()
        lay.addWidget(_label("Параметры построения", "cardTitle"))
        self.mode = QComboBox()
        for name, _ in MODES:
            self.mode.addItem(name)
        self.mode.setToolTip(
            "Точно по размерам: длина каждой линии равна числу на её размере (6, а не 6,001); "
            "неуказанное — из других размеров или ближайшее круглое.\n"
            "Как в PDF: точная копия листа, линии не двигаются; в размерах — числа из PDF.")
        self.mode.currentIndexChanged.connect(lambda _: self.recognize())
        self.dims_box = QCheckBox("Размеры по ГОСТ")
        self.dims_box.setChecked(True)
        self.dims_box.setToolTip("Снимите, чтобы построить просто чертёж — без размеров")
        self.param_box = QCheckBox("Параметризация эскиза модели")
        self.param_box.setChecked(True)
        self.param_box.setToolTip(
            "Эскиз 3D-модели с управляющими размерами на отрезках и дугах и связями "
            "(совпадение, горизонталь, вертикаль, касание): изменили размер — модель "
            "перестроилась. Без галочки — эскиз из простых линий.")
        lay.addWidget(self.mode)
        self.scale_box = QComboBox()
        for name, _ in SCALES:
            self.scale_box.addItem(name)
        self.scale_box.setToolTip(
            "Масштаб вида на построенном чертеже. Деталь остаётся в настоящих размерах, "
            "размеры не меняются; не помещается — берётся лист большего формата.")
        lay.addWidget(self.scale_box)
        lay.addWidget(self.dims_box)
        lay.addWidget(self.param_box)
        lay.addStretch(1)
        bottom.addWidget(options, 3)

        def build_card(title, note, button_text, action):
            frame, box = _card()
            box.addWidget(_label(title, "cardTitle"))
            text = _label(note, "sub")
            text.setWordWrap(True)
            box.addWidget(text)
            box.addStretch(1)
            button = QPushButton(button_text, objectName="primary")
            button.setStyleSheet("padding: 0 6px; font-size: 14px;")  # a narrow card
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(action)
            if sys.platform != "win32":
                button.setToolTip("Доступно в Windows с установленным КОМПАС-3D")
            box.addWidget(button)
            bottom.addWidget(frame, 2)
            return button, text

        self.build_button, _ = build_card(
            "Чертёж", "Лист в КОМПАС: геометрия, размеры, таблицы", "Построить чертёж",
            self.build_in_kompas)
        self.model_button, self.model_note = build_card(
            "3D-модель", "Тело вращения (профиль вращается на 360°, лыски, отверстия, резьба) "
            "или призматическая деталь (контур выдавливается на толщину)", "Построить модель",
            self.build_3d)
        self.both_button, _ = build_card(
            "Модель и чертёж", "Главный вид чертежа — вид модели: изменили модель — чертёж "
            "перестроился", "Построить всё", self.build_both)
        if sys.platform == "win32":
            for button, key in ((self.build_button, "Ctrl+B"), (self.model_button, "Ctrl+M"),
                                (self.both_button, "Ctrl+Shift+B")):
                button.setToolTip(key)
        grid.addLayout(bottom, 2, 0, 1, 3)
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
        self.check_button = QPushButton("Проверить КОМПАС", objectName="secondary")
        self.check_button.setToolTip(
            "Пробует в вашем КОМПАС все способы сделать таблицу и вид, связанный с моделью, "
            "и пишет отчёт — пришлите его, если таблицы или «Построить всё» не работают")
        self.check_button.clicked.connect(self.check_kompas)
        logs_button = QPushButton("Папка журналов", objectName="secondary")
        logs_button.setToolTip("Ctrl+L. Журнал каждого запуска сохраняется в файл — пришлите его, "
                               "если что-то пошло не так")
        logs_button.clicked.connect(self.open_log_folder)
        top.addWidget(logs_button)
        top.addWidget(self.check_button)
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
        for button in (self.build_button, self.model_button, self.both_button, self.dxf_button,
                       self.report_button):
            button.setEnabled(ready)
        if self.model_ok is False:
            self.model_button.setEnabled(False)  # only the drawing for this part
            self.both_button.setEnabled(False)
        if sys.platform != "win32":
            for button in (self.build_button, self.model_button, self.both_button):
                button.setEnabled(False)

    # --- open / recognise -----------------------------------------------------------------

    def open_dialog(self) -> None:
        start = self.settings.value("last_dir", str(Path.home()))
        name, _ = QFileDialog.getOpenFileName(
            self, "Открыть чертёж", start,
            "Чертёж (*.pdf *.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp);;PDF (*.pdf);;"
            "Фото или скан (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp)")
        if name:
            self.open_file(Path(name))

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.suffix.lower() in (".pdf",) + IMAGE_SUFFIXES:
                self.open_file(path)
                break
            if path.suffix.lower() == ".m3d":
                self.drawing_from_model(path)
                break

    def open_file(self, path: Path) -> None:
        if self._busy():
            # after the running job: a drawing opened meanwhile is not lost
            self.pending = path
            self._log(f"Откроется после текущей операции: {path.name}")
            self.statusBar().showMessage(f"{path.name} откроется, когда закончится текущая операция")
            return
        self.pending = None
        if path.suffix.lower() in IMAGE_SUFFIXES:
            self.photo_options = self._ask_photo(path)
            if self.photo_options is None:
                return
        self.pdf = path
        self.drawing = None
        self.model_ok = None
        self.show_page(0)
        self.settings.setValue("last_dir", str(path.parent))
        self._fill_recent(remember_file(self.settings, path))
        self.setWindowTitle(f"{APP_NAME} — {path.name}")
        self._show_title()
        self.recognize()

    def _ask_photo(self, path: Path):
        """The sheet format and the scale of a photographed drawing: its numbers
        are not read, so without them the part comes out of the wrong size.
        (sheet sides in mm, scale) or None when cancelled."""
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout

        dialog = QDialog(self)
        dialog.setWindowTitle("Чертёж с фото")
        form = QFormLayout(dialog)
        note = _label("Числа размеров с фото не читаются. Укажите, что написано в основной "
                      "надписи, — тогда деталь получит настоящие размеры (неуказанные округлятся "
                      "до круглых значений).", "sub")
        note.setWordWrap(True)
        form.addRow(note)
        fmt = QComboBox()
        for name, _ in SHEET_FORMATS:
            fmt.addItem(name)
        scale = QComboBox()
        for name, _ in PHOTO_SCALES:
            scale.addItem(name.replace("Масштаб ", ""))
        for key, box in (("photo_format", fmt), ("photo_scale", scale)):
            try:
                box.setCurrentIndex(min(int(self.settings.value(key, 0)), box.count() - 1))
            except (TypeError, ValueError):
                pass
        form.addRow("Формат листа", fmt)
        form.addRow("Масштаб", scale)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Распознать")
        buttons.button(QDialogButtonBox.Cancel).setText("Отмена")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec() != QDialog.Accepted:
            return None
        self.settings.setValue("photo_format", fmt.currentIndex())
        self.settings.setValue("photo_scale", scale.currentIndex())
        return SHEET_FORMATS[fmt.currentIndex()][1], PHOTO_SCALES[scale.currentIndex()][1]

    def _show_title(self) -> None:
        if getattr(self, "pdf", None) is None or not hasattr(self, "title"):
            return
        name = self.pdf.name
        width = max(self.title.width() - 8, 120)
        self.title.setText(self.title.fontMetrics().elidedText(name, Qt.ElideMiddle, width))
        self.title.setToolTip(name)

    def layout_title_later(self) -> None:
        from PySide6.QtCore import QTimer

        QTimer.singleShot(0, self._show_title)  # after the header has its new widths

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._show_title()

    def recognize(self) -> None:
        if self.pdf is None or self._busy():
            return
        self._set_ready(False)
        self.statusBar().showMessage(f"Распознаю {self.pdf.name}…")
        self._log(f"Распознавание: {self.pdf}")
        sheet_mm, scale = (getattr(self, "photo_options", None) or (None, None)) \
            if self.pdf.suffix.lower() in IMAGE_SUFFIXES else (None, None)
        job = RecognizeJob(self.pdf, exact=MODES[self.mode.currentIndex()][1],
                           sheet_mm=sheet_mm, scale=scale)
        exact = MODES[self.mode.currentIndex()][1]
        stages = [s for s in STAGES if exact or s not in STAGES[5:]] + [MODEL_STAGE,
                                                                       PREVIEW_STAGE]
        if self.pdf.suffix.lower() in IMAGE_SUFFIXES:
            stages = [PHOTO_STAGE] + stages
        self.loader.start(f"Читаю {self.pdf.name}", stages)
        job.stage.connect(self.loader.stage)
        self._cancel_target = job
        job.finished.connect(self.on_recognized)
        job.failed.connect(self.on_failed)
        self._start(job)

    def cancel_recognition(self) -> None:
        job = getattr(self, "_cancel_target", None)
        if job is not None and job is self.job and self._busy():
            job.cancel()
            self.loader.cancel_button.setText("Отменяю…")
            self.loader.cancel_button.setEnabled(False)
            self.statusBar().showMessage("Отменяю — остановлюсь после текущего шага")

    def on_recognized(self, drawing: ir.Drawing, png: bytes, page_height: float) -> None:
        self.loader.stop()
        self.drawing, self.page_height = drawing, page_height
        self.preview_dpi = getattr(self.job, "dpi", PREVIEW_DPI)
        self.preview.show_png(png)
        self.preview.set_marks(self._issue_marks(drawing) if self.marks_box.isChecked() else [])
        self.summary.setPlainText(summary_text(drawing))
        self._fill_review(drawing)
        self._show_results(drawing)
        self._judge_model(drawing)
        # the whole account into the journal (and its file): what to send
        # when the drawing came out wrong
        for line in drawing.processing:
            self._log("  " + line)
        for w in drawing.warnings:
            self._log("! " + w[:600])
        counts = drawing.summary()
        self.statusBar().showMessage(
            f"Готово: {len(drawing.entities)} объектов, требуют проверки {counts['review']}")
        self._log("Распознавание завершено")
        self._set_ready(True)

    def _judge_model(self, drawing: ir.Drawing) -> None:
        """Whether a body of revolution can be made: if not, only the drawing."""
        # judged in the background with the recognition (on an assembly the
        # search for a profile took minutes and froze the window)
        ok, why = getattr(drawing, "model_verdict", None) or (None, "не проверено")
        self.model_ok = ok
        if ok is False:
            self.model_note.setText(f"3D-модель не строится — будет только чертёж: {why}.")
            self.model_note.setObjectName("subWarn")
            self._log(f"3D-модель не строится: {why}")
        else:
            self.model_note.setText(why[:1].upper() + why[1:] + (
                "" if ok else ". Проверьте модель после построения") + ".")
            self.model_note.setObjectName("sub")
        self.model_note.style().unpolish(self.model_note)
        self.model_note.style().polish(self.model_note)

    def _show_results(self, drawing: ir.Drawing) -> None:
        self.sheet_chip.setText(f"{drawing.sheet.format} · {drawing.scale.text}")
        self.sheet_chip.show()
        self.layout_title_later()
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
        count = len(drawing.review) + len(drawing.issues)
        self.nav.button(2).setText(f"Проверка · {count}" if count else "Проверка")

    def _issue_place(self, drawing: ir.Drawing, text: str):
        """Sheet point of a broken rule: its coordinates, or its object's middle."""
        m = re.search(r"\((-?[\d.]+); (-?[\d.]+)\)", text)
        if m:
            return float(m.group(1)), float(m.group(2))
        entity = drawing.get(text.split(":", 1)[0])
        return _anchor(entity) if entity else None

    def _issue_marks(self, drawing: ir.Drawing) -> list:
        out = []
        for number, text in enumerate(drawing.issues, 1):
            place = self._issue_place(drawing, text)
            if place:
                x, y = sheet_to_pixel(drawing, self.page_height,
                                      getattr(self, "preview_dpi", PREVIEW_DPI), place)
                out.append((x, y, number))
        return out

    def _fill_review(self, drawing: ir.Drawing) -> None:
        """Broken contour rules first (what each means in the tooltip), then
        the objects recognised with doubt."""
        self.review.clear()

        def header(text: str) -> None:
            item = QListWidgetItem(text)
            item.setFlags(Qt.NoItemFlags)
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            self.review.addItem(item)

        if drawing.issues:
            header(f"Правила контура — нарушений {len(drawing.issues)}")
            for number, text in enumerate(drawing.issues, 1):
                item = QListWidgetItem(f"{number}. {text}")
                item.setData(Qt.UserRole, text.split(":", 1)[0])
                place = self._issue_place(drawing, text)
                if place:
                    item.setData(Qt.UserRole + 1, place)
                item.setToolTip(_rule_meaning(text))
                self.review.addItem(item)
        if drawing.review:
            header(f"Распознаны с сомнением — {len(drawing.review)}")
        for e in drawing.review:
            note = "; ".join(e.notes)
            item = QListWidgetItem(f"{TYPE_NAMES.get(e.kind, e.kind)} {e.id} — {e.confidence:.0%}"
                                   + (f": {note}" if note else ""))
            item.setData(Qt.UserRole, e.id)
            self.review.addItem(item)
        if not drawing.issues and not drawing.review:
            header("Всё в порядке: контур без нарушений, объекты распознаны уверенно")

    def on_review_clicked(self, item: QListWidgetItem) -> None:
        if self.drawing is None or not item.data(Qt.UserRole):
            return
        entity = self.drawing.get(item.data(Qt.UserRole))
        anchor = item.data(Qt.UserRole + 1) or (_anchor(entity) if entity else None)
        if anchor:
            self.show_page(0)
            x, y = sheet_to_pixel(self.drawing, self.page_height,
                                  getattr(self, "preview_dpi", PREVIEW_DPI), anchor)
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
        job = KompasJob(self.drawing, Path(name), with_dimensions=self.dims_box.isChecked(),
                        view_scale=SCALES[self.scale_box.currentIndex()][1])
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
        job = RevolveJob(self.drawing, Path(name), exact=MODES[self.mode.currentIndex()][1],
                         parametric=self.param_box.isChecked())
        job.progress.connect(self._log)
        job.finished.connect(self.on_built)
        job.failed.connect(self.on_failed)
        self._start(job)

    def build_both(self) -> None:
        """The model and the drawing with a view linked to it, side by side."""
        if self.drawing is None or self._busy():
            return
        out = self.pdf.with_name(self.pdf.stem + "_kompas.cdw")
        name, _ = QFileDialog.getSaveFileName(
            self, "Сохранить чертёж (деталь сохранится рядом, .m3d)", str(out), "КОМПАС (*.cdw)")
        if not name:
            return
        self._set_ready(False)
        self.statusBar().showMessage("Строю модель и чертёж в КОМПАС…")
        self.show_page(PAGES.index("Журнал"))
        job = BothJob(self.drawing, Path(name), exact=MODES[self.mode.currentIndex()][1],
                      parametric=self.param_box.isChecked(),
                      with_dimensions=self.dims_box.isChecked(),
                      view_scale=SCALES[self.scale_box.currentIndex()][1])
        job.progress.connect(self._log)
        job.finished.connect(self.on_built)
        job.failed.connect(self.on_failed)
        self._start(job)

    def drawing_from_model(self, model: Path | None = None) -> None:
        if self._busy():
            return
        if not isinstance(model, Path):  # from the button: the click's flag
            start = self.settings.value("last_dir", str(Path.home()))
            name, _ = QFileDialog.getOpenFileName(self, "3D-модель КОМПАС", start,
                                                  "Деталь КОМПАС (*.m3d)")
            if not name:
                return
            model = Path(name)
        out, _ = QFileDialog.getSaveFileName(self, "Сохранить чертёж", str(
            model.with_name(model.stem + "_чертёж.cdw")), "КОМПАС (*.cdw)")
        if not out:
            return
        self.show_page(PAGES.index("Журнал"))
        self.statusBar().showMessage("Строю чертёж по модели…")
        job = ModelDrawingJob(model, Path(out), SCALES[self.scale_box.currentIndex()][1])
        job.progress.connect(self._log)
        job.finished.connect(self.on_built)
        job.failed.connect(self.on_failed)
        self._start(job)

    def check_kompas(self) -> None:
        if self._busy():
            return
        self.show_page(PAGES.index("Журнал"))
        self.statusBar().showMessage("Проверяю КОМПАС…")
        job = CheckJob()
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
        if message == CANCELLED:
            self._log(message)
            self.statusBar().showMessage(message)
            self._set_ready(self.drawing is not None)
            return
        self._log(message)
        self.statusBar().showMessage("Ошибка — подробности в журнале")
        self._set_ready(self.drawing is not None)
        self.show_page(PAGES.index("Журнал"))
        QMessageBox.warning(self, APP_NAME, message.strip().splitlines()[-1])

    def _log(self, text: str) -> None:
        line = stamped(text)
        self.log.appendPlainText(line)
        self.session_log.write(line)

    def open_log_folder(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        folder = self.session_log.folder if self.session_log.path else app_folder()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _toggle_marks(self, on: bool) -> None:
        if self.drawing is not None:
            self.preview.set_marks(self._issue_marks(self.drawing) if on else [])

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


def _rule_meaning(text: str) -> str:
    """What a broken rule means for the drawing, in a sentence."""
    if "наклон" in text:
        return ("Линия почти горизонтальна или вертикальна (или почти под стандартным углом), "
                "но не точно: так обычно рисуют по ошибке. Размер на ней будет неточным, связь "
                "«горизонталь/вертикаль» в КОМПАС не наложится.")
    if "свободный конец" in text:
        return ("Конец линии ни с чем не соединён: контур не замкнут. Штриховка может не "
                "построиться, а 3D-модель — выйти не той формы.")
    if "не сходится" in text:
        return ("Конец почти касается соседнего, но остаётся щель: контур не замкнут. "
                "Обычно это неточность PDF — проверьте, тот ли это угол детали.")
    return "Правило контура не выполнено"


def _broken_rules(drawing: ir.Drawing) -> int:
    """Number of contour rules the pipeline reported as broken (0 when none)."""
    if drawing.issues:
        return len(drawing.issues)
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


def _crash_log() -> None:
    """Where the program died, if it ever does without a Python error (memory,
    a library): %APPDATA%/KompasAI/crash.log — send it with the PDF."""
    import faulthandler

    try:
        stream = open(app_folder() / "crash.log", "w", encoding="utf-8")
        faulthandler.enable(stream, all_threads=True)
        globals()["_CRASH_STREAM"] = stream  # kept open for the whole run
    except OSError:
        pass


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
    _crash_log()
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    icon = _icon_path()
    if icon:
        app.setWindowIcon(QIcon(str(icon)))
    window = MainWindow()
    window.show()
    args = app.arguments()[1:]
    if args and Path(args[0]).exists():
        path = Path(args[0])
        if path.suffix.lower() in (".pdf",) + IMAGE_SUFFIXES:
            window.open_file(path)
        elif path.suffix.lower() == ".m3d":
            window.drawing_from_model(path)
    return app.exec()
