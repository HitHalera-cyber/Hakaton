"""Main window: open a drawing, look at what was recognised, build it in KOMPAS.

    py -m kompas_ai.gui            (or KompasAI.exe)
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QThread
from PySide6.QtGui import (QAction, QBrush, QColor, QFont, QIcon, QKeySequence, QPainter, QPen,
                           QPixmap)
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog, QGraphicsEllipseItem,
                               QGraphicsScene, QGraphicsView, QLabel, QListWidget,
                               QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit,
                               QSplitter, QToolBar, QVBoxLayout, QWidget)

from .. import ir
from ..export.dxf_writer import write_dxf
from ..report.preview import sheet_to_pixel
from ..report.summary import TYPE_NAMES, summary_text
from .workers import PREVIEW_DPI, KompasJob, RecognizeJob, RevolveJob

APP_NAME = "КОМПАС-AI"
MODES = [("Точно по размерам", True), ("Как в PDF (без выравнивания)", False)]
BUILD_MODES = [("Вид с масштабом чертежа", "view"), ("В миллиметрах листа", "sheet")]


class PreviewView(QGraphicsView):
    """Zoomable, draggable preview of the source drawing with the recognised objects."""

    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setBackgroundBrush(QBrush(QColor("#e8e8e8")))
        self.marker: QGraphicsEllipseItem | None = None

    def show_png(self, png: bytes) -> None:
        pix = QPixmap()
        pix.loadFromData(png, "PNG")
        self.scene().clear()
        self.marker = None
        self.scene().addPixmap(pix)
        self.scene().setSceneRect(pix.rect())
        self.fitInView(self.scene().sceneRect(), Qt.KeepAspectRatio)

    def wheelEvent(self, event):
        factor = 1.25 if event.angleDelta().y() > 0 else 0.8
        self.scale(factor, factor)

    def point_at(self, x: float, y: float) -> None:
        if self.marker is not None:
            self.scene().removeItem(self.marker)
        r = 30
        self.marker = self.scene().addEllipse(x - r, y - r, 2 * r, 2 * r,
                                              QPen(QColor("red"), 6), QBrush(Qt.NoBrush))
        self.resetTransform()
        self.scale(1.2, 1.2)
        self.centerOn(x, y)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1400, 860)
        self.settings = QSettings("KompasAI", "KompasAI")
        self.pdf: Path | None = None
        self.drawing: ir.Drawing | None = None
        self.page_height = 0.0
        self.thread: QThread | None = None
        self.job = None

        self.preview = PreviewView()
        self.summary = QPlainTextEdit(readOnly=True)
        mono = QFont("Consolas")
        mono.setStyleHint(QFont.Monospace)
        self.summary.setFont(mono)
        self.summary.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.review = QListWidget()
        self.review.itemClicked.connect(self.on_review_clicked)
        self.log = QPlainTextEdit(readOnly=True)
        self.log.setMaximumBlockCount(500)

        side = QWidget()
        lay = QVBoxLayout(side)
        lay.addWidget(QLabel("<b>Результат распознавания</b>"))
        lay.addWidget(self.summary, 3)
        lay.addWidget(QLabel("<b>Требуют проверки</b> (щёлкните — покажу на листе)"))
        lay.addWidget(self.review, 2)
        lay.addWidget(QLabel("<b>Журнал</b>"))
        lay.addWidget(self.log, 1)

        split = QSplitter()
        split.addWidget(self.preview)
        split.addWidget(side)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 1)
        split.setSizes([980, 420])
        side.setMinimumWidth(320)
        self.setCentralWidget(split)
        self._toolbar()
        self.setAcceptDrops(True)
        self.statusBar().showMessage("Откройте PDF чертежа (или перетащите его в окно)")

    # --- toolbar ------------------------------------------------------------------------

    def _toolbar(self) -> None:
        bar = QToolBar()
        bar.setMovable(False)
        self.addToolBar(bar)

        open_act = QAction("Открыть PDF…", self, shortcut=QKeySequence.Open)
        open_act.triggered.connect(self.open_dialog)
        bar.addAction(open_act)

        self.mode = QComboBox()
        for name, _ in MODES:
            self.mode.addItem(name)
        self.mode.setToolTip("Точно по размерам — геометрия доводится до значений размеров чертежа")
        self.mode.currentIndexChanged.connect(lambda _: self.recognize())
        bar.addWidget(self.mode)
        bar.addSeparator()

        self.build_mode = QComboBox()
        for name, _ in BUILD_MODES:
            self.build_mode.addItem(name)
        self.build_mode.setToolTip(
            "Вид с масштабом: деталь в настоящих размерах, КОМПАС сам считает размеры "
            "(нужна лицензия, иначе — мм листа).\nВ миллиметрах листа: как на PDF, "
            "числа размеров вписываются из PDF.")
        bar.addWidget(self.build_mode)
        self.dims_box = QCheckBox("Размеры")
        self.dims_box.setChecked(True)
        self.dims_box.setToolTip("Снимите, чтобы построить просто чертёж — без размеров")
        bar.addWidget(self.dims_box)
        self.param_box = QCheckBox("Параметризация")
        self.param_box.setChecked(True)
        self.param_box.setToolTip("Связи: горизонталь, вертикаль, совпадение концов, касание, "
                                  "концентричность (нужна лицензия КОМПАС)")
        bar.addWidget(self.param_box)

        self.build_act = QAction("Построить в КОМПАС", self)
        self.build_act.triggered.connect(self.build_in_kompas)
        if sys.platform != "win32":
            self.build_act.setToolTip("Доступно в Windows с установленным КОМПАС-3D")
        bar.addAction(self.build_act)

        self.model_act = QAction("3D-модель (тело вращения)", self)
        self.model_act.setToolTip("Деталь КОМПАС-3D: профиль над осью (разрез) вращается на 360°")
        self.model_act.triggered.connect(self.build_3d)
        bar.addAction(self.model_act)

        self.dxf_act = QAction("Сохранить DXF…", self)
        self.dxf_act.triggered.connect(self.save_dxf)
        bar.addAction(self.dxf_act)

        self.report_act = QAction("Сохранить отчёт…", self)
        self.report_act.triggered.connect(self.save_report)
        bar.addAction(self.report_act)

        self.fit_act = QAction("Весь лист", self)
        self.fit_act.triggered.connect(
            lambda: self.preview.fitInView(self.preview.scene().sceneRect(), Qt.KeepAspectRatio))
        bar.addAction(self.fit_act)
        self._set_ready(False)

    def _set_ready(self, ready: bool) -> None:
        for act in (self.build_act, self.model_act, self.dxf_act, self.report_act):
            act.setEnabled(ready)
        if sys.platform != "win32":
            self.build_act.setEnabled(False)
            self.model_act.setEnabled(False)

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
        self.pdf = path
        self.settings.setValue("last_dir", str(path.parent))
        self.setWindowTitle(f"{APP_NAME} — {path.name}")
        self.recognize()

    def recognize(self) -> None:
        if self.pdf is None or self._busy():
            return
        self._set_ready(False)
        self.statusBar().showMessage(f"Распознаю {self.pdf.name}…")
        self._log(f"Распознавание: {self.pdf}")
        job = RecognizeJob(self.pdf, exact=MODES[self.mode.currentIndex()][1])
        job.finished.connect(self.on_recognized)
        job.failed.connect(self.on_failed)
        self._start(job)

    def on_recognized(self, drawing: ir.Drawing, png: bytes, page_height: float) -> None:
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
        counts = drawing.summary()
        self.statusBar().showMessage(
            f"Готово: {len(drawing.entities)} объектов, требуют проверки {counts['review']}")
        self._log("Распознавание завершено")
        self._set_ready(True)

    def on_review_clicked(self, item: QListWidgetItem) -> None:
        if self.drawing is None:
            return
        entity = self.drawing.get(item.data(Qt.UserRole))
        anchor = _anchor(entity) if entity else None
        if anchor:
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
        job = RevolveJob(self.drawing, Path(name))
        job.progress.connect(self._log)
        job.finished.connect(self.on_built)
        job.failed.connect(self.on_failed)
        self._start(job)

    def on_built(self, report: str) -> None:
        self._log(report)
        self.statusBar().showMessage("Чертёж построен в КОМПАС")
        self._set_ready(True)
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
        self._log(message)
        self.statusBar().showMessage("Ошибка — подробности в журнале")
        self._set_ready(self.drawing is not None)
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
        self.thread.start()


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
