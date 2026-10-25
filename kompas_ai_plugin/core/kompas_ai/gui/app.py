"""Main window: open a drawing, look at what was recognised, build it in KOMPAS.

    py -m kompas_ai.gui            (or KompasAI.exe)

The window is the program; its look is one of three layouts (layouts.py) —
«Инженер», «Мастер», «Пульт» — chosen at the top and switched on the fly.
Every command is a QAction here and every control holding a state one
widget here, so all the layouts can do all of it.
"""

from __future__ import annotations

import math
import re
import sys
from pathlib import Path

from PySide6.QtCore import QEvent, QSettings, Qt, QThread, QTimer
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog, QListWidget,
                               QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPlainTextEdit)

from .. import ir
from ..export.dxf_writer import write_dxf
from ..pipeline import STAGES
from ..report.preview import pixel_to_sheet, sheet_to_pixel
from ..report.summary import TYPE_NAMES, summary_text
from .layouts import LAYOUT_NAMES, LAYOUTS, PAGES
from .loader import DraftingLoader
from ..semantics.orphans import key_of, text_center
from .refine import RefineDialog, dimension_rows, orphan_rows, questions
from .session import SessionLog, app_folder, recent_files, remember_file, stamped
from .theme import THEME_ICONS, THEME_NAMES, THEMES, style_sheet
from .widgets import PreviewView, label
from .workers import (CANCELLED, IMAGE_SUFFIXES, MODEL_STAGE, PHOTO_STAGE, PREVIEW_DPI,
                      PREVIEW_STAGE, BothJob, CheckJob, KompasJob, ModelDrawingJob, RecognizeJob,
                      RevolveJob)

APP_NAME = "КОМПАС-AI"
MODES = [("Точно по размерам", True), ("Как в PDF (без выравнивания)", False)]
SCALES = [("Масштаб как на чертеже", None)] + [
    (f"Масштаб {name}", value) for name, value in (
        ("1:1", 1.0), ("1:2", 0.5), ("1:2,5", 0.4), ("1:4", 0.25), ("1:5", 0.2), ("1:10", 0.1),
        ("2:1", 2.0), ("2,5:1", 2.5), ("4:1", 4.0), ("5:1", 5.0), ("10:1", 10.0))]
SHEET_FORMATS = [("Авто — по основной надписи", None), ("A4", (210.0, 297.0)), ("A3", (297.0, 420.0)), ("A2", (420.0, 594.0)),
                 ("A1", (594.0, 841.0)), ("A0", (841.0, 1189.0))]
PHOTO_SCALES = [(name, value) for name, value in SCALES[1:]]
MIN_W, MIN_H = 960, 600  # a 1024×768 screen with its taskbar still holds the window
IMAGE_FILTER = "Фото или скан (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp)"
KINDS = [("Основные линии", lambda e: isinstance(e, ir.Line) and e.style == ir.STYLE_MAIN),
         ("Тонкие линии", lambda e: isinstance(e, ir.Line) and e.style == ir.STYLE_THIN),
         ("Осевые", lambda e: isinstance(e, ir.Line) and e.style == ir.STYLE_AXIAL),
         ("Окружности и дуги", lambda e: isinstance(e, (ir.Circle, ir.Arc, ir.Ellipse))),
         ("Штриховки", lambda e: isinstance(e, ir.Hatch)),
         ("Размеры", lambda e: isinstance(e, ir.Dimension)),
         ("Тексты", lambda e: isinstance(e, ir.Text)),
         ("Таблицы", lambda e: isinstance(e, ir.Table))]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.app_name = APP_NAME
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(MIN_W, MIN_H)
        self.settings = QSettings("KompasAI", "KompasAI")
        self.session_log = SessionLog()
        self.pdf: Path | None = None
        self.drawing: ir.Drawing | None = None
        self.page_height = 0.0
        self.thread: QThread | None = None
        self.job = None
        self.pending: Path | None = None
        self.model_ok: bool | None = None
        self.ready = False
        self.overrides: dict = {}  # dimension id → the user's value, for the open drawing
        self.attach: dict = {}  # text id of a size without its line → what it measures
        self.counters = {"opened": 0, "built": 0, "refined": 0, "photos": 0}
        self.ui = None

        self._make_actions()
        self._make_shared()
        self._restore_options()
        self.setAcceptDrops(True)
        self.theme = self.settings.value("theme", "light")
        name = self.settings.value("layout", "engineer")
        self.apply_layout(name if name in LAYOUTS else "engineer")
        self.apply_theme(self.theme)
        self._fit_to_screen()
        self._set_ready(False)
        self.statusBar().showMessage("Откройте PDF чертежа (или перетащите его в окно)")

    # --- the commands and the shared controls ---------------------------------------------

    def _make_actions(self) -> None:
        def act(key, text, slot, shortcut=None, tip=""):
            a = QAction(text, self)
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            if tip:
                a.setToolTip(tip)
            a.triggered.connect(lambda _=False: slot())
            self.addAction(a)  # the key works whatever layout shows the button
            self.acts[key] = a
            return a

        self.acts: dict[str, QAction] = {}
        act("open", "Открыть PDF / фото", self.open_dialog, QKeySequence.Open,
            "Можно и перетащить файл в окно (PDF, фото, .m3d)")
        act("photo", "Чертёж с фото", self.open_photo_dialog)
        act("from_model", "Чертёж по модели…", self.drawing_from_model, None,
            "Открыть 3D-модель КОМПАС (.m3d) и построить её чертёж: виды спереди, сверху, слева "
            "и изометрия, связанные с моделью")
        act("build", "Построить чертёж", self.build_in_kompas, "Ctrl+B",
            "Лист в КОМПАС: геометрия, размеры, таблицы")
        act("model", "Построить модель", self.build_3d, "Ctrl+M",
            "Тело вращения или призматическая деталь в КОМПАС")
        act("both", "Построить всё", self.build_both, "Ctrl+Shift+B",
            "Модель и чертёж, главный вид которого — вид модели: изменили модель — чертёж "
            "перестроился")
        act("refine", "Уточнить размеры…", lambda: self.refine(), "Ctrl+R",
            "Все размеры чертежа: что написано, что по линиям, выдержан ли; своё число — и "
            "чертёж пересчитается")
        act("dxf", "Сохранить DXF…", self.save_dxf)
        act("report", "Сохранить отчёт…", self.save_report)
        act("check", "Проверить КОМПАС", self.check_kompas, None,
            "Пробует в вашем КОМПАС все способы сделать таблицу и вид, связанный с моделью, и "
            "пишет отчёт — пришлите его, если таблицы или «Построить всё» не работают")
        act("logs", "Папка журналов", self.open_log_folder, "Ctrl+L",
            "Журнал каждого запуска сохраняется в файл — пришлите его, если что-то пошло не так")
        act("fit", "Весь лист", lambda: self.preview.fit(), "Ctrl+0")
        act("cancel", "Отменить", self.cancel_recognition, "Esc")
        act("theme", "◐  Тема", self.toggle_theme, None, "Сменить тему")
        for i in range(len(PAGES)):
            act(f"page{i}", PAGES[i], lambda i=i: self.show_page(i), f"Ctrl+{i + 1}")
        if sys.platform != "win32":
            for key in ("build", "model", "both", "from_model", "check"):
                self.acts[key].setToolTip("Доступно в Windows с установленным КОМПАС-3D")

    def _make_shared(self) -> None:
        self.preview = PreviewView()
        self.preview.setAcceptDrops(False)  # a PDF dropped on the drawing reaches the window
        self.preview.viewport().setAcceptDrops(False)
        self.preview.clicked.connect(self.on_sheet_clicked)
        self.preview.setToolTip("Щелчок по размеру — изменить его. Колесо — масштаб, "
                                "перетаскивание — сдвиг, двойной щелчок или Ctrl+0 — весь лист")
        self.summary = QPlainTextEdit(readOnly=True, objectName="report")
        self.summary.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.review = QListWidget()
        self.review.itemClicked.connect(self.on_review_clicked)
        self.log = QPlainTextEdit(readOnly=True, objectName="log")
        self.log.setMaximumBlockCount(500)

        self.mode = QComboBox()
        for name, _ in MODES:
            self.mode.addItem(name)
        self.mode.setToolTip(
            "Точно по размерам: длина каждой линии равна числу на её размере (6, а не 6,001); "
            "неуказанное — из других размеров или ближайшее круглое.\n"
            "Как в PDF: точная копия листа, линии не двигаются; в размерах — числа из PDF.")
        self.mode.currentIndexChanged.connect(lambda _: self.recognize())
        self.scale_box = QComboBox()
        for name, _ in SCALES:
            self.scale_box.addItem(name)
        self.scale_box.setToolTip(
            "Масштаб вида на построенном чертеже. Деталь остаётся в настоящих размерах, "
            "размеры не меняются; не помещается — берётся лист большего формата.")
        self.dims_box = QCheckBox("Размеры по ГОСТ")
        self.dims_box.setChecked(True)
        self.dims_box.setToolTip("Снимите, чтобы построить просто чертёж — без размеров")
        self.param_box = QCheckBox("Параметризация эскиза модели")
        self.param_box.setChecked(True)
        self.param_box.setToolTip(
            "Эскиз 3D-модели с управляющими размерами на отрезках и дугах и связями "
            "(совпадение, горизонталь, вертикаль, касание): изменили размер — модель "
            "перестроилась. Без галочки — эскиз из простых линий.")
        self.marks_box = QCheckBox("Нарушения на листе")
        self.marks_box.setChecked(True)
        self.marks_box.setToolTip("Красные кольца с номерами там, где контур нарушает правила")
        self.marks_box.toggled.connect(self._toggle_marks)
        self.layout_box = QComboBox()
        self.layout_box.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        for _, title in LAYOUT_NAMES:
            self.layout_box.addItem(f"Вид: {title}")
        self.layout_box.setToolTip("Оформление окна. Всё, что умеет программа, есть в каждом")
        self.layout_box.currentIndexChanged.connect(
            lambda i: QTimer.singleShot(0, lambda: self.apply_layout(LAYOUT_NAMES[i][0])))
        ready = sys.platform == "win32"
        self.kompas_note = label("КОМПАС-3D v23<br>" + (
            "строит в Windows" if ready else "доступен только в Windows"), "kompas")
        self.kompas_note.setTextFormat(Qt.RichText)
        self.kompas_note.setWordWrap(True)
        self.recent_menu = QMenu(self)
        self._fill_recent()
        self.loader = DraftingLoader(None)
        self.loader.cancel_button.clicked.connect(self.cancel_recognition)
        self.shared = [self.preview, self.summary, self.review, self.log, self.mode,
                       self.scale_box, self.dims_box, self.param_box, self.marks_box,
                       self.layout_box, self.kompas_note]

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

    # --- the window on the screen -------------------------------------------------------------

    def _fit_to_screen(self) -> None:
        """The size it was left at, or a size that fits this screen: a window
        wider than the monitor (1440 on a 1280 one) had its right column out
        of sight."""
        screen = self.screen().availableGeometry() if self.screen() else None
        saved = self.settings.value("geometry")
        if saved is not None and self.restoreGeometry(saved) and screen is not None \
                and screen.contains(self.frameGeometry().center()) \
                and self.width() <= screen.width() and self.height() <= screen.height():
            return
        if screen is None:
            self.resize(1440, 900)
            return
        w = min(1440, int(screen.width() * 0.94))
        h = min(900, int(screen.height() * 0.92))
        self.resize(max(w, MIN_W), max(h, MIN_H))
        self.move(screen.x() + (screen.width() - self.width()) // 2,
                  screen.y() + (screen.height() - self.height()) // 2)
        # a small screen (a laptop): the whole of it
        self.start_maximized = screen.width() < 1366 or screen.height() < 800

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.ui is not None:
            self.ui.on_resize(self.width(), self.height())

    def closeEvent(self, event):
        self.settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(event)

    # --- layouts and themes ----------------------------------------------------------------

    def apply_layout(self, key: str) -> None:
        """Build the chosen look and move the shared controls into it; the
        drawing, the options and a running job stay as they are."""
        if self.ui is not None and self.ui.key == key:
            return
        page = self.current_page()
        for widget in self.shared + [self.loader]:
            widget.setParent(None)  # out of the old look before it is deleted
        self.ui = LAYOUTS[key](self)
        central = self.ui.build()
        self.setCentralWidget(central)
        index = [k for k, _ in LAYOUT_NAMES].index(key)
        if self.layout_box.currentIndex() != index:
            self.layout_box.blockSignals(True)
            self.layout_box.setCurrentIndex(index)
            self.layout_box.blockSignals(False)
        self.settings.setValue("layout", key)
        host = self.ui.sheet_host
        self.loader.setParent(host)
        self.loader.setGeometry(host.rect())
        host.installEventFilter(self)
        if self.loader.timer.isActive():  # a recognition running
            self.loader.show()
            self.loader.raise_()
        self.ui.set_colors(THEMES.get(getattr(self, "theme", "light"), THEMES["light"]))
        self.ui.show_drawing(self.info())
        self.ui.on_resize(self.width(), self.height())
        if page:
            self.ui.show_page(page)
        self.preview.fit()

    def current_page(self) -> int:
        return getattr(self, "_page", 0)

    def eventFilter(self, obj, event):
        if self.ui is not None and obj is self.ui.sheet_host and event.type() == QEvent.Resize:
            self.loader.setGeometry(obj.rect())
        return super().eventFilter(obj, event)

    def apply_theme(self, name: str) -> None:
        self.theme = name if name in THEMES else "light"
        colors = THEMES[self.theme]
        self.setStyleSheet(style_sheet(colors))
        self.preview.set_colors(colors)
        self.loader.set_colors(colors)
        if self.ui is not None:
            self.ui.set_colors(colors)
        nxt = self._next_theme()
        self.acts["theme"].setText(f"{THEME_ICONS[nxt]}  {THEME_NAMES[nxt]}")
        self.settings.setValue("theme", self.theme)

    def _next_theme(self) -> str:
        names = list(THEMES)
        return names[(names.index(self.theme) + 1) % len(names)]

    def toggle_theme(self) -> None:
        self.apply_theme(self._next_theme())

    def _set_ready(self, ready: bool) -> None:
        self.ready = ready
        for key in ("build", "model", "both", "dxf", "report", "refine"):
            self.acts[key].setEnabled(ready)
        if self.model_ok is False:
            self.acts["model"].setEnabled(False)  # only the drawing for this part
            self.acts["both"].setEnabled(False)
        if sys.platform != "win32":
            for key in ("build", "model", "both"):
                self.acts[key].setEnabled(False)

    def recent_paths(self) -> list[Path]:
        return recent_files(self.settings)

    def _fill_recent(self, paths=None) -> None:
        self.recent_menu.clear()
        paths = recent_files(self.settings) if paths is None else paths
        for path in paths:
            act = self.recent_menu.addAction(path.name)
            act.setToolTip(str(path))
            act.triggered.connect(lambda _=False, p=path: self.open_file(p))
        if not paths:
            self.recent_menu.addAction("пока пусто").setEnabled(False)

    # --- what the layouts show -------------------------------------------------------------

    def info(self) -> dict | None:
        """The drawing's figures, the same for every layout."""
        d = self.drawing
        if d is None:
            return None
        exact = MODES[self.mode.currentIndex()][1]
        rows = dimension_rows(d)
        ask = questions(d) if exact else orphan_rows(d)
        ok, why = getattr(d, "model_verdict", None) or (None, "не проверено")
        if ok is False:
            model_text = f"3D-модель не строится — будет только чертёж: {why}."
        else:
            model_text = why[:1].upper() + why[1:] + (
                "" if ok else ". Проверьте модель после построения") + "."
        issues = _broken_rules(d) if exact else 0
        held = sum(1 for r in rows if r["state"] == "выдержан") if exact else 0
        chips = [(f"{d.sheet.format} · {d.scale.text}", "")]
        if exact:
            chips.append((f"размеров точно {held} из {len(rows)}",
                          "ok" if held == len(rows) else "warn"))
            chips.append((f"нарушений {issues}" if issues else "контур замкнут",
                          "warn" if issues else "ok"))
        else:
            chips.append(("как в PDF, без выравнивания", ""))
        if self.overrides or self.attach:
            chips.append((f"уточнено вручную: {len(self.overrides) + len(self.attach)}", ""))
        return {
            "name": self.pdf.name if self.pdf else "",
            "format": d.sheet.format, "scale": d.scale.text, "exact": exact,
            "photo": bool(getattr(d, "raster", False)),
            "objects": len(d.entities), "dims": len(rows), "held": held,
            "questions": ask, "issues": issues,
            "issue_list": list(enumerate(d.issues, 1)) if exact else [],
            "to_check": len(d.review) + len(d.issues),
            "counts": [(name, n) for name, test in KINDS
                       if (n := sum(1 for e in d.entities if test(e)))],
            "model_ok": ok, "model_text": model_text, "chips": chips,
        }

    # --- open / recognise -----------------------------------------------------------------

    def open_dialog(self, image_only: bool = False) -> None:
        start = self.settings.value("last_dir", str(Path.home()))
        filters = IMAGE_FILTER if image_only else (
            "Чертёж (*.pdf *.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp);;PDF (*.pdf);;"
            + IMAGE_FILTER)
        name, _ = QFileDialog.getOpenFileName(self, "Открыть чертёж", start, filters)
        if name:
            self.open_file(Path(name))

    def open_photo_dialog(self) -> None:
        self.open_dialog(image_only=True)

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
            self.counters["photos"] += 1
        self.pdf = path
        self.drawing = None
        self.model_ok = None
        self.overrides = {}
        self.attach = {}
        self.counters["opened"] += 1
        self.settings.setValue("last_dir", str(path.parent))
        self._fill_recent(remember_file(self.settings, path))
        self.setWindowTitle(f"{APP_NAME} — {path.name}")
        self.ui.show_drawing(None)
        self.show_page(0)
        self.recognize()

    def _ask_photo(self, path: Path):
        """The sheet format and the scale of a photographed drawing: its numbers
        are not read, so without them the part comes out of the wrong size.
        (sheet sides in mm, scale) or None when cancelled."""
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout

        dialog = QDialog(self)
        dialog.setWindowTitle("Чертёж с фото")
        form = QFormLayout(dialog)
        note = label("Числа размеров с фото не читаются. Укажите масштаб из основной надписи "
                     "— тогда деталь получит настоящие размеры (неуказанные округлятся до "
                     "круглых значений). Формат листа программа узнаёт по основной надписи "
                     "(её ширина по ГОСТ — 185 мм); если рамки на фото нет, выберите его сами.",
                     "sub")
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

    def recognize(self) -> None:
        if self.pdf is None or self._busy():
            return
        self._set_ready(False)
        self.statusBar().showMessage(f"Распознаю {self.pdf.name}…")
        self._log(f"Распознавание: {self.pdf}")
        sheet_mm, scale = (getattr(self, "photo_options", None) or (None, None)) \
            if self.pdf.suffix.lower() in IMAGE_SUFFIXES else (None, None)
        exact = MODES[self.mode.currentIndex()][1]
        job = RecognizeJob(self.pdf, exact=exact, sheet_mm=sheet_mm, scale=scale,
                           overrides=self.overrides, attach=self.attach)
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
        ok, why = getattr(drawing, "model_verdict", None) or (None, "не проверено")
        self.model_ok = ok
        if ok is False:
            self._log(f"3D-модель не строится: {why}")
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
        self.ui.show_drawing(self.info())

    # --- «Уточнить размеры» -----------------------------------------------------------------

    def refine(self, focus: str | None = None) -> None:
        """The table of sizes; the drawing recognised again with the user's values."""
        if self.drawing is None or self._busy():
            return
        photo = bool(getattr(self.drawing, "raster", False))
        dialog = RefineDialog(self.drawing, self.overrides, self, photo=photo, focus=focus,
                              attach=self.attach)
        if dialog.exec() != RefineDialog.DialogCode.Accepted:
            return
        if dialog.photo_requested:
            options = self._ask_photo(self.pdf)
            if options is not None:
                self.photo_options = options
                self.recognize()
            return
        if dialog.overrides == self.overrides and dialog.attach == self.attach:
            return
        self.counters["refined"] += len(set(dialog.overrides) - set(self.overrides)) \
            + len(set(dialog.attach) - set(self.attach))
        if dialog.overrides != self.overrides:
            self._log("Размеры уточнены вручную: " + (", ".join(
                f"{k} = {v:g}" for k, v in sorted(dialog.overrides.items())) or "сброшены"))
        for text_id in sorted(set(dialog.attach) - set(self.attach)):
            self._log(self._attach_note(text_id, dialog.attach[text_id]))
        self.overrides, self.attach = dialog.overrides, dialog.attach
        self.recognize()

    def _attach_note(self, text_id: str, choice) -> str:
        t = self.drawing.get(text_id) if self.drawing else None
        what = f"«{t.text}»" if t is not None else text_id
        if choice is None:
            return f"{what}: оставлен текстом"
        return f"{what}: привязан — {choice['kind']} по {', '.join(choice['refs'])}"

    def attach_orphan(self, text_id: str, index) -> None:
        """A size without its dimension line: the object it measures (its
        candidate ``index``) or None — just text; the drawing is read again."""
        if self.drawing is None or self._busy():
            return
        row = next((o for o in orphan_rows(self.drawing) if o["id"] == text_id), None)
        if row is None:
            return
        if index is None:
            choice = None
        elif 0 <= index < len(row["candidates"]):
            choice = key_of(row["candidates"][index])
        else:
            return
        self.attach[text_id] = choice
        self.counters["refined"] += 1
        self._log(self._attach_note(text_id, choice))
        self.recognize()

    def trust_lines(self, dim_id: str) -> None:
        """A size that contradicts the others takes what its lines measure."""
        if self.drawing is None or self._busy():
            return
        row = next((r for r in dimension_rows(self.drawing) if r["id"] == dim_id), None)
        if row is None or row["lines"] is None:
            return
        self.overrides[dim_id] = round(row["lines"], 2)
        self.counters["refined"] += 1
        self._log(f"{dim_id}: принято значение по линиям {self.overrides[dim_id]:g}")
        self.recognize()

    REACH = 8.0  # sheet mm: how far from a size's number a click still picks it

    def size_at(self, p) -> str | None:
        """The size (or the number without a dimension line) nearest to a
        sheet point: its number, its dimension line."""
        best, found = self.REACH, None
        for e in self.drawing.entities:
            if isinstance(e, ir.Dimension):
                spots = [q for q in (e.text_center, e.text_pos, e.line_point) if q]
            elif isinstance(e, ir.Text) and any(o["id"] == e.id
                                                for o in orphan_rows(self.drawing)):
                spots = [text_center(e), e.position]
            else:
                continue
            for q in spots:
                d = math.dist(p, q)
                if d < best:
                    best, found = d, e.id
        return found

    def on_sheet_clicked(self, x: float, y: float) -> None:
        """A click on a size on the sheet: its row in «Уточнить размеры»."""
        if self.drawing is None or self._busy():
            return
        p = pixel_to_sheet(self.drawing, self.page_height,
                           getattr(self, "preview_dpi", PREVIEW_DPI), x, y)
        found = self.size_at(p)
        if found is None:
            self.statusBar().showMessage("Щёлкните по числу размера, чтобы изменить его", 4000)
            return
        self.refine(found)

    def point_at_entity(self, entity_id: str) -> None:
        if self.drawing is None:
            return
        entity = self.drawing.get(entity_id)
        anchor = _anchor(entity) if entity else None
        if anchor:
            self._point(anchor)

    def point_at_issue(self, text: str) -> None:
        if self.drawing is None:
            return
        place = self._issue_place(self.drawing, text)
        if place:
            self._point(place)

    def _point(self, anchor) -> None:
        self.show_page(0)
        x, y = sheet_to_pixel(self.drawing, self.page_height,
                              getattr(self, "preview_dpi", PREVIEW_DPI), anchor)
        self.preview.point_at(x, y)

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
            self._point(anchor)

    # --- outputs -----------------------------------------------------------------------------

    def _run_build(self, job, message: str) -> None:
        self._set_ready(False)
        self.statusBar().showMessage(message)
        self.show_page(PAGES.index("Журнал"))
        job.progress.connect(self._log)
        job.finished.connect(self.on_built)
        job.failed.connect(self.on_failed)
        self._start(job)

    def build_in_kompas(self) -> None:
        if self.drawing is None or self._busy():
            return
        out = self.pdf.with_name(self.pdf.stem + "_kompas.cdw")
        name, _ = QFileDialog.getSaveFileName(self, "Сохранить чертёж КОМПАС", str(out),
                                              "КОМПАС (*.cdw)")
        if name:
            self._run_build(KompasJob(self.drawing, Path(name),
                                      with_dimensions=self.dims_box.isChecked(),
                                      view_scale=SCALES[self.scale_box.currentIndex()][1]),
                            "Строю чертёж в КОМПАС…")

    def build_3d(self) -> None:
        if self.drawing is None or self._busy():
            return
        out = self.pdf.with_name(self.pdf.stem + "_kompas.m3d")
        name, _ = QFileDialog.getSaveFileName(self, "Сохранить деталь КОМПАС", str(out),
                                              "Деталь КОМПАС (*.m3d)")
        if name:
            self._run_build(RevolveJob(self.drawing, Path(name),
                                       exact=MODES[self.mode.currentIndex()][1],
                                       parametric=self.param_box.isChecked()),
                            "Строю 3D-модель в КОМПАС…")

    def build_both(self) -> None:
        """The model and the drawing with a view linked to it, side by side."""
        if self.drawing is None or self._busy():
            return
        out = self.pdf.with_name(self.pdf.stem + "_kompas.cdw")
        name, _ = QFileDialog.getSaveFileName(
            self, "Сохранить чертёж (деталь сохранится рядом, .m3d)", str(out), "КОМПАС (*.cdw)")
        if name:
            self._run_build(BothJob(self.drawing, Path(name),
                                    exact=MODES[self.mode.currentIndex()][1],
                                    parametric=self.param_box.isChecked(),
                                    with_dimensions=self.dims_box.isChecked(),
                                    view_scale=SCALES[self.scale_box.currentIndex()][1]),
                            "Строю модель и чертёж в КОМПАС…")

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
        if out:
            self._run_build(ModelDrawingJob(model, Path(out),
                                            SCALES[self.scale_box.currentIndex()][1]),
                            "Строю чертёж по модели…")

    def check_kompas(self) -> None:
        if self._busy():
            return
        self._run_build(CheckJob(), "Проверяю КОМПАС…")

    def show_page(self, index: int) -> None:
        self._page = index
        if self.ui is not None:
            self.ui.show_page(index)

    def on_built(self, report: str) -> None:
        self._log(report)
        self.counters["built"] += 1
        self.statusBar().showMessage("Построено в КОМПАС — подробности в журнале")
        self._set_ready(self.drawing is not None)
        self.show_page(PAGES.index("Журнал"))
        QMessageBox.information(self, APP_NAME, report)

    def save_dxf(self) -> None:
        if self.drawing is None:
            return
        name, _ = QFileDialog.getSaveFileName(
            self, "Сохранить DXF", str(self.pdf.with_suffix(".dxf")), "DXF (*.dxf)")
        if name:
            write_dxf(self.drawing, name)
            self._log(f"DXF сохранён: {name}")

    def save_report(self) -> None:
        if self.drawing is None:
            return
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
    if getattr(window, "start_maximized", False):
        window.showMaximized()
    else:
        window.show()
    args = app.arguments()[1:]
    if args and Path(args[0]).exists():
        path = Path(args[0])
        if path.suffix.lower() in (".pdf",) + IMAGE_SUFFIXES:
            window.open_file(path)
        elif path.suffix.lower() == ".m3d":
            window.drawing_from_model(path)
    return app.exec()
